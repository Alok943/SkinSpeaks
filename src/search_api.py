from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, Range
import time
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="SkinSpeaks Semantic Search API")

# ──────────────────────────────────────────────
# GLOBAL STATE (Loaded once to minimize inference latency)
# ──────────────────────────────────────────────
MODEL_NAME = "paraphrase-multilingual-mpnet-base-v2"
COLLECTION_NAME = "skincare_products"

print(f"🧠 Loading model {MODEL_NAME} into memory...")
model = SentenceTransformer(MODEL_NAME)

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", None)

if QDRANT_API_KEY:
    qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
else:
    qdrant = QdrantClient(url=QDRANT_URL)

# ──────────────────────────────────────────────
# API CONTRACTS (Pydantic Models)
# ──────────────────────────────────────────────
class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    brand: Optional[str] = None
    max_price: Optional[float] = None
    category: Optional[str] = None

# ──────────────────────────────────────────────
# POST /search ENDPOINT
# ──────────────────────────────────────────────
@app.post("/search")
async def search_products(req: SearchRequest):
    start_time = time.time()
    
    try:
        # 1. Map Hinglish/English query into the Latent Space
        # Because we use a multilingual model, Hinglish maps beautifully here.
        query_vector = model.encode(req.query).tolist()
        
        # 2. Build Metadata Filters (The "Where" clause for Vector DBs)
        must_conditions = []
        if req.brand:
            must_conditions.append(FieldCondition(key="brand", match=MatchValue(value=req.brand)))
        if req.category:
            must_conditions.append(FieldCondition(key="category", match=MatchValue(value=req.category)))
        if req.max_price:
            must_conditions.append(FieldCondition(key="price", range=Range(lte=req.max_price)))
            
        query_filter = Filter(must=must_conditions) if must_conditions else None

        # 3. Calculate Cosine Similarity & Fetch from Qdrant
        search_response = qdrant.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            query_filter=query_filter,
            limit=req.top_k
        )
        
        # 4. Format Output
        results = [
                {**hit.payload, "score": round(hit.score, 4)}
                for hit in search_response.points
            ]
        
        # Calculate inference latency in milliseconds
        inference_latency = (time.time() - start_time) * 1000
        
        return {
            "latency_ms": round(inference_latency, 2),
            "results_count": len(results),
            "results": results
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))