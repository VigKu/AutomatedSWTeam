"""
Module: async_graph.py
Purpose: Defines and compiles the asynchronous parallel LangGraph workflow.
Owner: Lead Architect
Depends on: async_agents
"""

from typing import List
from langgraph.graph import START, END, StateGraph
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from .async_agents import (
    lead_engineer_async,
    frontend_engineer_async,
    backend_engineer_async,
    qa_engineer_async,
    AgentState,
)

def route_after_qa(state: AgentState) -> List[str] | str:
    """
    Conditional edge function for QA routing.
    Returns a list of node names for parallel execution or a single node string.
    """
    verdict = state.get("qa_verdict", {})
    next_agent = verdict.get("next_agent", "end")

    if next_agent == "both":
        return ["frontend", "backend"]  # Parallel execution matching node names
    elif next_agent == "frontend":
        return "frontend"
    elif next_agent == "backend":
        return "backend"
    else:
        return "end"


workflow = StateGraph(AgentState)

# Add async nodes
workflow.add_node("lead", lead_engineer_async)
workflow.add_node("frontend", frontend_engineer_async)
workflow.add_node("backend", backend_engineer_async)
workflow.add_node("qa", qa_engineer_async)

# Fork lead output into BOTH frontend and backend in parallel
workflow.add_edge(START, "lead")
workflow.add_edge("lead", "frontend")
workflow.add_edge("lead", "backend")

# Fan-in: both frontend and backend edge into qa
workflow.add_edge("frontend", "qa")
workflow.add_edge("backend", "qa")

# QA handles conditional feedback iteration
workflow.add_conditional_edges(
    "qa",
    route_after_qa,
    {"frontend": "frontend", "backend": "backend", "end": END},
)