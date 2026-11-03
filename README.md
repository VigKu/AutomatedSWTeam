# AutomatedSWTeam
Team of SW agents that can build prototypes with a user prompt.

An autonomous multi-agent software development system built with **LangGraph**, **LangChain**, and **OpenAI GPT-5.4-nano**. The system simulates a complete software engineering team—comprising a **Lead Engineer**, **Frontend Engineer**, **Backend Engineer**, and **QA Engineer**—to design, scaffold, implement, test, and refine full-stack applications in a sandboxed workspace.

## 📋 Table of Contents

1. [Architecture & Workflow](#architecture--workflow)

2. [Agent Roles & Responsibilities](#agent-roles--responsibilities)

3. [Key Features & Design Principles](#key-features--design-principles)

4. [File & Directory Structure](#file--directory-structure)

5. [Sandboxing & Security Model](#sandboxing--security-model)

6. [State Management & Observability](#state-management--observability)

7. [Installation & Setup](#installation--setup)

8. [Usage](#usage)

## 🏗 Architecture & Workflow

The orchestration logic is governed by a **LangGraph StateGraph** featuring dynamic conditional routing, state persistence via SQLite checkpointers, and cyclic send-back loops for quality assurance.

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
                           (Direct routing back to QA)

```

### Execution Flow

1. **Architecture & Planning (`lead_engineer`)**: Parses user requirements, specifies software architecture, sets shared API contracts (`contracts/api.md`), initializes `CODEMAP.json`/`CODEMAP.md`, and scaffolds workspace stub files.

2. **Frontend Implementation (`frontend_engineer`)**: Builds UI/UX code in `workspace/frontend/`.

3. **Backend Implementation (`backend_engineer`)**: Implements API endpoints, data models, and business logic in `workspace/backend/`.

4. **QA & Quality Control (`qa_engineer`)**: Executes unit/integration tests in `workspace/qa/`, checks documentation standards, and determines passing criteria:

   * **Pass**: State transitions to `END`.

   * **Fail (Send-back Count < 3)**: Routes back to either `frontend` or `backend` to fix failures.

   * **Fix Cycle**: Fixes applied by implementers return directly to `qa` to verify resolution.

   * **Max Send-backs Reached (`sendback_count >= 3`)**: Automatically terminates execution to avoid infinite loops.

## 👥 Agent Roles & Responsibilities

| Agent Role | Model / Tools | Directory Authority | Primary Responsibilities | 
| ----- | ----- | ----- | ----- | 
| **Lead Engineer** | Structured Output (`LeadPlan`) | Workspace-wide setup | • High-level application architecture.  • Defines shared API contracts (`contracts/api.md`).  • Generates `CODEMAP` index and stubs starting files. | 
| **Frontend Engineer** | Tool-bound Agent (`frontend_llm`) | `workspace/frontend/` (Write)  Workspace (Read) | • UI/UX interface implementation.  • Respects API contracts.  • Maintains top-of-file headers and JSDoc docstrings. | 
| **Backend Engineer** | Tool-bound Agent (`backend_llm`) | `workspace/backend/`  `workspace/contracts/` (Write)  Workspace (Read) | • Server logic, database schemas, and API handlers.  • Updates API contracts if changes occur.  • Maintains function docstrings. | 
| **QA Engineer** | Tool-bound Agent (`qa_llm`) + Structured Output (`QAVerdict`) | `workspace/qa/` (Write)  Workspace (Read) | • Runs verification test scripts via command line tool.  • Checks code style rules and header compliance.  • Issues verdicts (`passed`, `next_agent`, feedback). | 

## 🌟 Key Features & Design Principles

* **Role-Based Workspace Sandboxing**: Agents are restricted at runtime to their respective subdirectories. `frontend_engineer` cannot modify `backend/` files, preventing unwanted scope creep or code corruption across agents.

* **CODEMAP File Indexing**: Centralized code map (`CODEMAP.json` / `CODEMAP.md`) maintains module path references, purpose statements, exports, and dependencies across all folders.

* **Strict Code Documentation Enforcement**: QA fails builds if code files lack file headers (`Module`, `Purpose`, `Owner`, `Depends on`) or function docstrings (`Args`/`Returns` or JSDoc `@param`/`@returns`).

* **Persistent Checkpointing**: State is persisted at every transition step using LangGraph's `SqliteSaver` (`checkpoints.sqlite`), allowing time-travel debugging and session recovery.

* **Custom Observability**: Embedded metrics tracker records agent call counts, execution durations, pass/fail status, and send-back metrics, saving structured JSON reports post-execution.

## 📁 File & Directory Structure

```
.
├── agents.py           # Agent node functions, prompt templates, and Pydantic schemas
├── build.py            # Execution entry point, graph invocation, and report export
├── graph.py            # LangGraph workflow definition and dynamic routing logic
├── observability.py    # Execution performance tracking and JSON report generation
├── tools.py            # Sandboxed filesystem, indexing, and shell tool implementations
├── checkpoints.sqlite  # SQLite database holding state snapshots (generated at runtime)
├── final_state.txt     # Human-readable state summary output (generated post-run)
├── workspace/          # Isolated root directory for agent project generation
│   ├── CODEMAP.json    # Machine-readable workspace index
│   ├── CODEMAP.md      # Human-readable workspace index
│   ├── contracts/      # Shared API contracts (e.g., api.md)
│   ├── frontend/       # Frontend implementation code
│   ├── backend/        # Backend implementation code
│   └── qa/             # Test files and test runners
└── report/             # Execution metrics JSON reports directory

```

## 🔒 Sandboxing & Security Model

The system employs file isolation and safety checks within `tools.py`:

1. **Path Resolution**: Relative paths are forced to resolve inside `workspace/`. Attempts to traverse upward using relative paths (`../`) or absolute path tricks trigger `ValueError("Path is outside the workspace.")`.

2. **Directory Ownership Restrictions**:

   * `frontend`: Read/Write `frontend/`; Read-only `backend/`, `contracts/`, `qa/`.

   * `backend`: Read/Write `backend/`, `contracts/`; Read-only `frontend/`, `qa/`.

   * `qa`: Read/Write `qa/`; Read-only `frontend/`, `backend/`, `contracts/`.

3. **Execution Limits**: Shell commands issued by `run_command` are scoped to the agent's folder, locked against parent directory traversal (`..`), and subject to a strict 60-second timeout.

4. **Content Limits**: Text file reading and shell command outputs are truncated at 40,000 and 8,000 characters respectively to keep LLM context sizes within bounds.

## 📊 State Management & Observability

### Agent State Schema (`AgentState`)

```
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

### Metrics Reporting

Every agent execution decorated with `@track_agent` outputs performance metadata. Upon workflow completion, `save_observability_report()` produces a report formatted like:

```
{
  "summary": {
    "total_execution_time_sec": 42.15,
    "total_agent_calls": 5,
    "agent_breakdown": {
      "lead_engineer": { "calls": 1, "total_time_sec": 4.1, "failures": 0 },
      "frontend_engineer": { "calls": 2, "total_time_sec": 18.2, "failures": 0 },
      "backend_engineer": { "calls": 1, "total_time_sec": 9.5, "failures": 0 },
      "qa_engineer": { "calls": 2, "total_time_sec": 10.35, "failures": 0 }
    }
  },
  "detailed_logs": [...]
}

```

## ⚡ Installation & Setup

### Prerequisites

* Python 3.10 or higher

* OpenAI API Key configured in your environment

### Environment Setup

1. **Clone the Repository**:

   ```
   git clone https://github.com/your-org/automated-software-team.git
   cd automated-software-team
   
   ```

2. **Install Dependencies**:

   ```
   pip install langgraph langchain-core langchain-openai pydantic
   OR
   uv sync
   
   ```

3. **Set API Key**:

   ```
   export OPENAI_API_KEY="your-api-key-here" OR use load dot env
   
   ```

## 🚀 Usage

### Running the System

To launch the multi-agent workflow, execute `build.py`:

```
python build.py

```

### Customizing Prompts

You can change the target task inside `build.py` by modifying `initial_state`:

```
initial_state = {
    "user_prompt": "Build a full-stack real-time collaborative note-taking app with FastHTML and SQLite.",
    "sendback_count": 0,
}

```

### Inspecting Execution Artifacts

After execution completes, you can inspect:

* **Project Output**: `workspace/` folder contains generated code across `frontend/`, `backend/`, and `qa/`.

* **State Report**: `final_state.txt` displays human-readable output of all state keys.

* **Metrics**: `report/agent_observability_<timestamp>.json` gives precise timing and call-count metrics.

* **Checkpoints**: `checkpoints.sqlite` can be queried directly via SQLite CLI to inspect historical snapshots:

  ```
  sqlite3 checkpoints.sqlite "SELECT checkpoint_id, type FROM checkpoints;"
  
  ```
