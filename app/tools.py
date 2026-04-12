import sys, os
sys.path.insert(0, os.path.dirname(__file__)) 

from langchain_core.tools import tool
from rag import rag_answer
from config import llm

# ============================================================
# Tool 1: Answer questions using RAG (Knowledge QA)
# ============================================================

@tool
def search_programs(query: str) -> str:
    """
    Search the UofT knowledge base to answer questions about programs,
    courses, enrolment requirements, and completion requirements.
    Use this for any factual question about UofT academic programs.
    
    Examples:
    - "What are the requirements for African Studies Specialist?"
    - "What courses do I need for Rotman Commerce?"
    - "Does UofT offer a Computer Science program?"
    """
    result = rag_answer(query)
    
    answer = result["answer"]
    sources = result["sources"]
    
    # Append source attribution
    if sources:
        answer += "\n\n**Sources:**"
        seen = set()
        for s in sources:
            key = s["program_name"]
            if key not in seen:
                seen.add(key)
                answer += f"\n- {s['program_name']} ({s['department']})"
                if s["url"]:
                    answer += f" — {s['url']}"
    
    return answer


# ============================================================
# Tool 2: Recommend programs based on student profile
# ============================================================

@tool
def recommend_programs(student_profile: str) -> str:
    """
    Recommend suitable UofT undergraduate programs based on a student's
    background, interests, strengths, or goals.
    Use this when a student describes themselves and wants program suggestions.
    
    Examples:
    - "I love biology and want to work in medicine"
    - "I'm good at math and enjoy building things"
    - "I'm interested in business and economics"
    """
    # Step 1: Use profile to retrieve relevant programs
    result = rag_answer(student_profile)
    context = result["answer"]
    sources = result["sources"]

    # Step 2: Ask LLM to make personalized recommendations
    prompt = f"""You are a UofT academic advisor helping a student choose a program.

Student Profile:
{student_profile}

Relevant Programs from Knowledge Base:
{context}

Based on the student's profile and the available programs above,
recommend 2-3 the most suitable UofT undergraduate programs.
For each recommendation:
1. Name the program and department
2. Explain why it fits the student's profile
3. Mention one key requirement or highlight

Keep your response friendly and encouraging.
"""
    response = llm.invoke(prompt)
    
    # Append sources
    answer = response.content
    if sources:
        answer += "\n\n**Relevant Programs Found:**"
        seen = set()
        for s in sources:
            key = s["program_name"]
            if key not in seen:
                seen.add(key)
                answer += f"\n- {s['program_name']} ({s['department']})"

    return answer


@tool
def book_advisor_appointment(
    student_name: str,
    topic: str,
    preferred_time: str,
    email: str = ""
) -> str:
    """
    Book a mock appointment with a UofT academic advisor.
    Use this when a student wants to meet with an advisor.
    Collect these through conversation if missing:
      - student_name: the student's full name
      - topic: what they want to discuss (e.g. program selection, course planning)
      - preferred_time: a specific future date and time (e.g. "Monday April 14th at 2pm")
      - email: the student's Email address for confirmation (REQUIRED before confirming)

    IMPORTANT: Always ask for the student's Email address before confirming the booking.
    """
    # If email is missing, ask for it
    if not email:
        return (
            f"Got it! I have your name as **{student_name}**, topic as **{topic}**, "
            f"and time as **{preferred_time}**.\n\n"
            f"Could you please provide your **Email address** so we can send you a confirmation? 📧"
        )

    confirmation = f"""
✅ **Appointment Confirmed!**

Here are your booking details:
- **Student Name:** {student_name}
- **Topic:** {topic}
- **Preferred Time:** {preferred_time}
- **Email:** {email}
- **Advisor:** UofT Academic Advising Office
- **Location:** Sidney Smith Hall, Room 1006 (or via Zoom upon request)
- **Confirmation #:** ADV-{abs(hash(student_name + topic)) % 100000:05d}

A confirmation has been sent to **{email}**.
An advisor will reach out within 1-2 business days.
If you need to reschedule, please call **416-978-2011** (St. George Campus).
"""
    return confirmation

# ============================================================
# Export all tools
# ============================================================

TOOLS = [search_programs, recommend_programs, book_advisor_appointment]