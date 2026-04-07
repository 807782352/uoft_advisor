import re
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS


VECTORSTORE_DIR = "data/faiss_general"


# =========================================================
# 1. 基础提取函数
# =========================================================
def extract_course_code(query: str) -> Optional[str]:
    """
    提取课程代码，例如 RSM338H1, AMS100H1, BCB430Y1
    """
    m = re.search(r"\b[A-Z]{3,4}\d{3}[HY]\d?\b", query)
    return m.group(0) if m else None


def extract_program_code(query: str) -> Optional[str]:
    """
    提取项目代码，例如 ASSPE2038, ASMAJ0135, ERSPE2273
    """
    m = re.search(r"\b[A-Z]{2,}\d{4,}[A-Z]?\b", query)
    return m.group(0) if m else None


def extract_doc_type_hint(query: str) -> Optional[str]:
    """
    提取文档类型提示。
    这部分写死的是“通用 schema 类型”，不是具体专业名，所以是可扩展的。
    """
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
    """
    简单 token 化，用于 metadata/title 粗匹配
    """
    return re.findall(r"[a-z0-9&]+", text.lower())


# =========================================================
# 2. 从 docstore 自动建索引
# =========================================================
def build_symbolic_indexes(vectordb):
    """
    从向量库内部 docstore 自动建立符号索引
    """
    course_index: Dict[str, List] = defaultdict(list)
    program_index: Dict[str, List] = defaultdict(list)
    degree_index: Dict[str, List] = defaultdict(list)
    doc_type_index: Dict[str, List] = defaultdict(list)

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


# =========================================================
# 3. 动态 degree hint
# =========================================================
def extract_degree_hint(query: str, known_degrees: List[str]) -> Optional[str]:
    """
    不写死 degree 名，直接从数据库已有 degree 名里动态匹配。
    长名字优先，避免 'commerce' 抢走 'rotman commerce'
    """
    q = query.lower()

    for degree in known_degrees:
        if degree in q:
            return degree

    # 一个小补充：如果 query 提到 utm，并且库里 degree 叫 commerce，
    # 可以把它作为弱提示。这不是写死专业名，而是写死 campus 线索。
    if "utm" in q and "commerce" in known_degrees:
        return "commerce"

    return None


# =========================================================
# 4. exact match
# =========================================================
def exact_course_match(indexes, course_code: str) -> List:
    return indexes["course_index"].get(course_code, [])


def exact_program_match(indexes, program_code: str) -> List:
    return indexes["program_index"].get(program_code, [])


# =========================================================
# 5. metadata-aware candidate filtering
# =========================================================
def get_candidate_docs(indexes, doc_type_hint: Optional[str], degree_hint: Optional[str]) -> List:
    """
    先按 doc_type、degree 缩小候选集
    """
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
    """
    对候选文档做一个轻量 symbolic score
    主要看 section_title / degree / program_code / course_code 的 token overlap
    """
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


def metadata_ranked_search(indexes, query: str, doc_type_hint: Optional[str], degree_hint: Optional[str], k: int = 4) -> List:
    candidates = get_candidate_docs(indexes, doc_type_hint, degree_hint)

    print(f"[DEBUG] candidate docs after filtering: {len(candidates)}")

    scored: List[Tuple[int, object]] = []
    for doc in candidates:
        score = score_doc_against_query(doc, query)
        scored.append((score, doc))

    scored.sort(key=lambda x: x[0], reverse=True)

    preview = [(s, d.metadata.get("degree"), d.metadata.get("section_title")) for s, d in scored[:5]]
    print(f"[DEBUG] top symbolic scores: {preview}")

    # 去重：同 degree + same section_title 只保留一个
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


# =========================================================
# 6. 主 retrieval 流程
# =========================================================
def retrieve_docs(vectordb, indexes, query: str, k: int = 4):
    print(f"[DEBUG] query = {query}")

    # 1) exact course_code
    course_code = extract_course_code(query)
    print(f"[DEBUG] extracted course_code = {course_code}")
    if course_code:
        exact_docs = exact_course_match(indexes, course_code)
        print(f"[DEBUG] exact course matches found = {len(exact_docs)}")
        if exact_docs:
            print("[DEBUG] path used = exact_course_match")
            return exact_docs[:k]

    # 2) exact program_code
    program_code = extract_program_code(query)
    print(f"[DEBUG] extracted program_code = {program_code}")
    if program_code:
        exact_docs = exact_program_match(indexes, program_code)
        print(f"[DEBUG] exact program matches found = {len(exact_docs)}")
        if exact_docs:
            print("[DEBUG] path used = exact_program_match")
            return exact_docs[:k]

    # 3) dynamic metadata hints
    doc_type_hint = extract_doc_type_hint(query)
    degree_hint = extract_degree_hint(query, indexes["known_degrees"])

    print(f"[DEBUG] doc_type_hint = {doc_type_hint}")
    print(f"[DEBUG] degree_hint = {degree_hint}")

    filtered_docs = metadata_ranked_search(
        indexes=indexes,
        query=query,
        doc_type_hint=doc_type_hint,
        degree_hint=degree_hint,
        k=k,
    )
    print(f"[DEBUG] filtered_docs found = {len(filtered_docs)}")
    if filtered_docs:
        print("[DEBUG] path used = metadata_ranked_search")
        return filtered_docs

    # 4) semantic fallback
    print("[DEBUG] path used = similarity_search fallback")
    return vectordb.similarity_search(query, k=k)


# =========================================================
# 7. main
# =========================================================
def main():
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

    print(f"[DEBUG] total docs in docstore: {len(indexes['all_docs'])}")
    print(f"[DEBUG] known degrees: {indexes['known_degrees']}")

    queries = [
        "What are the enrolment requirements for Finance and Economics Specialist?",
        "What is the note about program completion for American Studies?",
        "What are the requirements for the Commerce Specialist at UTM?",
        "What is the prerequisite for RSM338H1?",
    ]

    for query in queries:
        print("\n" + "=" * 100)
        print("QUERY:", query)

        docs = retrieve_docs(vectordb, indexes, query, k=4)

        for i, d in enumerate(docs, start=1):
            print(f"\nResult {i}")
            print("Metadata:", d.metadata)
            print(d.page_content[:1000])


if __name__ == "__main__":
    main()