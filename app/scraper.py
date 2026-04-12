"""
UofT Academic Calendar Scraper
================================
Strategy:
  1. Selenium fetches all 378 "View program details" links from the UofT listing page
  2. UTSC programs are fetched separately from utsc.calendar.utoronto.ca/program-sections
  3. Each program page is visited to find its "Printer-friendly Version" URL
  4. Printer-friendly pages are scraped and parsed into structured records

Usage:
  python scraper.py          # Scrape all programs
  python scraper.py --test   # Scrape first 5 only

Output: data/knowledge_base.json
"""

import json
import os
import re
import sys
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# ── Config ────────────────────────────────────────────────────────────────────

LISTING_URL  = "https://www.utoronto.ca/academics/undergraduate-programs"
UTSC_CAL_URL = "https://utsc.calendar.utoronto.ca/program-sections"
UTSC_PRINT   = "https://utsc.calendar.utoronto.ca/print/view/pdf/calendar_section_view/print_page/debug?view_args[]={slug}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

OUTPUT_DIR  = "data"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "knowledge_base.json")
CRAWL_DELAY = 1.0   # seconds between requests


# ── Step 1: Collect program links ─────────────────────────────────────────────

def get_all_program_links() -> list[dict]:
    """
    Return a list of program dicts:
      {name, program_url, campus, print_url_override (optional)}

    Sources:
      - Main listing page (Selenium, covers UTSG / UTM / some UTSC)
      - UTSC calendar page (requests, covers remaining UTSC sections)
    """
    programs    = _fetch_listing_page_links()
    utsc_extras = _fetch_utsc_calendar_links(seen={p["program_url"] for p in programs})
    programs.extend(utsc_extras)

    from collections import Counter
    counts = Counter(p["campus"] for p in programs)
    print(f"✅ Total program links: {len(programs)}")
    for campus, n in counts.most_common():
        print(f"   {campus}: {n}")

    return programs


def _fetch_listing_page_links() -> list[dict]:
    """Use Selenium to get all 'View program details' links from the main listing page."""
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager

    print("🌐 Opening listing page with Selenium...")
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
        time.sleep(10)  # wait for JS to render

        # Scroll to trigger lazy-loaded content
        height = driver.execute_script("return document.body.scrollHeight")
        pos = 0
        while pos < height:
            driver.execute_script(f"window.scrollTo(0, {pos});")
            time.sleep(0.3)
            pos += 1000
            height = driver.execute_script("return document.body.scrollHeight")
        time.sleep(3)

        soup = BeautifulSoup(driver.page_source, "html.parser")
    finally:
        driver.quit()

    programs, seen = [], set()
    for a in soup.find_all("a", string="View program details"):
        href = a.get("href", "").strip()
        if not href or href in seen:
            continue

        # Infer campus from URL domain
        if "utm.calendar" in href:
            campus = "UTM"
        elif "utsc" in href:
            campus = "UTSC"
        else:
            campus = "UTSG"

        # Get program name from nearest heading in parent container
        parent   = a.find_parent(["div", "li", "article"])
        name_tag = parent.find(["h3", "h2", "strong"]) if parent else None
        name     = name_tag.get_text(strip=True) if name_tag else href.split("/")[-1].replace("-", " ").title()

        seen.add(href)
        programs.append({"name": name, "program_url": href, "campus": campus})

    print(f"   Found {len(programs)} links on listing page")
    return programs


def _fetch_utsc_calendar_links(seen: set) -> list[dict]:
    """
    Fetch UTSC section links from utsc.calendar.utoronto.ca/program-sections.
    Uses a different printer-friendly URL format than artsci/utm.
    """
    print("🌐 Fetching UTSC calendar sections...")
    extras = []
    try:
        resp = requests.get(UTSC_CAL_URL, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/section/" not in href:
                continue

            slug     = href.split("/section/")[-1].strip()
            full_url = f"https://utsc.calendar.utoronto.ca/section/{slug}"
            if full_url in seen:
                continue

            seen.add(full_url)
            extras.append({
                "name":               a.get_text(strip=True),
                "program_url":        full_url,
                "campus":             "UTSC",
                "print_url_override": UTSC_PRINT.format(slug=slug),
            })

        print(f"   Found {len(extras)} additional UTSC calendar sections")
    except Exception as e:
        print(f"   ⚠️  UTSC calendar fetch failed: {e}")

    return extras


# ── Step 2: Resolve printer-friendly URL ──────────────────────────────────────

def get_printer_friendly_url(program_url: str, session: requests.Session) -> str | None:
    """
    Visit a program page and return the absolute printer-friendly URL,
    or None if not found.
    """
    try:
        resp = session.get(program_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        link = soup.find("a", string=lambda t: t and "Printer-friendly" in t)
        if link:
            return urljoin(program_url, link["href"].strip())
    except Exception as e:
        print(f"    ⚠️  Could not fetch {program_url}: {e}")
    return None


# ── Step 3: Parse printer-friendly pages ─────────────────────────────────────

def parse_program_page(soup: BeautifulSoup, url: str, campus: str = "UTSG") -> list[dict]:
    """
    Parse a printer-friendly page and return a list of program records.
    Handles three formats:
      - artsci / utm  : views-row divs with enrolment/completion fields
      - UTSC calendar : views-row divs (same structure)
      - Engineering   : h2 headings with BASC program codes
    """
    records = []

    # Department name — first h1 that is not the site title
    department = "Unknown"
    for h1 in soup.find_all("h1"):
        if "site-name" not in (h1.get("class") or []):
            department = h1.get_text(strip=True)
            break

    introduction = _extract_intro(soup)

    # Format A: views-row (artsci, utm, utsc)
    rows = soup.find_all("div", class_="views-row")
    for row in rows:
        h2 = row.find("h2")
        if not h2:
            continue

        name, code = _split_title(h2.get_text(strip=True))
        if not code and any(kw in name for kw in ["Programs", "Courses", "Introduction"]):
            continue

        enrolment  = _extract_field(row, "enrolment")
        completion = _extract_field(row, "completion")
        if not enrolment and not completion:
            continue

        records.append(_build_record(name, code, department, campus, url,
                                     introduction, enrolment, completion))

    # Format B: Engineering h2 headings (e.g. "... Chemical Engineering (AECHEBASC)")
    if not records:
        for h2 in soup.find_all("h2"):
            text = h2.get_text(strip=True)
            if not re.search(r'\([A-Z]{5,}\)', text):
                continue

            name, code = _split_engineering_title(text)
            if not name:
                continue

            # Grab the first few paragraphs as description
            desc_parts = []
            for sib in h2.find_next_siblings():
                if sib.name == "h2":
                    break
                if sib.name in ("p", "ul"):
                    t = sib.get_text(strip=True)
                    if t:
                        desc_parts.append(t)
                if len(desc_parts) >= 5:
                    break

            desc = "\n".join(desc_parts)
            if desc:
                records.append(_build_record(name, code, department, campus, url,
                                             introduction or desc, "", desc))

    # Fallback: store page-level intro as a department record
    if not records and introduction:
        records.append(_build_record(department, "", department, campus, url,
                                     introduction, "", "", program_type="Department"))

    return records


# ── Parsing helpers ───────────────────────────────────────────────────────────

def _extract_intro(soup: BeautifulSoup) -> str:
    h2 = soup.find("h2", string=lambda t: t and "Introduction" in t)
    if not h2:
        return ""
    parts = []
    for sib in h2.find_next_siblings():
        if sib.name == "h2":
            break
        t = sib.get_text(strip=True)
        if t:
            parts.append(t)
    return "\n".join(parts)


def _extract_field(row: BeautifulSoup, field: str) -> str:
    # Format 1: div with class containing field name
    div = row.find("div", class_=lambda c: c and f"{field}-requirements" in c)
    if div:
        label = div.find("strong")
        if label:
            label.decompose()
        return div.get_text(separator="\n", strip=True)

    # Format 2: h3 heading followed by content
    kw = "Enrolment" if field == "enrolment" else "Completion"
    h3 = row.find("h3", string=lambda t: t and kw in t)
    if h3:
        parts = []
        for sib in h3.find_next_siblings():
            if sib.name in ("h2", "h3"):
                break
            parts.append(sib.get_text(strip=True))
        return "\n".join(parts)

    return ""


def _split_title(raw: str) -> tuple[str, str]:
    if " - " in raw:
        parts = raw.rsplit(" - ", 1)
        return parts[0].strip(), parts[1].strip()
    return raw.strip(), ""


def _split_engineering_title(raw: str) -> tuple[str, str]:
    m = re.search(r'\(([A-Z]{3,})\)', raw)
    if not m:
        return "", ""
    code = m.group(1)
    name = raw[:m.start()].strip()
    for prefix in ("Undergraduate Program in ", "Program in "):
        if name.startswith(prefix):
            name = name[len(prefix):]
    return name.strip(), code


def _get_type(name: str) -> str:
    for t in ("Specialist", "Major", "Minor", "Certificate", "Focus"):
        if t.lower() in name.lower():
            return t
    return "Other"


def _build_record(name, code, department, campus, url,
                  intro, enrolment, completion, program_type=None) -> dict:
    campus_label = {
        "UTSG": "St. George Campus",
        "UTM":  "University of Toronto Mississauga (UTM)",
        "UTSC": "University of Toronto Scarborough (UTSC)",
    }.get(campus, campus)

    full_text = "\n".join(filter(None, [
        f"Program: {name}",
        f"Program Code: {code}" if code else "",
        f"Department: {department}",
        f"Campus: {campus_label}",
        "",
        "=== About This Program ===",
        intro or "No introduction available.",
        "",
        "=== Enrolment Requirements ===",
        enrolment or "No enrolment requirements listed.",
        "",
        "=== Completion Requirements ===",
        completion or "No completion requirements listed.",
    ]))

    return {
        "program_name":            name,
        "program_code":            code,
        "program_type":            program_type or _get_type(name),
        "department":              department,
        "campus":                  campus,
        "url":                     url,
        "introduction":            intro,
        "enrolment_requirements":  enrolment,
        "completion_requirements": completion,
        "full_text":               full_text,
    }


# ── Main scraping flow ────────────────────────────────────────────────────────

def scrape_all(max_pages: int = None) -> list[dict]:
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    programs = get_all_program_links()
    if max_pages:
        programs = programs[:max_pages]
        print(f"⚠️  Test mode: first {max_pages} programs only\n")

    session = requests.Session()
    session.headers.update(HEADERS)

    all_records, failed, seen_print_urls = [], [], set()

    for i, item in enumerate(programs, 1):
        print(f"[{i}/{len(programs)}] [{item['campus']}] {item['name']}")

        # Resolve printer-friendly URL
        print_url = (
            item.get("print_url_override")
            or get_printer_friendly_url(item["program_url"], session)
        )

        if not print_url:
            print("  ⚠️  No printer-friendly URL — skipping")
            failed.append(item["program_url"])
            time.sleep(CRAWL_DELAY)
            continue

        if print_url in seen_print_urls:
            print("  ⏭️  Already scraped this section")
            continue
        seen_print_urls.add(print_url)

        # Scrape and parse
        try:
            resp = session.get(print_url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            records = parse_program_page(
                BeautifulSoup(resp.text, "html.parser"),
                print_url,
                item["campus"]
            )
            if records:
                all_records.extend(records)
                print(f"  ✅ {len(records)} sub-program(s)")
            else:
                print("  ⚠️  No content extracted")
        except Exception as e:
            print(f"  ❌ {e}")
            failed.append(print_url)

        time.sleep(CRAWL_DELAY)

    _save(all_records, failed)
    return all_records


def _save(records: list, failed: list):
    from collections import Counter
    print(f"\n💾 Saving {len(records)} records...")
    for campus, n in Counter(r["campus"] for r in records).most_common():
        print(f"   {campus}: {n}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"✅ Saved → {OUTPUT_FILE}")

    if failed:
        fail_path = os.path.join(OUTPUT_DIR, "failed_urls.txt")
        with open(fail_path, "w") as f:
            f.write("\n".join(failed))
        print(f"⚠️  {len(failed)} failures → {fail_path}")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    records = scrape_all(max_pages=5 if "--test" in sys.argv else None)
    print(f"\n🎉 Done! {len(records)} records total.")