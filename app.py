"""
FastAPI Backend for YouTube Q&A Bot
Provides REST API endpoints for the frontend to interact with the bot.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from dotenv import load_dotenv
import chromadb
from openai import OpenAI
from typing import List, Optional

load_dotenv()

app = FastAPI(title="YouTube Q&A Bot API")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "youtube_videos")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize ChromaDB
try:
    chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
    collection = chroma_client.get_collection(name=COLLECTION_NAME)
    print(f"✅ Connected to ChromaDB collection: {COLLECTION_NAME}")
except Exception as e:
    print(f"❌ Error loading ChromaDB: {e}")
    collection = None

# Initialize OpenAI
if OPENAI_API_KEY:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)
else:
    openai_client = None


# Pydantic models
class QuestionRequest(BaseModel):
    question: str
    n_results: Optional[int] = 5


class SourceInfo(BaseModel):
    video_id: str
    title: str
    url: str
    chunk_index: int
    relevance_score: float


class QuestionResponse(BaseModel):
    answer: str
    sources: List[SourceInfo]
    query: str


# API Endpoints
@app.get("/")
async def root():
    return {
        "message": "YouTube Q&A Bot API",
        "status": "running",
        "database_ready": collection is not None,
        "llm_ready": openai_client is not None,
    }


@app.get("/health")
async def health_check():
    """Check if all services are running."""
    return {
        "chromadb": collection is not None,
        "openai": openai_client is not None,
        "status": "healthy" if (collection and openai_client) else "degraded",
    }


@app.post("/ask", response_model=QuestionResponse)
async def ask_question(request: QuestionRequest):
    """
    Answer a question about the YouTube videos.
    """
    if not collection:
        raise HTTPException(status_code=500, detail="ChromaDB not initialized")

    if not openai_client:
        raise HTTPException(status_code=500, detail="OpenAI API not configured")

    # Retrieve relevant chunks
    results = collection.query(
        query_texts=[request.question], n_results=request.n_results
    )

    if not results["documents"][0]:
        raise HTTPException(status_code=404, detail="No relevant content found")

    # Format context
    context_parts = []
    sources = []

    for i, (doc, metadata, distance) in enumerate(
        zip(results["documents"][0], results["metadatas"][0], results["distances"][0])
    ):
        context_parts.append(f"""
[Video {i + 1}: {metadata["title"]}]
[URL: {metadata["url"]}]
{doc}
""")
        sources.append(
            SourceInfo(
                video_id=metadata["video_id"],
                title=metadata["title"],
                url=metadata["url"],
                chunk_index=metadata["chunk_index"],
                relevance_score=1 - distance,  # Convert distance to similarity
            )
        )

    context = "\n---\n".join(context_parts)

    # Generate answer with LLM
    system_prompt = """You are a helpful assistant that answers questions about YouTube videos.
You will be given relevant excerpts from video transcripts. Use this information to answer the user's question.
Always cite which video(s) you're referencing in your answer.
If the context doesn't contain enough information to answer the question, say so."""

    user_prompt = f"""Context from YouTube videos:
{context}

Question: {request.question}

Answer the question based on the context above. Be specific and cite the video titles."""

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=1000,
        )

        answer = response.choices[0].message.content

        return QuestionResponse(answer=answer, sources=sources, query=request.question)

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error generating answer: {str(e)}"
        )


@app.get("/stats")
async def get_stats():
    """Get statistics about the vector database."""
    if not collection:
        raise HTTPException(status_code=500, detail="ChromaDB not initialized")

    count = collection.count()

    # Get sample metadata to show available videos
    sample_results = collection.get(limit=100)

    # Extract unique videos
    videos = {}
    for metadata in sample_results["metadatas"]:
        video_id = metadata["video_id"]
        if video_id not in videos:
            videos[video_id] = {"title": metadata["title"], "url": metadata["url"]}

    return {
        "total_chunks": count,
        "total_videos": len(videos),
        "sample_videos": list(videos.values())[:10],
    }


if __name__ == "__main__":
    import uvicorn

    print("🚀 Starting FastAPI server...")
    print("📖 API docs available at: http://localhost:8000/docs")

    uvicorn.run(app, host="0.0.0.0", port=8000)
