# config.py
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

STUDENT_ID = "1003870554"

# LLM - finalproject endpoint
llm = ChatOpenAI(
    base_url="https://rsm-8430-finalproject.bjlkeng.io/v1",
    api_key=STUDENT_ID,
    model="qwen3-30b-a3b-fp8",
    temperature=0.3,
)

# Embeddings - A2 endpoint
embeddings = OpenAIEmbeddings(
    base_url="https://rsm-8430-a2.bjlkeng.io/v1",
    api_key=STUDENT_ID,
    model="text-embedding-3-small", 
    check_embedding_ctx_length=False, # Disable transform context to token
)