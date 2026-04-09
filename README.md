# UofT Academic Advisor Agent

An AI-powered conversational academic advisor for the University of Toronto,
built with LangChain, LangGraph, and Chainlit.

---

## Overview

This agent helps prospective and current UofT students with:
- **Program Information** — enrolment requirements, completion requirements
- **Program Recommendations** — personalized suggestions based on student profile
- **Course Planning** — course requirements for specific programs
- **Advisor Appointments** — mock booking with a UofT academic advisor

---

## Architecture
```
 User Query
    ↓
    Chainlit Interface (app.py)
    ↓
    LangGraph Agent (agent.py)
    ↓ intent classification + tool routing
    ├── search_programs   → RAG Pipeline → FAISS Vector Store
    ├── recommend_programs → RAG + LLM reasoning
    └── book_advisor_appointment → Multi-turn conversation
```

---

## Tech Stack

```
| Component | Technology |
|---|---|
| LLM | qwen3-30b-a3b-fp8 (course endpoint) |
| Embeddings | text-embedding-3-small (course A2 endpoint) |
| Vector Store | FAISS |
| Agent Framework | LangGraph |
| LLM Integration | LangChain |
| UI | Chainlit |
| Language | Python 3.11 |
```

---

## Project Structure
```
uoft_advisor/
├── app/
│   ├── agent.py              # LangGraph agent + graph definition
│   ├── app.py                # Chainlit UI entry point
│   ├── build_vectorstore.py  # Build and load FAISS index
│   ├── config.py             # LLM and embeddings configuration
│   ├── rag.py                # RAG pipeline
│   ├── scraper.py            # UofT calendar web scraper
│   └── tools.py              # Agent tools (search, recommend, book)
├── data/
│   └── knowledge_base.json   # Scraped UofT program data (476 records)
├── faiss_index/              # Saved FAISS vector store
├── test/
│   ├── results/              # Evaluation outputs
│   ├── evaluation.py         # Automated test suite (15 test cases)
│   └── test_*.py             # Unit tests per module
├── requirements.txt
└── README.md
```
---

## Setup Instructions

### 1. Clone the repository
```bash
git clone <repo_url>
cd uoft_advisor
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure API endpoints

Edit `app/config.py` and set your student ID:
```python
STUDENT_ID = "your_student_id"
```

### 4. Build the vector store
```bash
python app/build_vectorstore.py
```

### 5. Run the app
```bash
python -m chainlit run app/app.py -w
```

Open `http://localhost:8000` in your browser.

---

## Knowledge Base

- **Source**: UofT Arts & Science Academic Calendar
  (`artsci.calendar.utoronto.ca`)
- **Size**: 476 program records across 88 departments
- **Coverage**: Specialist, Major, Minor, Certificate, Focus programs
- **Fields**: program name, code, type, department, introduction,
  enrolment requirements, completion requirements

---

## Agent Capabilities

### 1. Knowledge Q&A with Source Attribution
Answers questions using RAG retrieval, citing the source program and department.

### 2. Program Recommendation
Analyzes student profile (interests, strengths, goals) and recommends
suitable UofT programs with explanations.

### 3. Course Planning
Retrieves specific course requirements and credit breakdowns for any program.

### 4. Advisor Appointment Booking (Multi-turn)
Collects student name, topic, and preferred time across multiple conversation
turns before confirming the booking.

### 5. Guardrails
- Rejects out-of-scope questions (e.g. coding help, weather)
- Handles prompt injection attempts
- Acknowledges when information is not in the knowledge base
- Never fabricates contact information

---

## Evaluation Results

**15 test cases** covering all required capability areas:
```
| Category | Score |
|---|---|
| RAG Knowledge Q&A | 4/4 |
| Program Recommendation | 1/2 |
| Course Planning | 1/2 |
| Appointment Booking | 2/2 |
| Out-of-Scope Rejection | 2/2 |
| Not in Knowledge Base | 2/2 |
| Prompt Injection | 1/1 |
| **Total** | **13/15 (86%)** |
```

### Failure Analysis
- **Program Recommendation (Test 6)**: Agent retrieves relevant programs
  but occasionally prioritizes less specific matches when query is broad.
- **Course Planning (Test 8)**: RAG retrieves correct document but
  response focuses on introduction rather than specific course codes.

### Known Limitations
- Knowledge base covers Arts & Science programs only (UTSG campus)
- Course-level details (individual course descriptions) not included
- Appointment booking is simulated, not connected to a real system

---

## Data Collection

UofT program data was scraped using `scraper.py`:
```bash
python app/scraper.py          # Scrape all programs
python app/scraper.py --test   # Test with first 5 pages only
```

The scraper uses printer-friendly versions of the Academic Calendar
for the most complete content.

---

## Dependencies

See `requirements.txt` for full list. Key libraries:

- `langchain`, `langchain-openai`, `langchain-community`
- `langgraph`
- `chainlit`
- `faiss-cpu`
- `beautifulsoup4`, `requests`