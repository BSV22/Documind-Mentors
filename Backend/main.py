from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import modular router/db configurations
from database import init_db
import auth
import chats
import documents

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

# Run schema initialization and migrations on startup
@app.on_event("startup")
def startup_event():
    init_db()


# Include Routers
app.include_router(auth.router)
app.include_router(chats.router)
app.include_router(documents.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)