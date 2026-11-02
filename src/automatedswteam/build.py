from .graph import graph

# Run the Graph with a configurable Thread Config
# When invoking or streaming the graph, provide a thread_id inside the config object. LangGraph uses the thread_id to index state checkpoints:

config = {"configurable": {"thread_id": "session-1"}}

initial_state = {
    "user_prompt": "Build a full-stack todo app with React and FastAPI.",
    "sendback_count": 0,
}

# Run the graph
final_state = graph.invoke(initial_state, config=config)