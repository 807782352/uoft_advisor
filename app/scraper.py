"""
UofT Academic Calendar Scraper
================================
Scrapes all undergraduate program pages from UofT.
Strategy:
  1. Use Selenium to get all 378 "View program details" links
  2. Visit each program page to find the "Printer-friendly Version" URL
  3. Scrape the printer-friendly page for program details

Usage:
  python scraper.py            # Scrape all programs
  python scraper.py --test     # Scrape first 5 only (for testing)

Output: data/knowledge_base.json
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import os
import sys
from urllib.parse import urljoin

# ============================================================
# Configuration
# ============================================================

LISTING_URL = "https://www.utoronto.ca/academics/undergraduate-programs"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

OUTPUT_DIR = "data"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "knowledge_base.json")
CRAWL_DELAY = 1.0


# ============================================================
# Function 1: Get all program links using Selenium
# ============================================================

def get_all_program_links() -> list[dict]:
    """
    Use Selenium to get all 'View program details' links from listing page.

    Returns:
        [{"name": "Accounting", "program_url": "https://artsci.../section/..."}, ...]
    """
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.by import By
    from webdriver_manager.chrome import ChromeDriverManager

    print(f"📋 Starting browser to fetch program list...")

    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )

    try:
        driver.get(LISTING_URL)

        # Wait for program links to appear
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located(
                (By.PARTIAL_LINK_TEXT, "View program details")
            )
        )
        time.sleep(5)

        # Scroll through the page to trigger lazy loading
        scroll_height = driver.execute_script("return document.body.scrollHeight")
        current = 0
        while current < scroll_height:
            driver.execute_script(f"window.scrollTo(0, {current});")
            time.sleep(0.3)
            current += 1000
            scroll_height = driver.execute_script("return document.body.scrollHeight")

        time.sleep(3)
        soup = BeautifulSoup(driver.page_source, "html.parser")

    finally:
        driver.quit()

    programs = []
    seen_urls = set()

    # Find all "View program details" links
    for a in soup.find_all("a", string="View program details"):
        href = a.get("href", "").strip()
        if not href or href in seen_urls:
            continue

        # Get program name from parent element
        parent = a.find_parent(["div", "li", "article"])
        if parent:
            name_el = parent.find(["h3", "h2", "strong"])
            name = name_el.get_text(strip=True) if name_el else href.split("/")[-1].replace("-", " ").title()
        else:
            name = href.split("/")[-1].replace("-", " ").title()

        # Determine campus from URL
        if "utm.calendar" in href:
            campus = "UTM"
        elif "utsc.calendar" in href or "utsc.utoronto.ca" in href:
            campus = "UTSC"
        else:
            campus = "UTSG"

        seen_urls.add(href)
        programs.append({
            "name":        name,
            "program_url": href,
            "campus":      campus,
        })

    print(f"✅ Found {len(programs)} program pages")
    from collections import Counter
    for campus, count in Counter(p["campus"] for p in programs).most_common():
        print(f"   {campus}: {count}")

    return programs


# ============================================================
# Function 2: Get printer-friendly URL from program page
# ============================================================

def get_printer_friendly_url(
    program_url: str,
    session: requests.Session
) -> str | None:
    """
    Visit a program page and find the 'Printer-friendly Version' link.

    Returns:
        Full printer-friendly URL, or None if not found.
    """
    try:
        resp = session.get(program_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Find "Printer-friendly Version" link
        printer_link = soup.find(
            "a", string=lambda t: t and "Printer-friendly" in t
        )

        if printer_link:
            href = printer_link.get("href", "").strip()
            # Convert relative URL to absolute
            full_url = urljoin(program_url, href)
            return full_url

        return None

    except Exception as e:
        print(f"    ⚠️  Error fetching {program_url}: {e}")
        return None


# ============================================================
# Function 3: Parse a printer-friendly page
# ============================================================

def parse_program_page(
    soup: BeautifulSoup,
    section_url: str,
    campus: str = "UTSG"
) -> list[dict]:
    """
    Parse a printer-friendly program page and extract all sub-programs.

    Returns:
        A list of dicts, one per sub-program found on the page.
    """
    records = []

    # Department name from h1 (exclude site navigation h1)
    department_name = "Unknown"
    for h1 in soup.find_all("h1"):
        classes = h1.get("class") or []
        if "site-name" not in classes:
            department_name = h1.get_text(strip=True)
            break

    # Extract Introduction section
    introduction = _extract_introduction(soup)

    # Try standard views-row format (artsci/utm)
    rows = soup.find_all("div", class_="views-row")
    if rows:
        for row in rows:
            h2 = row.find("h2")
            if not h2:
                continue

            raw_title = h2.get_text(strip=True)
            program_name, program_code = _parse_title(raw_title)

            # Skip section headers
            if not program_code and any(
                kw in program_name for kw in ["Programs", "Courses", "Introduction"]
            ):
                continue

            enrolment = _extract_field(row, "enrolment")
            completion = _extract_field(row, "completion")

            if not enrolment and not completion:
                continue

            records.append(_make_record(
                program_name, program_code, department_name,
                campus, section_url, introduction, enrolment, completion
            ))

    # Try Engineering format (h2 with program code in parentheses)
    if not records:
        for h2 in soup.find_all("h2"):
            text = h2.get_text(strip=True)
            # Engineering programs have code like (AECHEBASC) or (AECPEBASC)
            if not ("(" in text and "BASC" in text or "BASc" in text.lower()):
                continue

            program_name, program_code = _parse_engineering_title(text)
            if not program_name:
                continue

            # Extract description from following paragraphs
            description_parts = []
            for sib in h2.find_next_siblings():
                if sib.name == "h2":
                    break
                if sib.name in ["p", "ul"]:
                    t = sib.get_text(strip=True)
                    if t:
                        description_parts.append(t)
                if len(description_parts) > 5:
                    break

            description = "\n".join(description_parts)

            if description:
                records.append(_make_record(
                    program_name, program_code, department_name,
                    campus, section_url, introduction or description, "", description
                ))

    # Fallback: Department-level record
    if not records and introduction:
        records.append(_make_record(
            department_name, "", department_name,
            campus, section_url, introduction, "", "",
            program_type="Department"
        ))

    return records


# ============================================================
# Helper functions
# ============================================================

def _extract_introduction(soup: BeautifulSoup) -> str:
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
    div = row.find("div", class_=lambda c: c and f"{field}-requirements" in c)
    if div:
        label = div.find("strong")
        if label:
            label.decompose()
        return div.get_text(separator="\n", strip=True)

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
    if " - " in raw_title:
        parts = raw_title.rsplit(" - ", 1)
        return parts[0].strip(), parts[1].strip()
    return raw_title.strip(), ""


def _parse_engineering_title(raw_title: str) -> tuple[str, str]:
    """Parse Engineering program title like 'Undergraduate Program in Chemical Engineering (AECHEBASC)'"""
    import re
    match = re.search(r'\(([A-Z]{3,})\)', raw_title)
    if match:
        code = match.group(1)
        name = raw_title[:match.start()].strip()
        # Clean up common prefixes
        for prefix in ["Undergraduate Program in ", "Program in "]:
            if name.startswith(prefix):
                name = name[len(prefix):]
        return name.strip(), code
    return "", ""


def _get_program_type(name: str) -> str:
    for ptype in ["Specialist", "Major", "Minor", "Certificate", "Focus"]:
        if ptype.lower() in name.lower():
            return ptype
    return "Other"


def _make_record(
    program_name, program_code, department, campus,
    url, introduction, enrolment, completion,
    program_type=None
) -> dict:
    campus_label = {
        "UTSG": "St. George Campus",
        "UTM":  "University of Toronto Mississauga (UTM)",
        "UTSC": "University of Toronto Scarborough (UTSC)",
    }.get(campus, campus)

    ptype = program_type or _get_program_type(program_name)

    full_text = "\n".join([
        f"Program: {program_name}",
        f"Program Code: {program_code}" if program_code else "",
        f"Department: {department}",
        f"Campus: {campus_label}",
        "",
        "=== About This Program ===",
        introduction or "No introduction available.",
        "",
        "=== Enrolment Requirements ===",
        enrolment or "No enrolment requirements listed.",
        "",
        "=== Completion Requirements ===",
        completion or "No completion requirements listed.",
    ])

    return {
        "program_name":            program_name,
        "program_code":            program_code,
        "program_type":            ptype,
        "department":              department,
        "campus":                  campus,
        "url":                     url,
        "introduction":            introduction,
        "enrolment_requirements":  enrolment,
        "completion_requirements": completion,
        "full_text":               full_text,
    }


# ============================================================
# Function 4: Main scraping flow
# ============================================================

def scrape_all(max_pages: int = None):
    """
    Main scraping flow:
    1. Get all program links via Selenium
    2. For each: find printer-friendly URL → scrape → parse
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Step 1: Get all program links
    programs = get_all_program_links()

    if max_pages:
        programs = programs[:max_pages]
        print(f"⚠️  Test mode: scraping first {max_pages} pages only\n")

    session = requests.Session()
    session.headers.update(HEADERS)

    all_records = []
    failed = []
    seen_print_urls = set()  # avoid duplicate printer-friendly pages
    total = len(programs)

    for i, item in enumerate(programs, 1):
        print(f"[{i}/{total}] [{item['campus']}] {item['name']}")

        # Step 2: Get printer-friendly URL
        print_url = get_printer_friendly_url(item["program_url"], session)

        if not print_url:
            print(f"  ⚠️  No printer-friendly URL found")
            failed.append(item["program_url"])
            time.sleep(CRAWL_DELAY)
            continue

        # Skip duplicate printer-friendly pages
        # (multiple programs may share the same section page)
        if print_url in seen_print_urls:
            print(f"  ⏭️  Already scraped this page")
            continue

        seen_print_urls.add(print_url)

        # Step 3: Scrape printer-friendly page
        try:
            resp = session.get(print_url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            records = parse_program_page(soup, print_url, item["campus"])

            if records:
                all_records.extend(records)
                print(f"  ✅ Extracted {len(records)} sub-program(s)")
            else:
                print(f"  ⚠️  No content extracted")

        except Exception as e:
            print(f"  ❌ Failed: {e}")
            failed.append(print_url)

        time.sleep(CRAWL_DELAY)

    _save_results(all_records, failed)
    return all_records


def _save_results(all_records: list, failed: list):
    from collections import Counter
    print(f"\n💾 Saving results...")
    print(f"  Total records: {len(all_records)}")

    campus_counts = Counter(r["campus"] for r in all_records)
    for campus, count in campus_counts.most_common():
        print(f"  {campus}: {count} records")

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
    if "--test" in sys.argv:
        records = scrape_all(max_pages=5)
    else:
        records = scrape_all()

    print(f"\n🎉 Done! Extracted {len(records)} program records in total.")