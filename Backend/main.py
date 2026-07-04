from dotenv import load_dotenv

load_dotenv()

from rag.document import PDFLoader
from rag.chunker import TextChunker
from rag.embeddings import GeminiEmbedding
from rag.vector_store import VectorStore
from rag.retriever import Retriever
from rag.prompt import PromptBuilder
from rag.llm import LLM
import os

store = VectorStore()
CACHE_FILE = "data/vector_store.json"

# Try to load from cache
if os.path.exists(CACHE_FILE):
    print("Loading vector store from cache...")
    store.load(CACHE_FILE)
else:
    print("Creating vector store from PDF...")
    
    loader = PDFLoader()
    document = loader.load("data/sample.pdf")

    chunker = TextChunker()
    chunks = chunker.chunk(document)

    embedding = GeminiEmbedding()

    for i, chunk in enumerate(chunks):
        print(f"Embedding chunk {i+1}/{len(chunks)}...")
        vector = embedding.embed(chunk)
        store.add(chunk, vector)
    
    # Save to cache for future use
    store.save(CACHE_FILE)

embedding = GeminiEmbedding()

retriever = Retriever(
    embedding,
    store
)

query = input("ASK : ")
contexts = retriever.retrieve(
    query
)

prompt = PromptBuilder().build(
    query,
    contexts
)

answer = LLM().generate(prompt)

print(answer)