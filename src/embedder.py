import json
import os
import time
from typing import Optional
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    PayloadSchemaType,
)
from dotenv import load_dotenv

load_dotenv()

# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────

MODEL_NAME = "paraphrase-multilingual-mpnet-base-v2"
VECTOR_DIM = 768
COLLECTION_NAME = "skincare_products"

# Qdrant — reads from .env
# For Qdrant Cloud:  QDRANT_URL + QDRANT_API_KEY
# For local Docker:  QDRANT_URL=http://localhost:6333 (no key needed)
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", None)

# Data files — adjust paths as needed
DATA_FILES = [
    "data/dermaco_products.json",
    "data/minimalist_products_cleaned.json",
]


# ──────────────────────────────────────────────
# TEXT BUILDER
# Fields: product_name + description + target_concerns + tags
# Ingredients intentionally excluded — too chemical/technical,
# would dilute intent-based semantic matching.
# ──────────────────────────────────────────────

def build_embedding_text(product: dict) -> str:
    """
    Constructs a single, rich natural-language string per product
    for embedding. Field order matters — more important signal first.
    """
    parts = []

    name = product.get("product_name", "").strip()
    if name:
        parts.append(name)

    description = product.get("description", "").strip()
    if description:
        # Truncate to 400 chars — keeps us well within model token limits
        # even after tokenization overhead
        parts.append(description[:400])

    concerns = product.get("target_concerns", "").strip()
    if concerns:
        parts.append(f"Helps with: {concerns}")

    tags = product.get("tags", "").strip()
    if tags:
        parts.append(f"Tags: {tags}")

    return " | ".join(parts)


# ──────────────────────────────────────────────
# PAYLOAD BUILDER
# Everything stored as metadata in Qdrant —
# used for display, filtering, and API responses
# ──────────────────────────────────────────────

def build_payload(product: dict) -> dict:
    """
    Stores the full product record as Qdrant payload.
    This is what gets returned to the API / frontend on a search hit.
    """
    return {
        "brand": product.get("brand", ""),
        "product_name": product.get("product_name", ""),
        "description": product.get("description", ""),
        "price": product.get("price", 0.0),
        "rating": product.get("rating"),
        "review_count": product.get("review_count"),
        "product_url": product.get("product_url", ""),
        "image_url": product.get("image_url", ""),
        "category": product.get("category", ""),
        "target_concerns": product.get("target_concerns", ""),
        "ingredients": product.get("ingredients", ""),
        "tags": product.get("tags", ""),
    }


# ──────────────────────────────────────────────
# QDRANT SETUP
# ──────────────────────────────────────────────

def get_qdrant_client() -> QdrantClient:
    """Initializes Qdrant client — supports both Cloud and local Docker."""
    if QDRANT_API_KEY:
        print(f"🔌 Connecting to Qdrant Cloud: {QDRANT_URL}")
        client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    else:
        print(f"🔌 Connecting to Qdrant Local: {QDRANT_URL}")
        client = QdrantClient(url=QDRANT_URL)
    return client


def _ensure_indexes(client: QdrantClient):
    """
    Creates payload indexes on all filterable fields.
    create_payload_index is idempotent — safe to call even if the
    index already exists. Only indexes fields that are actually in
    the payload AND used in search filters.
    """
    client.create_payload_index(COLLECTION_NAME, "brand", PayloadSchemaType.KEYWORD)
    client.create_payload_index(COLLECTION_NAME, "category", PayloadSchemaType.KEYWORD)
    client.create_payload_index(COLLECTION_NAME, "price", PayloadSchemaType.FLOAT)
    print(f"✅ Indexes ensured on: brand, category, price")


def setup_collection(client: QdrantClient, recreate: bool = False):
    """
    Creates the Qdrant collection if it doesn't exist.
    Set recreate=True to wipe and rebuild from scratch.
    Indexes are always ensured regardless of path taken.
    """
    existing = [c.name for c in client.get_collections().collections]

    if COLLECTION_NAME in existing:
        if recreate:
            print(f"🗑️  Deleting existing collection: {COLLECTION_NAME}")
            client.delete_collection(COLLECTION_NAME)
        else:
            print(f"✅ Collection '{COLLECTION_NAME}' already exists.")
            # Always ensure indexes — covers the case where the collection
            # existed before indexes were added to this script.
            _ensure_indexes(client)
            return

    print(f"📦 Creating collection: {COLLECTION_NAME}")
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(
            size=VECTOR_DIM,
            distance=Distance.COSINE,  # Cosine similarity for semantic search
        ),
    )
    _ensure_indexes(client)


# ──────────────────────────────────────────────
# MAIN EMBEDDER
# ──────────────────────────────────────────────

def load_products(filepaths: list[str]) -> list[dict]:
    """Loads and merges all product JSON files."""
    all_products = []
    for path in filepaths:
        if not os.path.exists(path):
            print(f"⚠️  File not found, skipping: {path}")
            continue
        with open(path, "r", encoding="utf-8") as f:
            products = json.load(f)
        print(f"📂 Loaded {len(products)} products from {path}")
        all_products.extend(products)
    print(f"📊 Total products to embed: {len(all_products)}")
    return all_products


def embed_and_upsert(
    products: list[dict],
    model: SentenceTransformer,
    client: QdrantClient,
    batch_size: int = 64,
    start_id: int = 1,
):
    """
    Embeds products in batches and upserts into Qdrant.
    Uses batch processing for efficiency — avoids OOM on large catalogs.
    """
    total = len(products)
    upserted = 0

    for batch_start in range(0, total, batch_size):
        batch = products[batch_start: batch_start + batch_size]
        batch_num = batch_start // batch_size + 1
        total_batches = (total + batch_size - 1) // batch_size

        print(f"\n🔄 Batch {batch_num}/{total_batches} ({len(batch)} products)...")

        # Build embedding texts
        texts = [build_embedding_text(p) for p in batch]

        # Generate embeddings
        t0 = time.time()
        vectors = model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            normalize_embeddings=True,  # L2 normalize for cosine similarity
        )
        elapsed = time.time() - t0
        print(f"   ⚡ Embedded in {elapsed:.2f}s")

        # Build Qdrant points
        points = []
        for i, (product, vector) in enumerate(zip(batch, vectors)):
            point_id = start_id + batch_start + i
            points.append(
                PointStruct(
                    id=point_id,
                    vector=vector.tolist(),
                    payload=build_payload(product),
                )
            )

        # Upsert to Qdrant
        client.upsert(collection_name=COLLECTION_NAME, points=points)
        upserted += len(points)
        print(f"   ✅ Upserted {upserted}/{total} points")

    return upserted


# ──────────────────────────────────────────────
# ENTRY POINT
# ──────────────────────────────────────────────

def main(recreate_collection: bool = False):
    print("=" * 55)
    print("   SKINCARE SEMANTIC SEARCH — EMBEDDER")
    print("=" * 55)

    # 1. Load model
    print(f"\n🧠 Loading model: {MODEL_NAME}")
    t0 = time.time()
    model = SentenceTransformer(MODEL_NAME)
    print(f"✅ Model loaded in {time.time() - t0:.1f}s")

    # 2. Connect to Qdrant
    client = get_qdrant_client()
    setup_collection(client, recreate=recreate_collection)

    # 3. Load products
    products = load_products(DATA_FILES)
    if not products:
        print("❌ No products found. Check DATA_FILES paths.")
        return

    # 4. Check what's already in the collection to avoid re-embedding
    collection_info = client.get_collection(COLLECTION_NAME)
    existing_count = collection_info.points_count
    print(f"\n📊 Existing vectors in collection: {existing_count}")

    if existing_count >= len(products) and not recreate_collection:
        print("✅ All products already embedded. Nothing to do.")
        print("   Run with recreate_collection=True to force re-embed.")
        return

    start_id = existing_count + 1

    # 5. Embed and upsert
    print(f"\n🚀 Starting embedding pipeline...")
    t0 = time.time()
    total_upserted = embed_and_upsert(
        products=products,
        model=model,
        client=client,
        batch_size=64,
        start_id=start_id,
    )
    total_time = time.time() - t0

    # 6. Final report
    print("\n" + "=" * 55)
    print(f"✅ DONE! {total_upserted} products embedded & stored.")
    print(f"⏱️  Total time: {total_time:.1f}s")
    print(f"📦 Collection: '{COLLECTION_NAME}' on {QDRANT_URL}")
    print(f"🔍 Ready for semantic search via FastAPI.")
    print("=" * 55)


if __name__ == "__main__":
    # Set recreate_collection=True to wipe and rebuild
    # (useful when you update the product data)
    main(recreate_collection=False)