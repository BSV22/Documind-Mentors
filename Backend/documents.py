import os
import uuid
import shutil
import json
import psycopg2
import psycopg2.extras
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse

from database import get_db_connection
from auth import get_current_user
from schemas import ChatRequest

# RAG module imports
from rag.document import PDFLoader
from rag.chunker import TextChunker
from rag.embeddings import GeminiEmbedding
from rag.vector_store import VectorStore
from rag.retriever import Retriever
from rag.prompt import PromptBuilder
from rag.llm import LLM

router = APIRouter(prefix="/api", tags=["documents"])

# Initialize global RAG components
store = VectorStore()
embedding = GeminiEmbedding()
retriever = Retriever(embedding, store)

@router.get("/documents")
def get_documents(current_user: dict = Depends(get_current_user)):
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("SELECT id, filename, upload_time FROM documents WHERE user_id = %s ORDER BY upload_time DESC", (current_user["id"],))
                rows = cursor.fetchall()
                return [dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.post("/documents")
async def upload_document(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
        
    doc_id = str(uuid.uuid4())
    upload_dir = "data/documents"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{doc_id}.pdf")
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        loader = PDFLoader()
        document = loader.load(file_path)
        
        chunker = TextChunker()
        chunks = chunker.chunk(document)
        
        embedding_model = GeminiEmbedding()
        embeddings = []
        for chunk in chunks:
            vector = embedding_model.embed(chunk)
            embeddings.append(vector)
            
        # First insert document metadata row (satisfying FK constraints on child chunks)
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO documents (id, filename, user_id) VALUES (%s, %s, %s)",
                    (doc_id, file.filename, current_user["id"])
                )
            conn.commit()
            
        try:
            # Then bulk index chunks in PostgreSQL
            store.add_chunks_batch(chunks, embeddings, doc_id, current_user["id"])
        except Exception as e:
            # Clean up the document record if chunk indexing fails
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("DELETE FROM documents WHERE id = %s", (doc_id,))
                conn.commit()
            raise e
            
        return {"id": doc_id, "filename": file.filename}
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        print("Upload processing failed:", e)
        raise HTTPException(status_code=500, detail=f"Failed to process and index PDF: {str(e)}")

@router.delete("/documents/{doc_id}")
def delete_document(doc_id: str, current_user: dict = Depends(get_current_user)):
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("SELECT id, filename FROM documents WHERE id = %s AND user_id = %s", (doc_id, current_user["id"]))
                doc = cursor.fetchone()
                
            if not doc:
                raise HTTPException(status_code=404, detail="Document not found")
                
            # Remove from vector store
            store.delete_document(doc_id)
            
            file_path = f"data/documents/{doc_id}.pdf"
            if os.path.exists(file_path):
                os.remove(file_path)
                
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM documents WHERE id = %s", (doc_id,))
            conn.commit()
            
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")

def detect_intent(message: str) -> str:
    prompt = f"""
Analyze the following user question and categorize it into one of two options:
- 'DOCUMENT_INQUIRY': If the question is about specific content, data, facts, documents, or files that the user uploaded or refers to.
- 'GREETINGS_AND_GENERAL': If the question is a greeting (e.g. 'hello', 'hi'), conversational chit-chat, or a generic question that doesn't need external document references (e.g., 'what is RAG?', 'how are you?', 'tell me a joke').

Question: "{message}"

Respond with ONLY the exact string 'DOCUMENT_INQUIRY' or 'GREETINGS_AND_GENERAL'.
"""
    try:
        response = LLM().generate(prompt).strip()
        if "DOCUMENT_INQUIRY" in response:
            return "DOCUMENT_INQUIRY"
        return "GREETINGS_AND_GENERAL"
    except Exception as e:
        print("Intent detection failed, defaulting to DOCUMENT_INQUIRY:", e)
        return "DOCUMENT_INQUIRY"

async def event_generator(chat_id: str, message: str, user_id: int):
    # 1. Detect Intent to avoid unnecessary retrieval
    intent = detect_intent(message)
    print(f"Query Intent: {intent}")
    
    if intent == "DOCUMENT_INQUIRY":
        # Retrieve top-5 contexts using Hybrid Search (pgvector + FTS)
        contexts = retriever.retrieve(message, user_id=user_id, top_k=5)
        prompt = PromptBuilder().build(message, contexts)
    else:
        # Bypasses database retrieval completely
        prompt = f"""You are a helpful assistant. Provide a conversational or general answer to the user's message.
User Message: {message}
"""

    accumulated_response = ""
    try:
        llm = LLM()
        for chunk in llm.generate_stream(prompt):
            accumulated_response += chunk
            yield f"data: {json.dumps({'text': chunk})}\n\n"
    except Exception as e:
        print("LLM stream generation failed:", e)
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
        return

    # 4. Save messages to DB on completion
    user_msg_id = str(uuid.uuid4())
    bot_msg_id = str(uuid.uuid4())
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO messages (id, chat_id, from_user, text) VALUES (%s, %s, TRUE, %s)",
                    (user_msg_id, chat_id, message)
                )
                cur.execute(
                    "INSERT INTO messages (id, chat_id, from_user, text) VALUES (%s, %s, FALSE, %s)",
                    (bot_msg_id, chat_id, accumulated_response)
                )
            conn.commit()
    except Exception as db_e:
        print("Failed to save streamed chat messages to DB:", db_e)
        
    yield "data: [DONE]\n\n"

@router.post("/chat")
def chat_query(req: ChatRequest, current_user: dict = Depends(get_current_user)):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM chats WHERE id = %s AND user_id = %s", (req.chat_id, current_user["id"]))
                if not cursor.fetchone():
                    raise HTTPException(status_code=404, detail="Chat not found")
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
            
    return StreamingResponse(
        event_generator(req.chat_id, req.message, current_user["id"]),
        media_type="text/event-stream"
    )
