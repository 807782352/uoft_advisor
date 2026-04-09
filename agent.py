# agent.py
from typing import Annotated, Literal
from typing_extensions import TypedDict
import operator

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

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
- If a student wants to book an appointment, collect their name, topic, and preferred time through conversation before calling the tool
- If a question is completely unrelated to UofT academics (e.g. cooking, sports, coding help), politely decline and redirect
- Always be friendly, encouraging, and professional
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