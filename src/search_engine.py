from qdrant_client import QdrantClient
from qdrant_client.http import models
from sentence_transformers import SentenceTransformer
import os
from dotenv import load_dotenv

load_dotenv()

# Load our Hinglish-capable model
model = SentenceTransformer('paraphrase-multilingual-mpnet-base-v2')

# Connect to Qdrant Cloud securely
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

if QDRANT_API_KEY:
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
else:
    client = QdrantClient(url=QDRANT_URL or "http://localhost:6333")


def semantic_search(
    user_query: str,
    brand: str = None,
    category: str = None,
    max_price: float = None,
    top_k: int = 3,
):
    """
    Pure semantic search with optional filters on fields that
    actually exist in the payload: brand, category, price.

    For intent-based queries like "chipchipa na ho" or "dry skin ke liye",
    the multilingual model handles it — no skin_type/finish fields needed.

    Args:
        user_query  : Natural language or Hinglish query
        brand       : Optional — "Minimalist" or "The Derma Co"
        category    : Optional — e.g. "Skin Care", "Kit"
        max_price   : Optional — upper price limit in INR
        top_k       : Number of results to return (default 3)
    """

    # 1. Encode query into vector space
    query_vector = model.encode(user_query).tolist()

    # 2. Build filters only on fields that exist in the payload
    must_conditions = []

    if brand:
        must_conditions.append(
            models.FieldCondition(
                key="brand",
                match=models.MatchValue(value=brand)
            )
        )

    if category:
        must_conditions.append(
            models.FieldCondition(
                key="category",
                match=models.MatchValue(value=category)
            )
        )

    if max_price:
        must_conditions.append(
            models.FieldCondition(
                key="price",
                range=models.Range(lte=max_price)
            )
        )

    query_filter = models.Filter(must=must_conditions) if must_conditions else None

    # 3. Execute semantic search
    search_response = client.query_points(
        collection_name="skincare_products",
        query=query_vector,
        query_filter=query_filter,
        limit=top_k
    )

    return search_response.points


if __name__ == "__main__":
    print("Testing Semantic Engine...")
    print("=" * 50)

    # Test 1: Pure Hinglish intent — no filters
    # The model maps "chipchipa" and "dry skin" semantically
    print("\n🔍 Test 1: Hinglish query, no filters")
    results = semantic_search("chipchipa na ho aur dry skin ke liye acha ho")
    for hit in results:
        p = hit.payload
        print(f"  → {p['brand']} | {p['product_name']} | ₹{p['price']}")

    # Test 2: Same query but filtered to Minimalist brand only
    print("\n🔍 Test 2: Same query, Minimalist only")
    results = semantic_search(
        "chipchipa na ho aur dry skin ke liye acha ho",
        brand="Minimalist"
    )
    for hit in results:
        p = hit.payload
        print(f"  → {p['brand']} | {p['product_name']} | ₹{p['price']}")

    # Test 3: Budget filter
    print("\n🔍 Test 3: Dry skin moisturizer under ₹500")
    results = semantic_search(
        "moisturizer for dry skin",
        max_price=500.0
    )
    for hit in results:
        p = hit.payload
        print(f"  → {p['brand']} | {p['product_name']} | ₹{p['price']}")