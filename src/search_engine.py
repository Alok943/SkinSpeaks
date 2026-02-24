from qdrant_client import QdrantClient
from qdrant_client.http import models
from sentence_transformers import SentenceTransformer

# Load our Hinglish-capable model [cite: 6]
model = SentenceTransformer('paraphrase-multilingual-mpnet-base-v2') 
client = QdrantClient(host="localhost", port=6333) # Assuming local for MVP

def semantic_search_with_filters(user_query, target_skin_type="dry", avoid_texture="sticky"):
    # 1. Convert query to vector
    query_vector = model.encode(user_query).tolist()
    
    # 2. Build the Exact Match Filters
    # This is the secret sauce that fixes the "chipchipa" hallucination
    query_filter = models.Filter(
        must=[
            models.FieldCondition(
                key="skin_type", 
                match=models.MatchValue(value=target_skin_type)
            )
        ],
        must_not=[
            models.FieldCondition(
                key="finish", 
                match=models.MatchValue(value=avoid_texture)
            )
        ]
    )

    # 3. Execute the hybrid search
    hits = client.search(
        collection_name="skinspeaks_catalog",
        query_vector=query_vector,
        query_filter=query_filter,
        limit=3
    )
    
    return hits

# Example usage for your 'Killer Demo':
# hits = semantic_search_with_filters("chipchipa na ho aur dry skin ke liye acha ho")