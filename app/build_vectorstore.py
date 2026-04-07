import json
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS


INPUT_JSON = "data/general_docs.json"
VECTORSTORE_DIR = "data/faiss_general"


def load_docs(path: str) -> list[Document]:
    with open(path, "r", encoding="utf-8") as f:
        records = json.load(f)

    docs = []
    for r in records:
        docs.append(
            Document(
                page_content=r["page_content"],
                metadata=r["metadata"],
            )
        )
    return docs


def main():
    docs = load_docs(INPUT_JSON)
    print(f"Loaded docs: {len(docs)}")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=900,
        chunk_overlap=120,
        separators=["\n\n", "\n", ". ", "; ", " "],
    )

    chunks = splitter.split_documents(docs)
    print(f"Total chunks: {len(chunks)}")

    embeddings = HuggingFaceEmbeddings(
        model_name="BAAI/bge-small-en-v1.5",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True}
    )

    vectordb = FAISS.from_documents(chunks, embeddings)

    Path(VECTORSTORE_DIR).mkdir(parents=True, exist_ok=True)
    vectordb.save_local(VECTORSTORE_DIR)

    print(f"Saved vectorstore to: {VECTORSTORE_DIR}")


if __name__ == "__main__":
    main()