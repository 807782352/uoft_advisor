import re
from typing import List, Optional
from collections import defaultdict

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_openai import ChatOpenAI


VECTORSTORE_DIR = "data/faiss_general"


# =========================================================
# 1. Query parsing helpers
# =========================================================
def extract_course_code(query: str) -> Optional[str]:
    m = re.search(r"\b[A-Z]{3,4}\d{3}[HY]\d?\b", query)
    return m.group(0) if m else None


def extract_program_code(query: str) -> Optional[str]:
    m = re.search(r"\b[A-Z]{2,}\d{4,}[A-Z]?\b", query)
    return m.group(0) if m else None


def extract_doc_type_hint(query: str) -> Optional[str]:
    q = query.lower()

    if extract_course_code(query):
        return "course"

    if "note about program completion" in q or "introduction" in q or "additional notes" in q:
        return "section"

    for t in ["specialist", "major", "minor", "focus"]:
        if t in q:
            return t

    return None


def tokenize_for_match(text: str) -> List[str]:
    return re.findall(r"[a-z0-9&]+", text.lower())


# =========================================================
# 2. Build symbolic indexes from docstore
# =========================================================
def build_symbolic_indexes(vectordb):
    course_index = defaultdict(list)
    program_index = defaultdict(list)
    degree_index = defaultdict(list)
    doc_type_index = defaultdict(list)

    docs = list(vectordb.docstore._dict.values())

    for doc in docs:
        meta = doc.metadata

        course_code = meta.get("course_code")
        if course_code:
            course_index[course_code].append(doc)

        program_code = meta.get("program_code")
        if program_code:
            program_index[program_code].append(doc)

        degree = meta.get("degree")
        if degree:
            degree_index[degree.lower()].append(doc)

        doc_type = meta.get("doc_type")
        if doc_type:
            doc_type_index[doc_type].append(doc)

    return {
        "all_docs": docs,
        "course_index": course_index,
        "program_index": program_index,
        "degree_index": degree_index,
        "doc_type_index": doc_type_index,
        "known_degrees": sorted(degree_index.keys(), key=len, reverse=True),
    }


def extract_degree_hint(query: str, known_degrees: List[str]) -> Optional[str]:
    q = query.lower()

    for degree in known_degrees:
        if degree in q:
            return degree

    if "utm" in q and "commerce" in known_degrees:
        return "commerce"

    return None


# =========================================================
# 3. Retrieval logic
# =========================================================
def exact_course_match(indexes, course_code: str):
    return indexes["course_index"].get(course_code, [])


def exact_program_match(indexes, program_code: str):
    return indexes["program_index"].get(program_code, [])


def get_candidate_docs(indexes, doc_type_hint: Optional[str], degree_hint: Optional[str]):
    if doc_type_hint:
        candidates = list(indexes["doc_type_index"].get(doc_type_hint, []))
    else:
        candidates = list(indexes["all_docs"])

    if degree_hint:
        candidates = [
            d for d in candidates
            if d.metadata.get("degree", "").lower() == degree_hint
        ]

    return candidates


def score_doc_against_query(doc, query: str) -> int:
    q_tokens = set(tokenize_for_match(query))

    title = doc.metadata.get("section_title", "")
    degree = doc.metadata.get("degree", "")
    doc_type = doc.metadata.get("doc_type", "")
    course_code = doc.metadata.get("course_code", "") or ""
    program_code = doc.metadata.get("program_code", "") or ""

    title_tokens = set(tokenize_for_match(title))
    degree_tokens = set(tokenize_for_match(degree))
    type_tokens = set(tokenize_for_match(doc_type))
    code_tokens = set(tokenize_for_match(course_code + " " + program_code))

    score = 0
    score += 3 * len(q_tokens & title_tokens)
    score += 2 * len(q_tokens & degree_tokens)
    score += 1 * len(q_tokens & type_tokens)
    score += 4 * len(q_tokens & code_tokens)

    return score


def metadata_ranked_search(indexes, query: str, doc_type_hint: Optional[str], degree_hint: Optional[str], k: int = 4):
    candidates = get_candidate_docs(indexes, doc_type_hint, degree_hint)

    scored = []
    for doc in candidates:
        score = score_doc_against_query(doc, query)
        scored.append((score, doc))

    scored.sort(key=lambda x: x[0], reverse=True)

    # 去重：同 degree + section_title 只保留一个
    results = []
    seen = set()

    for score, doc in scored:
        if score <= 0:
            continue

        key = (
            doc.metadata.get("degree"),
            doc.metadata.get("section_title"),
        )
        if key in seen:
            continue

        seen.add(key)
        results.append(doc)

        if len(results) >= k:
            break

    return results


def retrieve_docs(vectordb, indexes, query: str, k: int = 4):
    # 1. exact course code
    course_code = extract_course_code(query)
    if course_code:
        exact_docs = exact_course_match(indexes, course_code)
        if exact_docs:
            return exact_docs[:k]

    # 2. exact program code
    program_code = extract_program_code(query)
    if program_code:
        exact_docs = exact_program_match(indexes, program_code)
        if exact_docs:
            return exact_docs[:k]

    # 3. metadata-aware retrieval
    doc_type_hint = extract_doc_type_hint(query)
    degree_hint = extract_degree_hint(query, indexes["known_degrees"])

    filtered_docs = metadata_ranked_search(
        indexes=indexes,
        query=query,
        doc_type_hint=doc_type_hint,
        degree_hint=degree_hint,
        k=k,
    )
    if filtered_docs:
        return filtered_docs

    # 4. fallback semantic search
    return vectordb.similarity_search(query, k=k)


# =========================================================
# 4. Prompt / context formatting
# =========================================================
def format_docs_for_context(docs) -> str:
    parts = []

    for i, doc in enumerate(docs, start=1):
        meta = doc.metadata
        parts.append(
            f"[Document {i}]\n"
            f"Degree: {meta.get('degree', 'Unknown')}\n"
            f"Doc Type: {meta.get('doc_type', 'Unknown')}\n"
            f"Title: {meta.get('section_title', 'Unknown')}\n"
            f"Content:\n{doc.page_content}\n"
        )

    return "\n\n".join(parts)


def build_prompt(query: str, context: str) -> str:
    return f"""
You are a UofT academic advising assistant.

Answer the user's question using ONLY the provided context.
Rules:
1. Do not make up facts.
2. If the answer is not in the context, say you could not find it in the current knowledge base.
3. Be clear and concise.
4. If relevant, mention the degree/program/course title you used.
5. For requirement questions, separate enrolment requirements and completion requirements if the context supports it.

User Question:
{query}

Context:
{context}

Answer:
""".strip()


# =========================================================
# 5. QA pipeline
# =========================================================
def build_llm():
    """
    用课程给的 final project endpoint
    """
    llm = ChatOpenAI(
        model="qwen3-30b-a3b-fp8",
        openai_api_base="https://rsm-8430-finalproject.bjlkeng.io",
        openai_api_key="1003870554",
        temperature=0,
    )
    return llm


def answer_query(vectordb, indexes, llm, query: str, k: int = 4):
    docs = retrieve_docs(vectordb, indexes, query, k=k)
    context = format_docs_for_context(docs)
    prompt = build_prompt(query, context)

    response = llm.invoke(prompt)
    answer = response.content if hasattr(response, "content") else str(response)

    return answer, docs


# =========================================================
# 6. Main
# =========================================================
def main():
    # local embedding model for retrieval
    embeddings = HuggingFaceEmbeddings(
        model_name="BAAI/bge-small-en-v1.5",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True}
    )

    vectordb = FAISS.load_local(
        VECTORSTORE_DIR,
        embeddings,
        allow_dangerous_deserialization=True
    )

    indexes = build_symbolic_indexes(vectordb)
    llm = build_llm()

    print("UofT Academic QA (type 'quit' to stop)\n")

    while True:
        query = input("Question: ").strip()
        if query.lower() == "quit":
            break

        answer, docs = answer_query(vectordb, indexes, llm, query, k=4)

        print("\n" + "=" * 100)
        print("ANSWER:\n")
        print(answer)

        print("\n" + "-" * 100)
        print("RETRIEVED DOCUMENTS:\n")
        for i, d in enumerate(docs, start=1):
            print(f"{i}. [{d.metadata.get('doc_type')}] {d.metadata.get('degree')} | {d.metadata.get('section_title')}")
        print("=" * 100 + "\n")


if __name__ == "__main__":
    main()