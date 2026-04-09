# build_vectorstore.py
import json
from time import sleep
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS

import sys, os
sys.path.insert(0, os.path.dirname(__file__)) 

import json
from time import sleep
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from config import embeddings

# ============================================================
# Function 1: Load JSON -> LangChain Documents
# ============================================================

def load_documents(json_path: str) -> list[Document]:
    """
    Load knowledge base JSON and convert to LangChain Document format.
    Each record becomes one Document, with metadata for source attribution.
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    documents = []
    for item in data:
        doc = Document(
            page_content=item["full_text"],
            metadata={
                "program_name": item["program_name"],
                "program_code": item.get("program_code", ""),
                "program_type": item.get("program_type", ""),
                "department":   item.get("department", ""),
                "url":          item.get("url", ""),
            }
        )
        documents.append(doc)

    print(f"✅ Loaded {len(documents)} documents")
    return documents


# ============================================================
# Function 2: Split Documents into Chunks
# ============================================================

def split_documents(documents: list[Document]) -> list[Document]:
    """
    Split long documents into smaller chunks for better retrieval.
    chunk_size=800 keeps each chunk focused on one topic.
    chunk_overlap=100 ensures context isn't lost at boundaries.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100,
    )
    chunks = splitter.split_documents(documents)
    print(f"✅ Split into {len(chunks)} chunks")
    return chunks


# ============================================================
# Function 3: Build and Save FAISS Vectorstore
# ============================================================

# def build_vectorstore(chunks: list[Document], save_path: str = "faiss_index"):
#     """
#     Generate embeddings for all chunks and save to local FAISS index.
#     This only needs to be run once — afterwards load from disk.
#     """
#     print(f"⏳ Generating embeddings (this may take 1-2 minutes)...")
#     vectorstore = FAISS.from_documents(chunks, embeddings)
#     vectorstore.save_local(save_path)
#     print(f"✅ Vectorstore saved to {save_path}/")
#     return vectorstore

def build_vectorstore(chunks: list[Document], save_path: str = "faiss_index"):
    """
    Generate embeddings in batches to avoid overwhelming the server.
    """
    BATCH_SIZE = 50  # Instead of processing all at once, do it in smaller batches to reduce load and risk of timeouts.
    
    print(f"⏳ Generating embeddings in batches of {BATCH_SIZE}...")
    
    # First batch to initialize the vectorstore
    first_batch = chunks[:BATCH_SIZE]
    vectorstore = FAISS.from_documents(first_batch, embeddings)
    print(f"  ✅ Batch 1/{(len(chunks) // BATCH_SIZE) + 1} done")
    
    # Remaining batches to be merged one by one
    for i in range(BATCH_SIZE, len(chunks), BATCH_SIZE):
        batch = chunks[i : i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1
        total_batches = (len(chunks) // BATCH_SIZE) + 1
        
        try:
            vectorstore.add_documents(batch)
            print(f"  ✅ Batch {batch_num}/{total_batches} done")
            sleep(1)  # Wait a bit between batches
        except Exception as e:
            print(f"  ❌ Batch {batch_num} failed: {e}")
            print(f"     Saving progress so far...")
            vectorstore.save_local(save_path)
            raise
    
    vectorstore.save_local(save_path)
    print(f"✅ Vectorstore saved to {save_path}/")
    return vectorstore


# ============================================================
# Function 4: Load Vectorstore from Disk
# ============================================================

def load_vectorstore(save_path: str = "faiss_index"):
    """
    Load an existing FAISS index from disk.
    Use this instead of rebuild_vectorstore() after the first run.
    """
    from config import embeddings
    vectorstore = FAISS.load_local(
        save_path,
        embeddings,
        allow_dangerous_deserialization=True
    )
    print(f"✅ Vectorstore loaded from {save_path}/")
    return vectorstore


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    # Step 1: Load
    docs = load_documents("data/knowledge_base.json")

    # Step 2: Split
    chunks = split_documents(docs)

    # Test ：only use a subset of chunks for faster testing during development
    # test_chunks = chunks[:20]
    # print(f"⚠️  Testing with {len(test_chunks)} chunks only")
    # build_vectorstore(test_chunks)

    # Step 3: Build & Save
    build_vectorstore(chunks)