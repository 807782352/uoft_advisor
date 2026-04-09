# app.py
import chainlit as cl

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from agent import build_agent, chat

# Run this code to start: python -m chainlit run app.py -w

# ============================================================
# Initialize agent on startup
# ============================================================

@cl.on_chat_start
async def on_chat_start():
    agent = build_agent()
    cl.user_session.set("agent", agent)
    cl.user_session.set("history", [])

    await cl.Message(
        content=(
            "Hello! I'm your **UofT Academic Advisor** 🎓\n\n"
            "I can help you with:\n"
            "- 📚 Program requirements and course information\n"
            "- 💡 Personalized program recommendations\n"
            "- 📅 Booking an appointment with an academic advisor\n\n"
            "What can I help you with today?"
        )
    ).send()

# ============================================================
# Handle incoming messages
# ============================================================

@cl.on_message
async def on_message(message: cl.Message):
    """
    Called every time the user sends a message.
    """
    agent   = cl.user_session.get("agent")
    history = cl.user_session.get("history")

    # Show a loading indicator while processing
    async with cl.Step(name="Thinking..."):
        response, updated_history = chat(agent, message.content, history)

    # Save updated history
    cl.user_session.set("history", updated_history)

    # Send response
    await cl.Message(content=response).send()