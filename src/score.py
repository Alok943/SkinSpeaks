from qdrant_client import QdrantClient
from qdrant_client.http import models
from sentence_transformers import SentenceTransformer
import os
from dotenv import load_dotenv

load_dotenv()

model = SentenceTransformer('paraphrase-multilingual-mpnet-base-v2')

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

if QDRANT_API_KEY:
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
else:
    client = QdrantClient(url=QDRANT_URL or "http://localhost:6333")


def inspect_scores(user_query: str, top_k: int = 10):
    query_vector = model.encode(user_query).tolist()

    search_response = client.query_points(
        collection_name="skincare_products",
        query=query_vector,
        limit=top_k,
        with_payload=True,
    )

    print(f"\n🔍 Query: '{user_query}'")
    print(f"{'SCORE':<8} {'BRAND':<20} PRODUCT")
    print("-" * 70)
    for hit in search_response.points:
        p = hit.payload
        print(f"{hit.score:<8.4f} {p['brand']:<20} {p['product_name'][:45]}")


if __name__ == "__main__":
    inspect_scores("chipchipa na ho aur dry skin ke liye acha ho")
    inspect_scores("moisturizer for dry skin")
    inspect_scores("oily skin ke liye face wash")