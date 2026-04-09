from agent import build_agent, chat

def test_agent():
    agent = build_agent()
    history = []

    # Test 1: RAG question
    print("\n" + "="*60)
    print("Test 1: Program requirements question")
    print("="*60)
    response, history = chat(agent, "What are the requirements for Rotman Commerce Accounting?", history)
    print(f"Agent: {response}")

    # Test 2: Follow-up (multi-turn)
    print("\n" + "="*60)
    print("Test 2: Follow-up question (multi-turn)")
    print("="*60)
    response, history = chat(agent, "What about the Finance and Economics stream?", history)
    print(f"Agent: {response}")

    # Test 3: Out-of-scope (guardrail)
    print("\n" + "="*60)
    print("Test 3: Out-of-scope question (guardrail)")
    print("="*60)
    response, history = chat(agent, "Can you write me a Python script?", history)
    print(f"Agent: {response}")

    # Test 4: Multi-turn appointment booking
    print("\n" + "="*60)
    print("Test 4: Appointment booking (multi-turn)")
    print("="*60)
    history = []  # Fresh conversation
    response, history = chat(agent, "I want to book an appointment with an advisor", history)
    print(f"Agent: {response}")
    response, history = chat(agent, "My name is Sarah Chen", history)
    print(f"Agent: {response}")
    response, history = chat(agent, "I want to discuss program selection", history)
    print(f"Agent: {response}")
    response, history = chat(agent, "Wednesday morning works for me", history)
    print(f"Agent: {response}")

test_agent()