# test_connection.py
from config import llm, embeddings

def test_llm():
    print("Test LLM Connection...")
    response = llm.invoke("Say 'Hello, UofT!' and nothing else.")
    print(f"✅ LLM Response: {response.content}")

def test_embeddings():
    print("\nTest Embeddings Connection...")
    vector = embeddings.embed_query("University of Toronto")
    print(f"✅ Embedding Dimensions: {len(vector)}")
    print(f"✅ First 5 Values: {vector[:5]}")

if __name__ == "__main__":
    test_llm()
    test_embeddings()