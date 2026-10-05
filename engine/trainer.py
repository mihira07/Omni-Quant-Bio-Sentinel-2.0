import os
import glob
from pathlib import Path
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings.sentence_transformer import SentenceTransformerEmbeddings
from langchain_community.vectorstores import Chroma

# --- CONFIGURATION ---
KNOWLEDGE_BASE_DIR = os.path.join(os.path.dirname(__file__), "knowledge")
BASE_DIR = Path(__file__).resolve().parent.parent
DB_DIR = BASE_DIR / "chroma_db"

def ingest_materials():
    print(f"[SYSTEM] Scanning {KNOWLEDGE_BASE_DIR} for training materials...")
    # Keep the portable project-local store available before Chroma opens it.
    DB_DIR.mkdir(parents=True, exist_ok=True)
    
    documents = []
    
    # 1. Load PDF Files
    pdf_files = glob.glob(os.path.join(KNOWLEDGE_BASE_DIR, "*.pdf"))
    for pdf in pdf_files:
        print(f"[READING] {os.path.basename(pdf)}...")
        loader = PyPDFLoader(pdf)
        documents.extend(loader.load())

    # 2. Load TXT Files
    txt_files = glob.glob(os.path.join(KNOWLEDGE_BASE_DIR, "*.txt"))
    for txt in txt_files:
        print(f"[READING] {os.path.basename(txt)}...")
        loader = TextLoader(txt, encoding='utf-8')
        documents.extend(loader.load())

    if not documents:
        print("[WARNING] No materials found. Drop PDFs or TXTs into engine/knowledge/.")
        return

    # 3. Chop documents into tactical chunks
    print("[PROCESSING] Slicing materials into data vectors...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, 
        chunk_overlap=200
    )
    chunks = text_splitter.split_documents(documents)

    # 4. Initialize Local Embedding Model (Runs entirely on your machine)
    print("[EMBEDDING] Activating Sentence Transformers...")
    embedding_model = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")

    # 5. Store in ChromaDB
    print(f"[STORING] Writing to Vector Vault at {DB_DIR}...")
    vector_db = Chroma.from_documents(
        documents=chunks, 
        embedding=embedding_model, 
        persist_directory=str(DB_DIR)
    )
    
    # Force save to disk (Required for some ChromaDB versions)
    vector_db.persist()
    print("[SUCCESS] Training Complete. OmniQuant Knowledge Vault is updated.")

if __name__ == "__main__":
    ingest_materials()
