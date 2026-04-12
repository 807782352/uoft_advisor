# test_scraper.py
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'app')))

import requests
from bs4 import BeautifulSoup
from scraper import parse_program_page, scrape_all, get_all_program_links


def test_get_slugs():
    programs = get_all_program_links() 
    print(f"\nTotal programs: {len(programs)}")
    for p in programs[:10]:
        print(f"  [{p['campus']}] {p['name']}")
        
        
def test_parse_page():
    session = requests.Session()
    
    test_slug = "African-Studies"
    print_url = f"https://artsci.calendar.utoronto.ca/print/view/pdf/section_view/print_page/debug?view_args[]={test_slug}"
    
    print(f"Testing parsing: {print_url}\n")
    
    resp = session.get(print_url, timeout=15)
    soup = BeautifulSoup(resp.text, "html.parser")
    
    records = parse_program_page(soup, print_url, campus="UTSG")  # ← add campus
    
    print(f"Extracted {len(records)} sub-programs\n")
    for r in records:
        print(f"  Program:  {r['program_name']}")
        print(f"  Code:     {r['program_code']}")
        print(f"  Type:     {r['program_type']}")
        print(f"  Campus:   {r['campus']}")           # ← add campus
        print(f"  Enrolment length:   {len(r['enrolment_requirements'])} characters")
        print(f"  Completion length:  {len(r['completion_requirements'])} characters")
        print(f"  Full text length:   {len(r['full_text'])} characters")
        print()
        
def test_scrape_all():
    records = scrape_all()
    
    print(f"\nFinal Results:")
    print(f"  Total Records: {len(records)}")
    
    from collections import Counter
    
    print(f"\nBy Type:")
    types = Counter(r['program_type'] for r in records)
    for t, count in types.most_common():
        print(f"  {t}: {count} programs")

    print(f"\nBy Campus:")                             # new campus
    campuses = Counter(r['campus'] for r in records)
    for c, count in campuses.most_common():
        print(f"  {c}: {count} programs")
        

def test_empty_pages():
    session = requests.Session()
    
    for slug in ["Academic-Bridging-Program", "Anatomy"]:
        print_url = f"https://artsci.calendar.utoronto.ca/print/view/pdf/section_view/print_page/debug?view_args[]={slug}"
        
        resp = session.get(print_url, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        records = parse_program_page(soup, print_url, campus="UTSG")  # ← add campus
        
        print(f"=== {slug} ===")
        print(f"Extracted {len(records)} records")
        for r in records:
            print(f"  Type: {r['program_type']}")
            print(f"  Name: {r['program_name']}")
            print(f"  Introduction length: {len(r['introduction'])} characters")
        print()


def debug_missing():
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    from bs4 import BeautifulSoup
    import time

    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )

    driver.get("https://www.utoronto.ca/academics/undergraduate-programs")
    time.sleep(8)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    driver.quit()

    # 找所有 "View program details" 链接
    all_links = soup.find_all("a", string="View program details")
    print(f"总共找到 'View program details' 链接: {len(all_links)}")
    print()

    # 分类统计
    artsci, utm, engineering, music, daniels, other = [], [], [], [], [], []
    for a in all_links:
        href = a["href"]
        if "artsci.calendar" in href:
            artsci.append(href)
        elif "utm.calendar" in href:
            utm.append(href)
        elif "engineering.calendar" in href:
            engineering.append(href)
        elif "music.calendar" in href:
            music.append(href)
        elif "daniels.calendar" in href:
            daniels.append(href)
        else:
            other.append(href)

    print(f"artsci:      {len(artsci)}")
    print(f"utm:         {len(utm)}")
    print(f"engineering: {len(engineering)}")
    print(f"music:       {len(music)}")
    print(f"daniels:     {len(daniels)}")
    print(f"other:       {len(other)}")
    print()
    print("Other 链接:")
    for l in other[:10]:
        print(f"  {l}")

def debug_raw_links():
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    from bs4 import BeautifulSoup
    import time

    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )

    driver.get("https://www.utoronto.ca/academics/undergraduate-programs")
    time.sleep(8)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    driver.quit()

    all_cal_links = [
        a["href"] for a in soup.find_all("a", href=True)
        if "calendar.utoronto.ca/section" in a["href"]
    ]
    
    print(f"Total calendar/section Links: {len(all_cal_links)}")
    
    unique = list(set(all_cal_links))
    print(f"After deduplication: {len(unique)}")
    
    from collections import Counter
    domains = Counter(l.split("/")[2] for l in unique)
    for domain, count in domains.most_common():
        print(f"  {domain}: {count}")

def test_printer_friendly_flow():
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.by import By
    from webdriver_manager.chrome import ChromeDriverManager
    from bs4 import BeautifulSoup
    import time, requests

    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )

    # Step 1: 打开listing页面
    driver.get("https://www.utoronto.ca/academics/undergraduate-programs")
    time.sleep(8)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    driver.quit()

    # Step 2: 找所有 "View program details" 链接
    all_links = soup.find_all("a", string="View program details")
    print(f"找到 {len(all_links)} 个 program 链接")

    # Step 3: 测试前3个，找它们的 Printer-friendly URL
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})

    for a in all_links[:10]:
        program_url = a["href"]
        print(f"\n程序页面: {program_url}")

        # 访问 program 页面，找 Printer-friendly 链接
        resp = session.get(program_url, timeout=15)
        page_soup = BeautifulSoup(resp.text, "html.parser")

        # 找 Printer-friendly Version 链接
        printer_link = page_soup.find("a", string=lambda t: t and "Printer-friendly" in t)
        if printer_link:
            print(f"  ✅ Printer-friendly URL: {printer_link['href']}")
        else:
            print(f"  ❌ 没有找到 Printer-friendly 链接")


def debug_utsc():
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    from bs4 import BeautifulSoup
    import time

    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )

    driver.get("https://www.utoronto.ca/academics/undergraduate-programs")
    time.sleep(10)
    soup = BeautifulSoup(driver.page_source, "html.parser")
    driver.quit()

    all_links = soup.find_all("a", string="View program details")
    
    utsc_admissions = [a["href"] for a in all_links if "utsc.utoronto.ca/admissions" in a["href"]]
    utsc_calendar   = [a["href"] for a in all_links if "utsc.calendar.utoronto.ca" in a["href"]]
    
    print(f"UTSC admissions 格式: {len(utsc_admissions)}")
    print(f"UTSC calendar 格式:   {len(utsc_calendar)}")
    print("\nUTSC calendar 链接:")
    for l in utsc_calendar:
        print(f"  {l}")
        
def debug_utsc_calendar():
    import requests
    from bs4 import BeautifulSoup

    url = "https://utsc.calendar.utoronto.ca/program-sections"
    resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(resp.text, "html.parser")

    print(f"Status: {resp.status_code}")
    
    # 找所有链接
    links = soup.find_all("a", href=True)
    print(f"总链接数: {len(links)}")
    
    # 找 section 链接
    section_links = [a for a in links if "/section/" in a.get("href", "")]
    print(f"Section 链接数: {len(section_links)}")
    for a in section_links[:10]:
        print(f"  {a['href']} — {a.get_text(strip=True)}")


def debug_utsc_add():
    import requests
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin

    HEADERS = {"User-Agent": "Mozilla/5.0"}
    
    utsc_resp = requests.get(
        "https://utsc.calendar.utoronto.ca/program-sections",
        headers=HEADERS, timeout=15
    )
    utsc_soup = BeautifulSoup(utsc_resp.text, "html.parser")

    programs = []
    for a in utsc_soup.find_all("a", href=True):
        href = a["href"]
        if "/section/" not in href:
            continue
        slug = href.split("/section/")[-1].strip()
        full_url = f"https://utsc.calendar.utoronto.ca/section/{slug}"
        print_url = f"https://utsc.calendar.utoronto.ca/print/view/pdf/calendar_section_view/print_page/debug?view_args[]={slug}"
        name = a.get_text(strip=True)
        programs.append({"name": name, "program_url": full_url, "print_url_override": print_url})

    print(f"UTSC calendar programs: {len(programs)}")
    for p in programs[:5]:
        print(f"  {p['name']} → {p['print_url_override']}")



test_get_slugs()
# test_parse_page()
# test_scrape_all()
# test_empty_pages()

# --- Other Tests ---
# debug_missing()
# debug_raw_links()
# debug_utsc()
# debug_utsc_calendar()
# debug_utsc_add()

# test_printer_friendly_flow()