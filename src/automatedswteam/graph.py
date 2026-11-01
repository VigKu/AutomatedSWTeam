from .agents import lead_engineer, frontend_engineer, backend_engineer, qa_engineer, AgentState
from langgraph.graph import START, END, StateGraph

workflow = StateGraph(AgentState)

workflow.add_node("lead", lead_engineer)
workflow.add_node("frontend", frontend_engineer)
workflow.add_node("backend", backend_engineer)
workflow.add_node("qa", qa_engineer)

workflow.add_edge(START, "lead")
workflow.add_edge("lead", "frontend")
workflow.add_edge("frontend", "backend")
workflow.add_edge("backend", "qa")
workflow.add_edge("qa", END)

graph = workflow.compile()