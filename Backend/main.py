from dotenv import load_dotenv
import os
import uuid
import shutil
import datetime
import json
from typing import List, Optional
from pydantic import BaseModel

# Load environment variables
load_dotenv()

from fastapi import FastAPI, File, UploadFile, Depends, HTTPException, status, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import bcrypt
import jwt
import psycopg2
import psycopg2.extras
from google.oauth2 import id_token
from google.auth.transport import requests

# RAG module imports
from rag.document import PDFLoader
from rag.chunker import TextChunker
from rag.embeddings import GeminiEmbedding
from rag.vector_store import VectorStore
from rag.retriever import Retriever
from rag.prompt import PromptBuilder
from rag.llm import LLM

# Configure paths and database URLs
DATABASE_URL = os.getenv("DATABASE_URL")
JWT_SECRET = os.getenv("JWT_SECRET", "super-secret-key-change-in-production")
ALGORITHM = "HS256"

# Initialize global RAG components
store = VectorStore()
embedding = GeminiEmbedding()
retriever = Retriever(embedding, store)

# Create FastAPI app
app = FastAPI(title="Documind RAG API")

# Add CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from contextlib import contextmanager
from psycopg2.pool import ThreadedConnectionPool

# Initialize ThreadedConnectionPool for fast connection reuse and to prevent leaks
db_pool = None

def init_db_pool():
    global db_pool
    if not DATABASE_URL:
        return
    try:
        db_pool = ThreadedConnectionPool(
            minconn=2,
            maxconn=15,
            dsn=DATABASE_URL
        )
    except Exception as e:
        print("Failed to initialize database connection pool:", e)

# Run pool initialization
init_db_pool()

@contextmanager
def get_db_connection():
    global db_pool
    if not db_pool:
        # Fallback to direct connection if pool is not initialized
        if not DATABASE_URL:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="DATABASE_URL environment variable is not configured. Please set it in Backend/.env"
            )
        conn = psycopg2.connect(DATABASE_URL)
        try:
            with conn.cursor() as cursor:
                cursor.execute("SET search_path TO documind, public;")
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    else:
        conn = db_pool.getconn()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SET search_path TO documind, public;")
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            db_pool.putconn(conn)

# Initialize PostgreSQL database
def init_db():
    if not DATABASE_URL:
        print("DATABASE_URL is not set. Skipping schema initialization...")
        return
    try:
        print("Initializing PostgreSQL database...")
        schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
        if not os.path.exists(schema_path):
            print(f"schema.sql not found at {schema_path}")
            return
            
        with open(schema_path, "r") as f:
            schema_sql = f.read()
            
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(schema_sql)
            conn.commit()
        print("Database schema initialized successfully.")
    except Exception as e:
        print("WARNING: Database schema initialization failed. Is the database URL/credentials correct?")
        print("Error details:", e)

# Run schema initialization
init_db()

# JWT Helpers
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.datetime.utcnow() + datetime.timedelta(days=7)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=ALGORITHM)
    return encoded_jwt

def decode_token(token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None

# Auth dependency
def get_current_user(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    
    # Verify user exists in the database
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM users WHERE id = %s", (payload.get("id"),))
                if not cursor.fetchone():
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="User session is invalid. Please sign in again.",
                    )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database user validation failed: {str(e)}"
        )
        
    return payload

# Pydantic Schemas
class SignupRequest(BaseModel):
    email: str
    password: str
    name: str

class SigninRequest(BaseModel):
    email: str
    password: str

class GoogleAuthRequest(BaseModel):
    token: str

class CreateChatRequest(BaseModel):
    title: str

class ChatRequest(BaseModel):
    chat_id: str
    message: str

# password utils
def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

# Endpoints
@app.post("/api/auth/signup")
def signup(req: SignupRequest, response: Response):
    hashed = hash_password(req.password)
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO users (name, email, password_hash) VALUES (%s, %s, %s) RETURNING id",
                    (req.name, req.email, hashed)
                )
                user_id = cursor.fetchone()[0]
            conn.commit()
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(status_code=400, detail="Email already registered")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    
    user_data = {"id": user_id, "email": req.email, "name": req.name}
    token = create_access_token(user_data)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=7 * 24 * 3600,
        samesite="lax",
        secure=False,
        path="/"
    )
    return {"user": user_data}

@app.post("/api/auth/signin")
def signin(req: SigninRequest, response: Response):
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("SELECT id, name, email, password_hash FROM users WHERE email = %s", (req.email,))
                user = cursor.fetchone()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
        
    if not user or not user["password_hash"]:
        raise HTTPException(status_code=401, detail="Invalid email or password")
        
    if not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
        
    user_data = {"id": user["id"], "email": user["email"], "name": user["name"]}
    token = create_access_token(user_data)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=7 * 24 * 3600,
        samesite="lax",
        secure=False,
        path="/"
    )
    return {"user": user_data}

@app.post("/api/auth/google")
def google_auth(req: GoogleAuthRequest, response: Response):
    try:
        client_id = os.getenv("GOOGLE_CLIENT_ID", "821514705181-4j2t6hghcn168s32hoinvuo8vf1kl84i.apps.googleusercontent.com")
        idinfo = id_token.verify_oauth2_token(req.token, requests.Request(), client_id)
        
        email = idinfo['email']
        name = idinfo.get('name', '')
        sub = idinfo['sub']
    except Exception as e:
        print("Google token verification failed:", e)
        raise HTTPException(status_code=401, detail=f"Google authentication failed: {str(e)}")
        
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("SELECT id, name, email FROM users WHERE google_sub = %s OR email = %s", (sub, email))
                user = cursor.fetchone()
                
                if not user:
                    cursor.execute(
                        "INSERT INTO users (name, email, google_sub) VALUES (%s, %s, %s) RETURNING id",
                        (name, email, sub)
                    )
                    user_id = cursor.fetchone()[0]
                    user_name = name
                    conn.commit()
                else:
                    user_id = user["id"]
                    user_name = user["name"]
                    cursor.execute("UPDATE users SET google_sub = %s WHERE id = %s", (sub, user_id))
                    conn.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
            
    user_data = {"id": user_id, "email": email, "name": user_name}
    token = create_access_token(user_data)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=7 * 24 * 3600,
        samesite="lax",
        secure=False,
        path="/"
    )
    return {"user": user_data}

@app.get("/api/auth/me")
def get_me(current_user: dict = Depends(get_current_user)):
    return {"user": current_user}

@app.post("/api/auth/signout")
def signout(response: Response):
    response.delete_cookie(key="access_token", path="/")
    return {"status": "success"}

# Document Management Endpoints
@app.get("/api/documents")
def get_documents(current_user: dict = Depends(get_current_user)):
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("SELECT id, filename, upload_time FROM documents WHERE user_id = %s ORDER BY upload_time DESC", (current_user["id"],))
                rows = cursor.fetchall()
                return [dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.post("/api/documents")
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

@app.delete("/api/documents/{doc_id}")
def delete_document(doc_id: str, current_user: dict = Depends(get_current_user)):
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("SELECT id, filename FROM documents WHERE id = %s AND user_id = %s", (doc_id, current_user["id"]))
                doc = cursor.fetchone()
                
            if not doc:
                raise HTTPException(status_code=404, detail="Document not found")
                
            # Remove from vector store (cascading deletes in DB schema will handle the database row cleanup if configured, but let's do it explicitly)
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

# Chat & Conversation History Endpoints
@app.get("/api/chats")
def get_chats(current_user: dict = Depends(get_current_user)):
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("SELECT id, title, created_at FROM chats WHERE user_id = %s ORDER BY created_at DESC", (current_user["id"],))
                rows = cursor.fetchall()
                return [dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.post("/api/chats")
def create_chat(req: CreateChatRequest, current_user: dict = Depends(get_current_user)):
    chat_id = str(uuid.uuid4())
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("INSERT INTO chats (id, title, user_id) VALUES (%s, %s, %s)", (chat_id, req.title, current_user["id"]))
            conn.commit()
        return {"id": chat_id, "title": req.title}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.delete("/api/chats/{chat_id}")
def delete_chat(chat_id: str, current_user: dict = Depends(get_current_user)):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM chats WHERE id = %s AND user_id = %s", (chat_id, current_user["id"]))
                if not cursor.fetchone():
                    raise HTTPException(status_code=404, detail="Chat not found")
                # Cascade delete deletes messages from the database
                cursor.execute("DELETE FROM chats WHERE id = %s", (chat_id,))
            conn.commit()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/chats/{chat_id}/messages")
def get_messages(chat_id: str, current_user: dict = Depends(get_current_user)):
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("SELECT id FROM chats WHERE id = %s AND user_id = %s", (chat_id, current_user["id"]))
                if not cursor.fetchone():
                    raise HTTPException(status_code=404, detail="Chat not found")
                    
                cursor.execute("SELECT id, from_user, text, timestamp FROM messages WHERE chat_id = %s ORDER BY timestamp ASC", (chat_id,))
                rows = cursor.fetchall()
                return [dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

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

@app.post("/api/chat")
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)