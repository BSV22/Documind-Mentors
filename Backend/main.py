from dotenv import load_dotenv
import os
import sqlite3
import uuid
import shutil
import datetime
from typing import List, Optional
from pydantic import BaseModel

# Load environment variables
load_dotenv()

from fastapi import FastAPI, File, UploadFile, Depends, HTTPException, status, Request, Response
from fastapi.middleware.cors import CORSMiddleware
import bcrypt
import jwt
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

# Configure files and database paths
DB_PATH = "data/db.sqlite"
CACHE_FILE = "data/vector_store.json"
JWT_SECRET = os.getenv("JWT_SECRET", "super-secret-key-change-in-production")
ALGORITHM = "HS256"

# Initialize global RAG components
store = VectorStore()

# Load vector store from cache or create from sample PDF if no cache exists
if os.path.exists(CACHE_FILE):
    print("Loading vector store from cache...")
    store.load(CACHE_FILE)
else:
    print("Creating vector store from default PDF...")
    sample_pdf = "data/sample.pdf"
    if os.path.exists(sample_pdf):
        try:
            loader = PDFLoader()
            document = loader.load(sample_pdf)
            chunker = TextChunker()
            chunks = chunker.chunk(document)
            embedding = GeminiEmbedding()
            for i, chunk in enumerate(chunks):
                print(f"Embedding chunk {i+1}/{len(chunks)}...")
                vector = embedding.embed(chunk)
                # Public chunks have no user_id or doc_id
                store.add(chunk, vector, {"filename": "sample.pdf"})
            store.save(CACHE_FILE)
        except Exception as e:
            print("Error indexing default sample PDF:", e)
    else:
        print("Default PDF sample.pdf not found in data/.")

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

# Initialize SQLite database
def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            password_hash TEXT,
            google_sub TEXT UNIQUE
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            filename TEXT,
            upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_id INTEGER,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents(user_id);")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            id TEXT PRIMARY KEY,
            title TEXT,
            user_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chats_user_id ON chats(user_id);")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            chat_id TEXT,
            from_user BOOLEAN,
            text TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(chat_id) REFERENCES chats(id)
        );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages(chat_id);")
        conn.commit()

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
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                (req.name, req.email, hashed)
            )
            conn.commit()
            user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Email already registered")
    
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
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, email, password_hash FROM users WHERE email = ?", (req.email,))
        user = cursor.fetchone()
        
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
        
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, email FROM users WHERE google_sub = ? OR email = ?", (sub, email))
        user = cursor.fetchone()
        
        if not user:
            cursor.execute(
                "INSERT INTO users (name, email, google_sub) VALUES (?, ?, ?)",
                (name, email, sub)
            )
            conn.commit()
            user_id = cursor.lastrowid
            user_name = name
        else:
            user_id = user["id"]
            user_name = user["name"]
            cursor.execute("UPDATE users SET google_sub = ? WHERE id = ?", (sub, user_id))
            conn.commit()
            
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
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT id, filename, upload_time FROM documents WHERE user_id = ? ORDER BY upload_time DESC", (current_user["id"],))
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

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
        for chunk in chunks:
            vector = embedding_model.embed(chunk)
            metadata = {
                "user_id": current_user["id"],
                "doc_id": doc_id,
                "filename": file.filename
            }
            store.add(chunk, vector, metadata)
            
        store.save(CACHE_FILE)
        
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO documents (id, filename, user_id) VALUES (?, ?, ?)",
                (doc_id, file.filename, current_user["id"])
            )
            conn.commit()
            
        return {"id": doc_id, "filename": file.filename}
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        print("Upload processing failed:", e)
        raise HTTPException(status_code=500, detail=f"Failed to process and index PDF: {str(e)}")

@app.delete("/api/documents/{doc_id}")
def delete_document(doc_id: str, current_user: dict = Depends(get_current_user)):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT id, filename FROM documents WHERE id = ? AND user_id = ?", (doc_id, current_user["id"]))
        doc = cursor.fetchone()
        
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    store.delete_document(doc_id)
    store.save(CACHE_FILE)
    
    file_path = f"data/documents/{doc_id}.pdf"
    if os.path.exists(file_path):
        os.remove(file_path)
        
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        conn.commit()
        
    return {"status": "success"}

# Chat & Conversation History Endpoints
@app.get("/api/chats")
def get_chats(current_user: dict = Depends(get_current_user)):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, created_at FROM chats WHERE user_id = ? ORDER BY created_at DESC", (current_user["id"],))
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

@app.post("/api/chats")
def create_chat(req: CreateChatRequest, current_user: dict = Depends(get_current_user)):
    chat_id = str(uuid.uuid4())
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO chats (id, title, user_id) VALUES (?, ?, ?)", (chat_id, req.title, current_user["id"]))
        conn.commit()
    return {"id": chat_id, "title": req.title}

@app.delete("/api/chats/{chat_id}")
def delete_chat(chat_id: str, current_user: dict = Depends(get_current_user)):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM chats WHERE id = ? AND user_id = ?", (chat_id, current_user["id"]))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Chat not found")
        cursor.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
        cursor.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
        conn.commit()
    return {"status": "success"}

@app.get("/api/chats/{chat_id}/messages")
def get_messages(chat_id: str, current_user: dict = Depends(get_current_user)):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM chats WHERE id = ? AND user_id = ?", (chat_id, current_user["id"]))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Chat not found")
            
        cursor.execute("SELECT id, from_user, text, timestamp FROM messages WHERE chat_id = ? ORDER BY timestamp ASC", (chat_id,))
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

@app.post("/api/chat")
def chat_query(req: ChatRequest, current_user: dict = Depends(get_current_user)):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM chats WHERE id = ? AND user_id = ?", (req.chat_id, current_user["id"]))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Chat not found")
            
    # Retrieve relevant contexts
    contexts = retriever.retrieve(req.message, user_id=current_user["id"])
    
    prompt = PromptBuilder().build(req.message, contexts)
    
    try:
        answer = LLM().generate(prompt)
    except Exception as e:
        print("LLM generation failed:", e)
        raise HTTPException(status_code=500, detail=f"LLM generation failed: {str(e)}")
        
    user_msg_id = str(uuid.uuid4())
    bot_msg_id = str(uuid.uuid4())
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO messages (id, chat_id, from_user, text) VALUES (?, ?, 1, ?)",
            (user_msg_id, req.chat_id, req.message)
        )
        cursor.execute(
            "INSERT INTO messages (id, chat_id, from_user, text) VALUES (?, ?, 0, ?)",
            (bot_msg_id, req.chat_id, answer)
        )
        conn.commit()
        
    return {"answer": answer}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)