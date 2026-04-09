from rag import rag_answer

def test_rag():
    questions = [
        "What are the requirements for African Studies Specialist?",
        "What courses do I need for Rotman Commerce Accounting?",
        "I enjoy math and coding, what program should I pick?",
    ]

    for q in questions:
        print(f"\n{'='*60}")
        print(f"Question: {q}")
        print(f"{'='*60}")
        result = rag_answer(q)
        print(f"\nAnswer:\n{result['answer']}")
        print(f"\nSources:")
        for s in result['sources']:
            print(f"  - {s['program_name']} ({s['department']})")

test_rag()