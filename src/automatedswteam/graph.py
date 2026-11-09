from .agents import lead_engineer, frontend_engineer, backend_engineer, qa_engineer, AgentState
from langgraph.graph import START, END, StateGraph
from langgraph.checkpoint.memory import MemorySaver


def route_after_frontend(state: AgentState) -> str:
    # First pass still goes through backend. QA send-backs return to QA only.
    if state.get("sendback_count", 0) == 0:
        return "backend"
    return "qa"


def route_after_qa(state: AgentState) -> str:
    next_agent = (state.get("qa_verdict") or {}).get("next_agent", "end")
    if next_agent in ("frontend", "backend"):
        return next_agent
    return "end"

# Initialize in-memory checkpointer
checkpointer = MemorySaver()

workflow = StateGraph(AgentState)

workflow.add_node("lead", lead_engineer)
workflow.add_node("frontend", frontend_engineer)
workflow.add_node("backend", backend_engineer)
workflow.add_node("qa", qa_engineer)

workflow.add_edge(START, "lead")
workflow.add_edge("lead", "frontend")
workflow.add_conditional_edges(
    "frontend",
    route_after_frontend,
    {"backend": "backend", "qa": "qa"},
)
workflow.add_edge("backend", "qa")
workflow.add_conditional_edges(
    "qa",
    route_after_qa,
    {"frontend": "frontend", "backend": "backend", "end": END},
)

# graph = workflow.compile(checkpointer=checkpointer)

# # Initialize SQLite checkpointer context manager or instance
# # Use from_conn_string to establish a persistent SQLite connection
# with SqliteSaver.from_conn_string("sqlite:///checkpoints.sqlite") as checkpointer:
#     graph = workflow.compile(checkpointer=checkpointer)
