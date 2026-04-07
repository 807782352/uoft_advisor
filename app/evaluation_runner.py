import csv
from pathlib import Path
from typing import List, Dict, Any

from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings

# 如果你的 qa_chain.py 在 app 文件夹里，就改成 from app.qa_chain import ...
from qa_chain import (
    VECTORSTORE_DIR,
    build_symbolic_indexes,
    build_llm,
    answer_query,
)

# =========================================================
# 1. Evaluation set
# =========================================================
EVAL_QUESTIONS = [
    # A. Course-level
    {
        "id": 1,
        "type": "course",
        "question": "What is the prerequisite for RSM338H1?",
        "expected_doc_type": "course",
        "expected_keywords": ["prerequisite", "rsm338h1"],
    },
    {
        "id": 2,
        "type": "course",
        "question": "What are the exclusions for RSM100H1?",
        "expected_doc_type": "course",
        "expected_keywords": ["exclusion", "rsm100h1"],
    },
    {
        "id": 3,
        "type": "course",
        "question": "What is the description of RSM219H1?",
        "expected_doc_type": "course",
        "expected_keywords": ["rsm219h1"],
    },
    {
        "id": 4,
        "type": "course",
        "question": "What is the credit value of ECO101H1?",
        "expected_doc_type": "course",
        "expected_keywords": ["eco101h1"],
    },
    {
        "id": 5,
        "type": "course",
        "question": "What topics are covered in RSM332H1?",
        "expected_doc_type": "course",
        "expected_keywords": ["rsm332h1"],
    },

    # B. Program requirements
    {
        "id": 6,
        "type": "program",
        "question": "What are the completion requirements for the Rotman Commerce specialist?",
        "expected_doc_type": "specialist",
        "expected_keywords": ["completion", "program"],
    },
    {
        "id": 7,
        "type": "program",
        "question": "What are the enrolment requirements for the Commerce major?",
        "expected_doc_type": "major",
        "expected_keywords": ["enrolment", "program"],
    },
    {
        "id": 8,
        "type": "program",
        "question": "What courses are required for the Management specialist program?",
        "expected_doc_type": "specialist",
        "expected_keywords": ["management", "program"],
    },
    {
        "id": 9,
        "type": "program",
        "question": "What is required to complete a Commerce minor?",
        "expected_doc_type": "minor",
        "expected_keywords": ["completion", "program"],
    },
    {
        "id": 10,
        "type": "program",
        "question": "Are there GPA requirements for the specialist program?",
        "expected_doc_type": "specialist",
        "expected_keywords": ["gpa"],
    },
    {
        "id": 11,
        "type": "program",
        "question": "What are the requirements for program completion in Rotman Commerce?",
        "expected_doc_type": None,  # 可能不止一个 doc_type，先不强绑
        "expected_keywords": ["program completion", "completion"],
    },

    # C. Section queries
    {
        "id": 12,
        "type": "section",
        "question": 'What does the "Note About Program Completion" say?',
        "expected_doc_type": "section",
        "expected_section_title": "Note About Program Completion",
        "expected_keywords": ["program completion"],
    },
    {
        "id": 13,
        "type": "section",
        "question": 'What information is provided in the "Additional Notes" section?',
        "expected_doc_type": "section",
        "expected_section_title": "Additional Notes",
        "expected_keywords": ["additional notes"],
    },
    {
        "id": 14,
        "type": "section",
        "question": "What is stated in the Introduction section of the Commerce program?",
        "expected_doc_type": "section",
        "expected_section_title": "Introduction",
        "expected_keywords": ["introduction"],
    },
    {
        "id": 15,
        "type": "section",
        "question": "Are there any restrictions mentioned in the notes section?",
        "expected_doc_type": "section",
        "expected_keywords": ["note", "notes", "restriction"],
    },

    # D. Cross / reasoning
    {
        "id": 16,
        "type": "reasoning",
        "question": "Can I take RSM338H1 without completing ECO220Y1?",
        "expected_doc_type": "course",
        "expected_keywords": ["rsm338h1", "prerequisite"],
    },
    {
        "id": 17,
        "type": "reasoning",
        "question": "Does RSM338H1 require programming knowledge?",
        "expected_doc_type": "course",
        "expected_keywords": ["rsm338h1", "csc108h1", "csc148h1"],
    },
    {
        "id": 18,
        "type": "reasoning",
        "question": "Is ECO101H1 required for the Commerce program?",
        "expected_doc_type": None,
        "expected_keywords": ["eco101h1", "commerce"],
    },

    # E. Negative / hallucination
    {
        "id": 19,
        "type": "negative",
        "question": "Does the Commerce program require an interview?",
        "expected_doc_type": None,
        "expected_keywords": ["interview"],
    },
    {
        "id": 20,
        "type": "negative",
        "question": "Is there a co-op option in the Rotman Commerce program?",
        "expected_doc_type": None,
        "expected_keywords": ["co-op", "coop"],
    },
]


# =========================================================
# 2. Load components
# =========================================================
def load_retrieval_components():
    embeddings = HuggingFaceEmbeddings(
        model_name="BAAI/bge-small-en-v1.5",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )

    vectordb = FAISS.load_local(
        VECTORSTORE_DIR,
        embeddings,
        allow_dangerous_deserialization=True,
    )

    indexes = build_symbolic_indexes(vectordb)
    llm = build_llm()

    return vectordb, indexes, llm


# =========================================================
# 3. Retrieval evaluation helpers
# =========================================================
def normalize_text(text: str) -> str:
    return (text or "").strip().lower()


def get_doc_preview(doc, max_len=300):
    content = (doc.page_content or "").replace("\n", " ")
    if len(content) > max_len:
        return content[:max_len] + "..."
    return content


def docs_to_string(docs):
    lines = []
    for i, d in enumerate(docs, start=1):
        meta = d.metadata
        lines.append(
            f"{i}. "
            f"[{meta.get('doc_type', 'Unknown')}] "
            f"{meta.get('degree', 'Unknown')} | "
            f"{meta.get('section_title', 'Unknown')} | "
            f"course={meta.get('course_code', '')} | "
            f"program={meta.get('program_code', '')}"
        )
    return " || ".join(lines)


def check_expected_doc_type(docs, expected_doc_type: str) -> bool:
    if not expected_doc_type:
        return False

    for d in docs:
        if normalize_text(d.metadata.get("doc_type", "")) == normalize_text(expected_doc_type):
            return True
    return False


def check_expected_section_title(docs, expected_section_title: str) -> bool:
    if not expected_section_title:
        return False

    for d in docs:
        if normalize_text(d.metadata.get("section_title", "")) == normalize_text(expected_section_title):
            return True
    return False


def check_expected_keywords_in_docs(docs, expected_keywords: List[str]) -> bool:
    if not expected_keywords:
        return False

    kws = [normalize_text(k) for k in expected_keywords if k]
    if not kws:
        return False

    for d in docs:
        haystack = " ".join([
            normalize_text(d.page_content),
            normalize_text(d.metadata.get("section_title", "")),
            normalize_text(d.metadata.get("degree", "")),
            normalize_text(d.metadata.get("doc_type", "")),
            normalize_text(d.metadata.get("course_code", "")),
            normalize_text(d.metadata.get("program_code", "")),
        ])
        if any(k in haystack for k in kws):
            return True
    return False


def evaluate_retrieval_signals(item: Dict[str, Any], docs) -> Dict[str, Any]:
    expected_doc_type = item.get("expected_doc_type")
    expected_section_title = item.get("expected_section_title")
    expected_keywords = item.get("expected_keywords", [])

    doc_type_hit = check_expected_doc_type(docs, expected_doc_type) if expected_doc_type else None
    section_hit = check_expected_section_title(docs, expected_section_title) if expected_section_title else None
    keyword_hit = check_expected_keywords_in_docs(docs, expected_keywords) if expected_keywords else None

    # 简单聚合逻辑
    signals = [x for x in [doc_type_hit, section_hit, keyword_hit] if x is not None]

    if not signals:
        overall = "unknown"
    elif all(signals):
        overall = "strong_hit"
    elif any(signals):
        overall = "partial_hit"
    else:
        overall = "miss"

    return {
        "retrieval_doc_type_hit": doc_type_hit,
        "retrieval_section_hit": section_hit,
        "retrieval_keyword_hit": keyword_hit,
        "retrieval_overall": overall,
    }


# =========================================================
# 4. Main evaluation runner
# =========================================================
def run_evaluation(output_csv="evaluation_results.csv", k=4):
    vectordb, indexes, llm = load_retrieval_components()
    output_path = Path(output_csv)

    with output_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "id",
                "type",
                "question",
                "answer",
                "retrieved_docs",
                "retrieval_doc_type_hit",
                "retrieval_section_hit",
                "retrieval_keyword_hit",
                "retrieval_overall",
                "label",   # correct / partial / wrong
                "notes",
            ],
        )
        writer.writeheader()

        for item in EVAL_QUESTIONS:
            qid = item["id"]
            qtype = item["type"]
            question = item["question"]

            print("\n" + "=" * 120)
            print(f"[Q{qid}] ({qtype}) {question}")

            try:
                answer, docs = answer_query(vectordb, indexes, llm, question, k=k)
                retrieved_docs_str = docs_to_string(docs)
                retrieval_eval = evaluate_retrieval_signals(item, docs)

                print("\nANSWER:\n")
                print(answer)

                print("\nRETRIEVED DOCS:\n")
                for i, d in enumerate(docs, start=1):
                    meta = d.metadata
                    print(
                        f"{i}. [{meta.get('doc_type', 'Unknown')}] "
                        f"{meta.get('degree', 'Unknown')} | "
                        f"{meta.get('section_title', 'Unknown')} | "
                        f"course={meta.get('course_code', '')} | "
                        f"program={meta.get('program_code', '')}"
                    )
                    print(f"   Preview: {get_doc_preview(d)}")

                print("\nAUTO RETRIEVAL CHECK:\n")
                print(f"doc_type_hit   = {retrieval_eval['retrieval_doc_type_hit']}")
                print(f"section_hit    = {retrieval_eval['retrieval_section_hit']}")
                print(f"keyword_hit    = {retrieval_eval['retrieval_keyword_hit']}")
                print(f"overall        = {retrieval_eval['retrieval_overall']}")

            except Exception as e:
                answer = f"ERROR: {str(e)}"
                docs = []
                retrieved_docs_str = ""
                retrieval_eval = {
                    "retrieval_doc_type_hit": None,
                    "retrieval_section_hit": None,
                    "retrieval_keyword_hit": None,
                    "retrieval_overall": "error",
                }

                print("\nERROR:\n")
                print(answer)

            print("\nManual answer label:")
            print("  c = correct")
            print("  p = partial")
            print("  w = wrong")

            raw_label = input("Your label: ").strip().lower()
            label_map = {
                "c": "correct",
                "p": "partial",
                "w": "wrong",
            }
            label = label_map.get(raw_label, "unlabeled")

            notes = input("Notes (optional): ").strip()

            writer.writerow(
                {
                    "id": qid,
                    "type": qtype,
                    "question": question,
                    "answer": answer,
                    "retrieved_docs": retrieved_docs_str,
                    "retrieval_doc_type_hit": retrieval_eval["retrieval_doc_type_hit"],
                    "retrieval_section_hit": retrieval_eval["retrieval_section_hit"],
                    "retrieval_keyword_hit": retrieval_eval["retrieval_keyword_hit"],
                    "retrieval_overall": retrieval_eval["retrieval_overall"],
                    "label": label,
                    "notes": notes,
                }
            )

    print("\nDone.")
    print(f"Saved results to: {output_path.resolve()}")


if __name__ == "__main__":
    run_evaluation()