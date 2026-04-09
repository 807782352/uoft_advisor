import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'app')))

from build_vectorstore import load_vectorstore

def test_vectorstore():
    vectorstore = load_vectorstore("faiss_index")
    
    # Use MMR to get more diverse results and avoid returning very similar documents
    retriever = vectorstore.as_retriever(
        search_type="mmr",           # Maximum Marginal Relevance
        search_kwargs={
            "k": 3,                  # return top 3 results
            "fetch_k": 20,           # GET top 20 candidates from the vectorstore before re-ranking with MMR
        }
    )

    test_queries = [
        "What are the requirements for African Studies Specialist?",
        "I like math and programming, what program should I choose?",
        "What courses do I need for Rotman Commerce?",
    ]

    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"Query: {query}")
        print(f"{'='*60}")
        docs = retriever.invoke(query)
        for i, doc in enumerate(docs, 1):
            print(f"\n  Result {i}:")
            print(f"  Program:    {doc.metadata['program_name']}")
            print(f"  Type:       {doc.metadata['program_type']}")
            print(f"  Department: {doc.metadata['department']}")
            print(f"  Preview:    {doc.page_content[:150]}...")

test_vectorstore()