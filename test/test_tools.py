import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'app')))

from tools import search_programs, recommend_programs, book_advisor_appointment

def test_tools():
    print("\n" + "="*60)
    print("Tool 1: search_programs")
    print("="*60)
    result = search_programs.invoke("What courses do I need for Rotman Commerce Accounting?")
    print(result)

    print("\n" + "="*60)
    print("Tool 2: recommend_programs")
    print("="*60)
    result = recommend_programs.invoke("I enjoy math and statistics, and I want a career in finance")
    print(result)

    print("\n" + "="*60)
    print("Tool 3: book_advisor_appointment")
    print("="*60)
    result = book_advisor_appointment.invoke({
        "student_name": "John Smith",
        "topic": "Program selection for first year",
        "preferred_time": "Monday afternoon"
    })
    print(result)

test_tools()