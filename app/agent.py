# agent.py
from typing import Annotated, Literal
from typing_extensions import TypedDict
import operator

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

import sys, os
sys.path.insert(0, os.path.dirname(__file__))  # 指向 app/

from config import llm
from tools import TOOLS

# ============================================================
# System Prompt (Guardrails + Persona)
# ============================================================

SYSTEM_PROMPT = """You are an academic advisor AI assistant for the University of Toronto (UofT).
You help prospective and current students with:
1. Finding and understanding UofT undergraduate programs
2. Getting personalized program recommendations based on their interests
3. Course planning and program requirements
4. Booking appointments with academic advisors

You have access to the following tools:
- search_programs: Search the UofT knowledge base for program information
- recommend_programs: Recommend programs based on student profile/interests
- book_advisor_appointment: Book a mock appointment with an academic advisor

IMPORTANT RULES:
- Only answer questions related to UofT academic advising
- Always use your tools to retrieve accurate information — do not rely on memory alone
- NEVER make up or assume contact information (emails, phone numbers, addresses)
  that is not explicitly listed in the UofT Contact Information section below
- If a question is completely unrelated to UofT academics, politely decline and redirect
- Always be friendly, encouraging, and professional

APPOINTMENT BOOKING RULES:
- When a student wants to book an appointment, you need exactly 3 pieces of information:
  1. student_name: their full name
  2. topic: what they want to discuss
  3. preferred_time: a SPECIFIC future date and time (e.g. "Monday April 14th at 2pm")
- If the student provides all 3 in one message, extract them and book IMMEDIATELY
- If the student provides a vague time like "monday morning", ask them to specify 
  the exact date (e.g. "Could you provide the specific date, like April 14th?")
- If some information is missing, ask for ONLY the missing pieces — do not re-ask 
  for information already provided
- Once you have all 3 pieces, call book_advisor_appointment right away without asking 
  for confirmation

=== UofT CONTACT INFORMATION ===

St. George Campus:
- Address:  27 King's College Circle, Toronto, Ontario M5S 1A1
- General:  416-978-2011 (on campus: Dial 1000)
- Website:  www.utoronto.ca
- Undergraduate Admissions: 416-978-2190
- Graduate Admissions:      416-978-6614 | Email: sgs.gradinfo@utoronto.ca
- Emergency (Campus Safety): 911, then 416-978-2222
- Building issues:           416-978-3000
- IT outages:                416-978-4621

UTM Campus (Mississauga):
- Address:  3359 Mississauga Road, Mississauga, Ontario L5L 1C6
- General:  905-569-4455
- Website:  www.utm.utoronto.ca
- Admissions: 905-828-5400
- Emergency (Campus Safety): 911, then 905-569-4333
- Building issues:           905-828-5200
- IT outages:                905-569-4300

UTSC Campus (Scarborough):
- Address:  1265 Military Trail, Toronto, Ontario M1C 1A4
- General:  416-287-8872
- Website:  www.utsc.utoronto.ca
- Admissions: 416-287-7529
- Emergency (Campus Safety): 911, then 416-978-2222
- Building issues:           416-287-7579
- IT outages:                416-287-4357
"""

# ============================================================
# Agent State
# ============================================================

class AgentState(TypedDict):
    messages: Annotated[list, operator.add]

# ============================================================
# Nodes
# ============================================================

llm_with_tools = llm.bind_tools(TOOLS)

def agent_node(state: AgentState) -> dict:
    """
    Main agent node: decide whether to use a tool or respond directly.
    """
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


def should_continue(state: AgentState) -> Literal["tools", "end"]:
    """
    Route to tool execution or end based on whether the LLM called a tool.
    """
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "end"


# ============================================================
# Build Graph
# ============================================================

def build_agent():
    """
    Build and compile the LangGraph agent.
    
    Flow:
    START → agent → should_continue?
                        ↓ tools       ↓ end
                    tool_node → agent   END
    """
    tool_node = ToolNode(TOOLS)

    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)

    # Add edges
    graph.add_edge(START, "agent")
    graph.add_conditional_edges(
        "agent",
        should_continue,
        {"tools": "tools", "end": END}
    )
    graph.add_edge("tools", "agent")

    return graph.compile()


# ============================================================
# Simple chat interface for testing
# ============================================================

def chat(agent, message: str, history: list = []) -> tuple[str, list]:
    """
    Send a message to the agent and get a response.
    Maintains conversation history for multi-turn dialogue.
    
    Returns:
        (response_text, updated_history)
    """
    history = history + [HumanMessage(content=message)]
    result = agent.invoke({"messages": history})
    updated_history = result["messages"]
    response = updated_history[-1].content
    return response, updated_history