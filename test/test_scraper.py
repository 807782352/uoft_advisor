# test_scraper.py
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'app')))

import requests
from bs4 import BeautifulSoup
from scraper import get_all_program_slugs, parse_program_page, scrape_all


def test_get_slugs():
    session = requests.Session()
    programs = get_all_program_slugs(session)

    print(f"\nTotal: {len(programs)} programs")
    print("\nFirst 5:")
    for p in programs[:5]:
        print(f"  Name: {p['name']}")
        print(f"  slug: {p['slug']}")
        print(f"  print_url: {p['print_url']}")
        print()
        
        
def test_parse_page():
    session = requests.Session()
    
    # Use African Studies for testing
    test_slug = "African-Studies"
    print_url = f"https://artsci.calendar.utoronto.ca/print/view/pdf/section_view/print_page/debug?view_args[]={test_slug}"
    
    print(f"Testing parsing: {print_url}\n")
    
    resp = session.get(print_url, timeout=15)
    soup = BeautifulSoup(resp.text, "html.parser")
    
    records = parse_program_page(soup, print_url)
    
    print(f"Extracted {len(records)} sub-programs\n")
    for r in records:
        print(f"  Program:  {r['program_name']}")
        print(f"  Code:     {r['program_code']}")
        print(f"  Type:     {r['program_type']}")
        print(f"  Enrolment length:   {len(r['enrolment_requirements'])} characters")
        print(f"  Completion length:  {len(r['completion_requirements'])} characters")
        print(f"  Full text length:   {len(r['full_text'])} characters")
        print()
        
def test_scrape_all():
    # Remove max_pages，Scrape all 92 programs
    records = scrape_all()
    
    print(f"\nFinal Results:")
    print(f"  Total Records: {len(records)}")
    
    # 按类型统计
    from collections import Counter
    types = Counter(r['program_type'] for r in records)
    print(f"\nBy Type Distribution:")
    for t, count in types.most_common():
        print(f"  {t}: {count} programs")
        

def test_empty_pages():
    import requests
    from bs4 import BeautifulSoup

    session = requests.Session()
    
    for slug in ["Academic-Bridging-Program", "Anatomy"]:
        print_url = f"https://artsci.calendar.utoronto.ca/print/view/pdf/section_view/print_page/debug?view_args[]={slug}"
        
        resp = session.get(print_url, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        records = parse_program_page(soup, print_url)
        
        print(f"=== {slug} ===")
        print(f"Extracted {len(records)} records")
        for r in records:
            print(f"  Type: {r['program_type']}")
            print(f"  Name: {r['program_name']}")
            print(f"  Introduction length: {len(r['introduction'])} characters")
        print()


# test_get_slugs()
# test_parse_page()
# test_scrape_all()
# test_empty_pages()