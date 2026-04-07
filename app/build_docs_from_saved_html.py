import json
import re
from pathlib import Path
from typing import List, Optional

from bs4 import BeautifulSoup, Tag
from langchain_core.documents import Document


DATA_DIR = "data"
OUTPUT_JSON = "data/general_docs.json"


# -----------------------------
# utils
# -----------------------------
def clean_text(text: str) -> str:
    if not text:
        return ""

    replacements = {
        "\xa0": " ",
        "\u200b": "",
        "\ufeff": "",
        "\u00ad": "",
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
        "/​": "/",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"\s+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def get_text(elem: Optional[Tag]) -> str:
    if elem is None:
        return ""
    return clean_text(elem.get_text("\n", strip=True))


def safe_select_one(root: Tag, selector: str) -> Optional[Tag]:
    try:
        return root.select_one(selector)
    except Exception:
        return None


def infer_degree_name(soup: BeautifulSoup, fallback: str) -> str:
    h1 = safe_select_one(soup, "div.view-section-view header h1")
    if h1:
        return clean_text(h1.get_text(" ", strip=True))
    return fallback


def infer_source_type_from_path(path: str) -> str:
    lower = path.lower()
    if "utm" in lower or "commerce.html" == Path(path).name.lower():
        # not perfect, but harmless metadata
        return "utm_or_other"
    return "artsci_or_other"


def extract_code_from_title(title: str) -> Optional[str]:
    m = re.search(r"-\s*([A-Z]{2,}\d+[A-Z]?)\s*$", title)
    return m.group(1) if m else None


def extract_course_code_from_title(title: str) -> Optional[str]:
    m = re.match(r"^([A-Z]{3,4}\d{3}[HY]\d?)\s*-\s*.+", title)
    return m.group(1) if m else None


def infer_doc_type(title: str, default: str) -> str:
    if re.match(r"^[A-Z]{3,4}\d{3}[HY]\d?\s*-\s*.+", title):
        return "course"
    lowered = title.lower()
    if "specialist" in lowered:
        return "specialist"
    if "major" in lowered:
        return "major"
    if "minor" in lowered:
        return "minor"
    if "focus" in lowered:
        return "focus"
    if title.endswith("Programs"):
        return "programs_overview"
    if title.endswith("Courses"):
        return "courses_overview"
    return default


# -----------------------------
# general sections
# -----------------------------
def parse_general_sections(soup, source_file, degree_name):
    docs = []

    root = soup.select_one("div.view-section-view")
    if root is None:
        return docs

    body = root.select_one("div.view-content")
    if body is None:
        return docs

    # 关键：真正正文通常在这里
    field_content = body.select_one("div.views-field-body div.field-content")
    if field_content is None:
        field_content = body

    # 去掉 faculty list accordion
    for dl in field_content.select("dl.ckeditor-accordion"):
        dl.decompose()

    headings = field_content.find_all(["h2", "h3", "h4"])
    if not headings:
        return docs

    for i, heading in enumerate(headings):
        title = clean_text(heading.get_text(" ", strip=True))
        content_parts = []

        current = heading.find_next_sibling()
        while current:
            # 到下一个同级标题就停
            if getattr(current, "name", None) in ["h2", "h3", "h4"]:
                break
            txt = get_text(current)
            if txt:
                content_parts.append(txt)
            current = current.find_next_sibling()

        content = clean_text("\n\n".join(content_parts))

        if len(content) >= 40:
            docs.append(
                Document(
                    page_content=content,
                    metadata={
                        "degree": degree_name,
                        "doc_type": "section",
                        "section_title": title,
                        "source_file": source_file,
                        "source_kind": "general_section",
                    }
                )
            )

    return docs

# -----------------------------
# program rows
# -----------------------------
PROGRAM_FIELD_SELECTORS = {
    "overview": [
        "div.views-field-body",
        "div.field--name-body",
    ],
    "enrolment": [
        "div.views-field-field-enrolment-requirements",
        "h3.views-label-field-enrolment-requirements",
    ],
    "completion": [
        "div.views-field-field-completion-requirements",
        "h3.views-label-field-completion-req",
        "h3.views-label-field-completion-requirements",
    ],
}


def first_text_by_selectors(row: Tag, selectors: List[str]) -> str:
    for sel in selectors:
        elem = safe_select_one(row, sel)
        if elem is not None:
            txt = get_text(elem)
            if txt:
                return txt
    return ""


def parse_program_rows(soup: BeautifulSoup, source_file: str, degree_name: str) -> List[Document]:
    docs = []

    programs_root = safe_select_one(soup, "div.view-programs-view")
    if programs_root is None:
        return docs

    rows = programs_root.select("div.views-row")
    for row in rows:
        # Works for Artsci + UTM
        title_elem = (
            safe_select_one(row, "div.views-field-title h2")
            or safe_select_one(row, "h2.field-content")
            or safe_select_one(row, "h2")
        )
        if title_elem is None:
            continue

        title = clean_text(title_elem.get_text(" ", strip=True))
        if not title:
            continue

        overview = first_text_by_selectors(row, PROGRAM_FIELD_SELECTORS["overview"])
        enrolment = first_text_by_selectors(row, PROGRAM_FIELD_SELECTORS["enrolment"])
        completion = first_text_by_selectors(row, PROGRAM_FIELD_SELECTORS["completion"])

        # UTM fallback: the row is flatter, so extract text after title manually
        if not overview and not enrolment and not completion:
            raw = get_text(row)
            if raw:
                overview = raw

        parts = []
        if overview:
            parts.append("Overview:\n" + overview)
        if enrolment:
            parts.append("Enrolment Requirements:\n" + enrolment)
        if completion:
            parts.append("Completion Requirements:\n" + completion)

        content = clean_text("\n\n".join(parts))
        if len(content) < 40:
            continue

        docs.append(
            Document(
                page_content=content,
                metadata={
                    "degree": degree_name,
                    "doc_type": infer_doc_type(title, "program"),
                    "section_title": title,
                    "program_code": extract_code_from_title(title),
                    "source_file": source_file,
                    "source_kind": "program_row",
                },
            )
        )

    return docs


# -----------------------------
# course rows
# -----------------------------
COURSE_FIELD_MAP = {
    "Description": [
        "div.views-field-body",
    ],
    "Hours": [
        "span.views-field-field-hours",
    ],
    "Prerequisite": [
        "span.views-field-field-prerequisite",
    ],
    "Corequisite": [
        "span.views-field-field-corequisite",
    ],
    "Exclusion": [
        "span.views-field-field-exclusion",
    ],
    "Breadth Requirements": [
        "span.views-field-field-breadth-requirements",
    ],
    "Recommended Preparation": [
        "span.views-field-field-recommended",
    ],
    "Previous Course Number": [
        "span.views-field-field-previous-course-number",
    ],
}


def parse_course_rows(soup: BeautifulSoup, source_file: str, degree_name: str) -> List[Document]:
    docs = []

    courses_root = safe_select_one(soup, "div.view-courses-view")
    if courses_root is None:
        return docs

    rows = courses_root.select("div.views-row")
    for row in rows:
        title_elem = (
            safe_select_one(row, "div.views-field-title h3")
            or safe_select_one(row, "span.course-title h3")
            or safe_select_one(row, "h3")
        )
        if title_elem is None:
            continue

        title = clean_text(title_elem.get_text(" ", strip=True))
        if not title:
            continue

        parts = []
        for label, selectors in COURSE_FIELD_MAP.items():
            txt = first_text_by_selectors(row, selectors)
            if txt:
                parts.append(f"{label}:\n{txt}")

        content = clean_text("\n\n".join(parts))
        if len(content) < 20:
            continue

        docs.append(
            Document(
                page_content=content,
                metadata={
                    "degree": degree_name,
                    "doc_type": "course",
                    "section_title": title,
                    "course_code": extract_course_code_from_title(title),
                    "source_file": source_file,
                    "source_kind": "course_row",
                },
            )
        )

    return docs


# -----------------------------
# file -> docs
# -----------------------------
def html_file_to_documents(path: str) -> List[Document]:
    with open(path, "r", encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "lxml")
    degree_name = infer_degree_name(soup, Path(path).stem)

    docs = []
    docs.extend(parse_general_sections(soup, path, degree_name))
    docs.extend(parse_program_rows(soup, path, degree_name))
    docs.extend(parse_course_rows(soup, path, degree_name))
    return docs


def save_docs_to_json(docs: List[Document], output_path: str) -> None:
    records = [{"page_content": d.page_content, "metadata": d.metadata} for d in docs]
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def main():
    html_files = sorted(Path(DATA_DIR).glob("*.html"))

    all_docs = []
    for path in html_files:
        docs = html_file_to_documents(str(path))
        print(f"\n{path.name}: {len(docs)} docs")

        # quick breakdown
        counts = {}
        for d in docs:
            counts[d.metadata["doc_type"]] = counts.get(d.metadata["doc_type"], 0) + 1
        print("Breakdown:", counts)

        for d in docs[:5]:
            print(f"- [{d.metadata['doc_type']}] {d.metadata['section_title']}")

        all_docs.extend(docs)

    print(f"\nTotal docs: {len(all_docs)}")
    save_docs_to_json(all_docs, OUTPUT_JSON)
    print(f"Saved to {OUTPUT_JSON}")


if __name__ == "__main__":
    main()