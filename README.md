# Follow-Up Agent

## Overview
Follow-Up Agent is an intelligent, semantic assistant designed for "zero-chase execution." It acts as a resilient state machine that automatically tracks pending tasks, drafts context-aware follow-up messages, parses incoming replies, and manages escalations so you never have to manually chase a thread again.

## Key Features

- **Intelligent Lifecycle Tracking**: Automatically tracks tasks through dynamic visual stages (`Created` → `Waiting` → `Follow Up 1` → `Follow Up 2` → `Escalated`/`Closed`).
- **Resilient State Machine**: Built using LangGraph to reliably evaluate schedules, assess thread context via LLMs, and safely transition entities between states.
- **Zero-Chase Execution**: 
  - Generates accurate draft messages automatically via LLM integration (Gemini).
  - Automatically assesses incoming threads (pauses intelligently when it detects Out-of-Office responses, and closes loops upon standard replies).
- **Flexible Action Modes**:
  - **Mode A (Approval Required)**: Drafts are prepared and strictly await human review before dispatch.
  - **Mode B (Draft Only)**: Operates purely as an assistant without dispatching.
  - **Mode C (Auto Send)**: Fully automated execution once specific validations traverse the graph successfully.
- **Deep Explainability**: Every task features an "Explain" timeline, providing a comprehensive audit trail of exactly *why* a draft was produced or a task was escalated.
- **Customizable Rescheduling**: Exposes granular controls to manually edit `next_follow_up_at` times without disrupting the background scheduler.

## Tech Stack
- **Backend**: Python, FastAPI, LangGraph, Supabase (PostgreSQL).
- **Frontend**: React, Vite, Axios.
- **AI/LLM**: Google Gemini.

## Getting Started

### Prerequisites
- Python 3.9+ 
- Node.js & npm
- Supabase account & credentials

### 1. Running the Backend
The backend utilizes FastAPI and Python modules. Run it from the root of the project to ensure correct Python pathing.
```bash
# Install dependencies
pip install -r backend/requirements.txt

# Start the FastAPI server (Runs on http://localhost:8000)
uvicorn backend.api.main:app --reload
```

### 2. Running the Frontend
The frontend is a fast React application powered by Vite.
```bash
cd frontend

# Install packages
npm install

# Start the local development server (Runs on http://localhost:5173)
npm run dev
```

### 3. Running Tests
To run the automated suite of backend tests properly, run `pytest` as a Python module from the project root.
```bash
python -m pytest backend/tests
```

## Dashboard Components
- **Pending**: View tasks that require your immediate approval or action.
- **Overdue**: View tasks that have passed their deadline but have not been followed up properly.
- **Report & Escalations**: Read detailed summaries highlighting blockers and entirely escalated tasks.
- **Active Follow-Ups**: Ensure visibility on all running tasks, check how long it's been since the last sent communication, and track graphical progress bars.
- **Create New**: Manually onboard a semantic task directly into the agent.
