# rag.py
import sys, os
sys.path.insert(0, os.path.dirname(__file__))  # 指向 app/

from langchain_core.prompts import ChatPromptTemplate
from build_vectorstore import load_vectorstore
from config import llm

# ============================================================
# Load Retriever
# ============================================================

vectorstore = load_vectorstore("faiss_index")

retriever = vectorstore.as_retriever(
    search_type="mmr",
    search_kwargs={
        "k": 4,       # Return 4 results
        "fetch_k": 20 # Candidate pool
    }
)

# ============================================================
# RAG Prompt
# ============================================================

RAG_PROMPT = ChatPromptTemplate.from_template("""
You are a helpful academic advisor at the University of Toronto.
Answer the student's question using ONLY the information provided below.
Always cite which program or department your answer comes from.
If the information is not in the context, say "I don't have that information in my knowledge base."

Context:
{context}

Student Question: {question}

Answer:
""")

# ============================================================
# Function 1: Retrieve relevant documents
# ============================================================

def retrieve(query: str) -> list:
    """
    Retrieve the most relevant program documents for a query.
    Returns a list of LangChain Documents with metadata.
    """
    docs = retriever.invoke(query)
    return docs

# ============================================================
# Function 2: Format docs into context string
# ============================================================

def format_docs(docs: list) -> str:
    """
    Format retrieved documents into a single context string for the LLM.
    Includes source attribution in the context.
    """
    formatted = []
    for i, doc in enumerate(docs, 1):
        source = f"[Source {i}: {doc.metadata['program_name']} - {doc.metadata['department']}]"
        formatted.append(f"{source}\n{doc.page_content}")
    return "\n\n".join(formatted)

# ============================================================
# Function 3: Full RAG pipeline
# ============================================================

def rag_answer(question: str) -> dict:
    """
    Full RAG pipeline: retrieve -> format -> generate answer.
    
    Returns:
        {
            "answer": "...",
            "sources": [{"program_name": ..., "department": ..., "url": ...}]
        }
    """
    # Step 1: Retrieve
    docs = retrieve(question)

    # Step 2: Format context
    context = format_docs(docs)

    # Step 3: Generate answer
    chain = RAG_PROMPT | llm
    response = chain.invoke({
        "context": context,
        "question": question
    })

    # Step 4: Extract sources for attribution
    sources = [
        {
            "program_name": doc.metadata["program_name"],
            "department":   doc.metadata["department"],
            "url":          doc.metadata["url"],
        }
        for doc in docs
    ]

    return {
        "answer": response.content,
        "sources": sources
    }