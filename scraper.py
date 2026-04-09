"""
UofT Academic Calendar Scraper
================================
Scrapes all undergraduate program pages from artsci.calendar.utoronto.ca
Uses the printer-friendly version for the most complete content.

Usage:
  python scraper.py            # Scrape all programs
  python scraper.py --test     # Scrape first 5 only (for testing)
  python scraper.py --local data/html_files  # Parse local HTML files

Output: data/knowledge_base.json
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import os
import sys

# ============================================================
# Configuration
# ============================================================

BASE_URL = "https://artsci.calendar.utoronto.ca"
LISTING_URL = f"{BASE_URL}/listing-program-subject-areas"

# Printer-friendly URL template
# slug = the part after /section/ e.g. "African-Studies"
PRINT_URL_TEMPLATE = (
    f"{BASE_URL}/print/view/pdf/section_view/print_page/debug?view_args[]={{slug}}"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

OUTPUT_DIR = "data"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "knowledge_base.json")
CRAWL_DELAY = 1.5  # seconds between requests (polite crawling)


# ============================================================
# Function 1: Get all program slugs from the listing page
# ============================================================

def get_all_program_slugs(session: requests.Session) -> list[dict]:
    """
    Fetch all program slugs from the UofT listing page.

    Returns:
        [{"name": "African Studies", "slug": "African-Studies", "print_url": "..."}, ...]
    """
    print(f"📋 Fetching program list from: {LISTING_URL}")

    resp = session.get(LISTING_URL, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    programs = []
    seen_slugs = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        name = a.get_text(strip=True)

        # Only keep /section/ links
        if not href.startswith("/section/"):
            continue

        # Extract slug, strip any anchor (e.g. #programs)
        slug = href.replace("/section/", "").split("#")[0].strip()

        if not slug or not name or slug in seen_slugs:
            continue

        seen_slugs.add(slug)
        programs.append({
            "name": name,
            "slug": slug,
            "print_url": PRINT_URL_TEMPLATE.format(slug=slug),
        })

    print(f"✅ Found {len(programs)} program pages")
    return programs


# ============================================================
# Function 2: Parse a single printer-friendly page
# ============================================================

def parse_program_page(soup: BeautifulSoup, section_url: str) -> list[dict]:
    """
    Parse a printer-friendly program page and extract all sub-programs
    (Specialist / Major / Minor / Certificate / Focus).

    Returns:
        A list of dicts, one per sub-program found on the page.
    """
    records = []

    # Department name from h1 (exclude the site navigation h1)
    department_name = "Unknown"
    for h1 in soup.find_all("h1"):
        classes = h1.get("class") or []
        if "site-name" not in classes:
            department_name = h1.get_text(strip=True)
            break

    # Extract the Introduction section
    introduction = _extract_introduction(soup)

    # Each views-row is one sub-program or course entry
    rows = soup.find_all("div", class_="views-row")
    for row in rows:
        h2 = row.find("h2")
        if not h2:
            continue

        raw_title = h2.get_text(strip=True)
        program_name, program_code = _parse_title(raw_title)

        # Skip section headers like "African Studies Programs" or "Courses"
        if not program_code and any(
            kw in program_name for kw in ["Programs", "Courses", "Introduction"]
        ):
            continue

        enrolment = _extract_field(row, "enrolment")
        completion = _extract_field(row, "completion")

        # Skip rows with no requirements (e.g. course description rows)
        if not enrolment and not completion:
            continue

        records.append({
            "program_name": program_name,
            "program_code": program_code,
            "program_type": _get_program_type(program_name),
            "department": department_name,
            "url": section_url,
            "introduction": introduction,
            "enrolment_requirements": enrolment,
            "completion_requirements": completion,
            "full_text": _build_full_text(
                program_name, program_code, department_name,
                introduction, enrolment, completion
            ),
        })

    # Fallback: if no sub-programs were found but there is an Introduction,
    # store the page as a Department-level record.
    # This handles departments that only offer courses (e.g. Anatomy).
    if not records and introduction:
        records.append({
            "program_name": department_name,
            "program_code": "",
            "program_type": "Department",
            "department": department_name,
            "url": section_url,
            "introduction": introduction,
            "enrolment_requirements": "",
            "completion_requirements": "",
            "full_text": _build_full_text(
                department_name, "", department_name,
                introduction, "", ""
            ),
        })

    return records


# ============================================================
# Helper functions
# ============================================================

def _extract_introduction(soup: BeautifulSoup) -> str:
    """Extract all paragraphs under the Introduction heading."""
    intro_h2 = soup.find("h2", string=lambda t: t and "Introduction" in t)
    if not intro_h2:
        return ""
    parts = []
    for sibling in intro_h2.find_next_siblings():
        if sibling.name == "h2":
            break
        text = sibling.get_text(strip=True)
        if text:
            parts.append(text)
    return "\n".join(parts)


def _extract_field(row: BeautifulSoup, field: str) -> str:
    """
    Extract enrolment or completion requirements from a views-row.
    Handles two HTML formats:
      Format 1 (UTSG printer-friendly): div with class containing field name
      Format 2 (UTM):                   h3 heading followed by content
    """
    # Format 1: div class contains "enrolment-requirements" or "completion-requirements"
    div = row.find("div", class_=lambda c: c and f"{field}-requirements" in c)
    if div:
        label = div.find("strong")
        if label:
            label.decompose()  # Remove the "Enrolment Requirements:" label text
        return div.get_text(separator="\n", strip=True)

    # Format 2 (UTM): h3 heading with keyword
    keyword = "Enrolment" if field == "enrolment" else "Completion"
    h3 = row.find("h3", string=lambda t: t and keyword in t)
    if h3:
        parts = []
        for sib in h3.find_next_siblings():
            if sib.name in ("h2", "h3"):
                break
            parts.append(sib.get_text(strip=True))
        return "\n".join(parts)

    return ""


def _parse_title(raw_title: str) -> tuple[str, str]:
    """
    Split a program title into name and code.
    e.g. "African Studies Specialist (Arts Program) - ASSPE1707"
      -> ("African Studies Specialist (Arts Program)", "ASSPE1707")
    """
    if " - " in raw_title:
        parts = raw_title.rsplit(" - ", 1)
        return parts[0].strip(), parts[1].strip()
    return raw_title.strip(), ""


def _get_program_type(name: str) -> str:
    """Infer the program type from the program name."""
    for ptype in ["Specialist", "Major", "Minor", "Certificate", "Focus"]:
        if ptype.lower() in name.lower():
            return ptype
    return "Other"


def _build_full_text(
    program_name: str,
    program_code: str,
    department: str,
    introduction: str,
    enrolment: str,
    completion: str,
) -> str:
    """
    Combine all fields into a single structured text string.
    Optimized for RAG retrieval — clear sections make it easy for the LLM to parse.
    """
    lines = [
        f"Program: {program_name}",
        f"Program Code: {program_code}" if program_code else "",
        f"Department: {department}",
        "",
        "=== About This Program ===",
        introduction or "No introduction available.",
        "",
        "=== Enrolment Requirements ===",
        enrolment or "No enrolment requirements listed.",
        "",
        "=== Completion Requirements ===",
        completion or "No completion requirements listed.",
    ]
    return "\n".join(lines)


# ============================================================
# Function 3: Main scraping flow (network mode)
# ============================================================

def scrape_all(max_pages: int = None):
    """
    Scrape all program pages and save results to JSON.

    Args:
        max_pages: Limit number of pages scraped (for testing). None = scrape all.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    session = requests.Session()
    session.headers.update(HEADERS)

    programs = get_all_program_slugs(session)

    if max_pages:
        programs = programs[:max_pages]
        print(f"⚠️  Test mode: scraping first {max_pages} pages only\n")

    all_records = []
    failed = []
    total = len(programs)

    for i, item in enumerate(programs, 1):
        print(f"[{i}/{total}] {item['name']}")
        try:
            resp = session.get(item["print_url"], headers=HEADERS, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            records = parse_program_page(soup, item["print_url"])
            if records:
                all_records.extend(records)
                print(f"  ✅ Extracted {len(records)} sub-program(s)")
            else:
                print(f"  ⚠️  No content extracted")
        except Exception as e:
            print(f"  ❌ Failed: {e}")
            failed.append(item["print_url"])
        time.sleep(CRAWL_DELAY)

    _save_results(all_records, failed)
    return all_records


# ============================================================
# Function 4: Local HTML file mode (fallback)
# ============================================================

def scrape_from_local(html_dir: str):
    """
    Parse local HTML files instead of scraping the web.
    Useful when the website is slow or inaccessible.
    Place all printer-friendly HTML files in html_dir.

    Usage:
        python scraper.py --local data/html_files
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    html_files = [f for f in os.listdir(html_dir) if f.endswith(".html")]
    print(f"📁 Found {len(html_files)} local HTML files\n")

    all_records = []
    failed = []

    for filename in html_files:
        filepath = os.path.join(html_dir, filename)
        slug = filename.replace(".html", "")
        fake_url = PRINT_URL_TEMPLATE.format(slug=slug)

        print(f"Parsing: {filename}")
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                soup = BeautifulSoup(f.read(), "html.parser")
            records = parse_program_page(soup, fake_url)
            if records:
                all_records.extend(records)
                print(f"  ✅ Extracted {len(records)} sub-program(s)")
            else:
                print(f"  ⚠️  No content extracted")
        except Exception as e:
            print(f"  ❌ Failed: {e}")
            failed.append(filename)

    _save_results(all_records, failed)
    return all_records


def _save_results(all_records: list, failed: list):
    """Save results to JSON and log any failed URLs."""
    print(f"\n💾 Saving results...")
    print(f"  Total records: {len(all_records)}")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_records, f, ensure_ascii=False, indent=2)
    print(f"  ✅ Saved to {OUTPUT_FILE}")
    if failed:
        failed_file = os.path.join(OUTPUT_DIR, "failed_urls.txt")
        with open(failed_file, "w") as f:
            f.write("\n".join(failed))
        print(f"  ⚠️  {len(failed)} failed — logged to {failed_file}")


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    if "--local" in sys.argv:
        idx = sys.argv.index("--local")
        html_dir = sys.argv[idx + 1]
        records = scrape_from_local(html_dir)
    elif "--test" in sys.argv:
        records = scrape_all(max_pages=5)
    else:
        records = scrape_all()

    print(f"\n🎉 Done! Extracted {len(records)} program records in total.")