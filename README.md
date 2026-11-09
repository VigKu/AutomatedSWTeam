# AutomatedSWTeam
Team of SW agents that can build prototypes with a user prompt.

An autonomous multi-agent software development system built with **LangGraph**, **LangChain**, and **OpenAI GPT-5.4-nano**. The system simulates a complete software engineering team—comprising a **Lead Engineer**, **Frontend Engineer**, **Backend Engineer**, and **QA Engineer**—to design, scaffold, implement, test, and refine full-stack applications in a sandboxed workspace.

The system natively supports **dual operational modes**: a traditional **Synchronous Sequential Workflow** for predictable step-by-step optimization and an advanced **Asynchronous Parallel Fan-Out Workflow** utilizing concurrent I/O tool loops, isolated context tracking, and async SQLite checkpoints.

## 📋 Table of Contents

1. [Architecture & Workflows](#architecture--workflows)
   * [Synchronous Sequential Track](#1-synchronous-sequential-track)
   * [Asynchronous Parallel Track](#2-asynchronous-parallel-track)
2. [Agent Roles & Responsibilities](#agent-roles--responsibilities)
3. [Key Features & Design Principles](#key-features--design-principles)
4. [File & Directory Structure](#file--directory-structure)
5. [Sandboxing & Security Model](#sandboxing--security-model)
6. [State Management & Observability](#state-management--observability)
7. [Installation & Setup](#installation--setup)
8. [Usage](#usage)

---

## 🏗 Architecture & Workflows

The system architecture features dual orchestration execution pathways configured through distinct LangGraph topology definitions.

### 1. Synchronous Sequential Track
In this track, agents operate linearly. The system fully explores frontend implementations before introducing integration points to the backend sub-agent.

```
                  ┌────────────────────────┐
                  │        START           │
                  └───────────┬────────────┘
                              │
                              ▼
                  ┌────────────────────────┐
                  │     Lead Engineer      │
                  │(Architecture & Index)  │
                  └───────────┬────────────┘
                              │
                              ▼
                  ┌────────────────────────┐
                  │    Frontend Engineer   │
                  │   (UI/UX Development)  │
                  └───────────┬────────────┘
                              │
                    (Initial execution)
                              │
                              ▼
                  ┌────────────────────────┐
                  │    Backend Engineer    │
                  │ (APIs & Server Logic)  │
                  └───────────┬────────────┘
                              │
                              ▼
                  ┌────────────────────────┐
                  │      QA Engineer       │◄───────────────────────┐
                  │(Testing & Inspection)  │                        │
                  └───────────┬────────────┘                        │
                              │                                     │
                      [Evaluate Verdict]                            │
                              │                                     │
           ┌──────────────────┼─────────────────────┐               │
           │                  │                     │               │
    (Passed / End)     (Fix Frontend)        (Fix Backend)          │
           │                  │                     │               │
           ▼                  ▼                     ▼               │
        ┌─────┐     ┌────────────────────┐  ┌────────────────────┐  │
        │ END │     │ Frontend Fix Loop  │  │ Backend Fix Loop   │──┘
        └─────┘     └────────────────────┘  └────────────────────┘
```

### 2. Asynchronous Parallel Track
In this track, the lead engineer's plans are forked concurrently. Frontend and backend developers design their functional units in parallel using non-blocking execution mechanisms, merging together at a shared QA join gate.

```
                  ┌────────────────────────┐
                  │        START           │
                  └───────────┬────────────┘
                              │
                              ▼
                  ┌────────────────────────┐
                  │  Lead Engineer (Async) │
                  │(Architecture & Index)  │
                  └───────────┬────────────┘
                              │
                ┌─────────────┴─────────────┐
                │ (Parallel Fan-Out Fork)   │
                ▼                           ▼
    ┌──────────────────────┐    ┌──────────────────────┐
    │  Frontend Engineer   │    │   Backend Engineer   │
    │ (Async UI/UX Dev)    │    │ (Async Server Logic) │
    └───────────┬──────────┘    └───────────┬──────────┘
                │                           │
                └─────────────┬─────────────┘
                              │ (Parallel Fan-In Join)
                              ▼
                  ┌────────────────────────┐
                  │   QA Engineer (Async)  │◄───────────────────────┐
                  │(Testing & Inspection)  │                        │
                  └───────────┬────────────┘                        │
                              │                                     │
                      [Evaluate Verdict]                            │
                              │                                     │
           ┌──────────────────┼─────────────────────┐               │
           │                  │                     │               │
    (Passed / End)     (Fix Frontend)        (Fix Backend)          │
           │                  │                     │               │
           ▼                  ▼                     ▼               │
        ┌─────┐     ┌────────────────────┐  ┌────────────────────┐  │
        │ END │     │ Frontend Fix Loop  │  │ Backend Fix Loop   │──┘
        └─────┘     └────────────────────┘  └────────────────────┘
```

---

## 👥 Agent Roles & Responsibilities

| Agent Role | Model / Tools | Directory Authority | Primary Responsibilities |
| :--- | :--- | :--- | :--- |
| **Lead Engineer** | Structured Output (`LeadPlan`) | Workspace-wide setup | • High-level application architecture.<br>• Defines shared API contracts (`contracts/api.md`).<br>• Generates `CODEMAP` file tree indexes. |
| **Frontend Engineer** | Tool-bound Agent | `workspace/frontend/` (Write)<br>Workspace (Read) | • UI/UX interface implementation.<br>• Respects API contracts.<br>• Complies with top-of-file header conventions. |
| **Backend Engineer** | Tool-bound Agent | `workspace/backend/`<br>`workspace/contracts/` (Write)<br>Workspace (Read) | • Server logic, database schemas, and API handlers.<br>• Updates API contracts if changes occur. |
| **QA Engineer** | Agent + Structured Verdict | `workspace/qa/` (Write)<br>Workspace (Read) | • Runs verification test scripts via command tools.<br>• Verifies code documentation standards.<br>• Issues structural routing verdicts. |

---

## 🌟 Key Features & Design Principles

* **Dual Core Architectures**: Seamlessly choose between a predictable, linear multi-agent sequence or a concurrent, parallel execution matrix depending on environment infrastructure profiles.
* **Role-Based Workspace Sandboxing**: Path enforcement keeps agents bound strictly within their assigned working roots. The frontend branch cannot overwrite the backend layout, eliminating unintended cross-contamination risks.
* **Non-Blocking Async Tool Extension**: Asynchronous file system read/write layers delegate disk interactions to workers using `asyncio.to_thread`. Shell interactions utilize `asyncio.create_subprocess_shell` configurations.
* **Context-Isolated Token Observability**: Uses `ContextVar` metrics hooks to ensure exact prompt and completion token tracking without data leaks across multi-threaded or concurrent graph loops.
* **Persistent Checkpointing**: State is safely captured during execution steps using either standard `SqliteSaver` or async `AsyncSqliteSaver` database configurations.

---

## 📁 File & Directory Structure

```
.
├── agents.py              # Synchronous agent nodes, prompt templates, and Pydantic schemas
├── build.py               # Synchronous entry point, sequential invocation, and metrics exporter
├── graph.py               # Synchronous LangGraph workflow definition and sequential routing
├── tools.py               # Shared utility operations, path sandboxing, and sync tool targets
│
├── async_agents.py        # Asynchronous agent nodes, tool loops, and prompt engines
├── async_build.py         # Asynchronous entry point, parallel runtime, and text reporter
├── async_graph.py         # LangGraph workflow definition and parallel forking layout
├── async_observability.py # ContextVar token-safe execution tracking engine
├── async_tools.py         # Sandboxed non-blocking async file and subprocess tools
│
├── checkpoints.sqlite     # SQLite database capturing runtime state snapshots
├── final_state.txt        # Human-readable sync state summary output
├── final_state_async.txt  # Human-readable async state summary output
├── workspace/             # Isolated root directory for agent project generation
│   ├── CODEMAP.json       # Machine-readable workspace index
│   ├── CODEMAP.md         # Human-readable workspace index
│   ├── contracts/         # Shared API contracts (e.g., api.md)
│   ├── frontend/          # Frontend implementation code
│   ├── backend/           # Backend implementation code
│   └── qa/                # Test files and test runners
└── report/                # Execution metrics JSON reports directory
```

---

## 🔒 Sandboxing & Security Model

The runtime security layout remains strictly enforced across both tool pathways:

1. **Path Resolution**: Relative paths are forced to resolve inside `workspace/`. Traversal anomalies (`../`) trigger instant `ValueError` exceptions.
2. **Directory Ownership Restrictions**:
   * `frontend`: Read/Write `frontend/`; Read-only `backend/`, `contracts/`, `qa/`.
   * `backend`: Read/Write `backend/`, `contracts/`; Read-only `frontend/`, `qa/`.
   * `qa`: Read/Write `qa/`; Read-only `frontend/`, `backend/`, `contracts/`.
3. **Execution Safety**: Shell operations run inside localized working directories (`cwd`), prohibit parent path modifiers (`..`), and are bound to a strict 60-second execution cutoff. If an async cutoff is reached, the subsystem forces process pruning (`proc.kill()`) to clean up resources.

---

## 📊 State Management & Observability

### Agent State Schema (`AgentState`)

```python
class AgentState(TypedDict):
    user_prompt: str          # Raw task instruction from user
    lead_plan: dict           # Scaffolding and architecture plan from Lead
    frontend_plan: str        # Execution plan summary from Frontend agent
    backend_plan: str         # Execution plan summary from Backend agent
    qa_plan: str              # Test strategy plan from QA agent
    qa_verdict: dict          # Structured QA output (passed, next_agent, feedback)
    qa_feedback: str          # Actionable feedback for send-back loops
    error_log: str            # Collected errors during build
    test_results: str         # Captured output from execution of tests
    sendback_count: int       # Send-back counter (Max: 3)
    workspace_root: str       # Physical path to target project directory
    codemap: str              # Current Markdown contents of CODEMAP.md
```

---

## ⚡ Installation & Setup

### Prerequisites

* Python 3.10 or higher
* OpenAI API Key configured in your environment

### Environment Setup

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/your-org/automated-software-team.git
   cd automated-software-team
   ```

2. **Install Dependencies**:
   ```bash
   pip install langgraph langchain-core langchain-openai pydantic python-dotenv
   # OR if using uv:
   uv sync
   ```

3. **Configure Environment Variables**:
   Create a `.env` file in the root directory:
   ```env
   OPENAI_API_KEY="your-api-key-here"
   ```

---

## 🚀 Usage

### Option A: Running the Synchronous Sequential System
To launch the traditional sequential architecture execution loop, run the following:
```bash
python build.py
```

### Option B: Running the Asynchronous Parallel System
To execute the high-throughput parallel execution map using async primitives, run the following:
```bash
python async_build.py
```

### Customizing System Target Prompts
You can modify the product building goal inside the respective build launcher files (`build.py` or `async_build.py`) by adjusting the `initial_state` input object:
```python
initial_state = {
    "user_prompt": "Build a full-stack real-time collaborative note-taking app with FastHTML and SQLite.",
    "sendback_count": 0,
}
```