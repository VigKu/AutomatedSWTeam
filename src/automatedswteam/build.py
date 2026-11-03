from langgraph.checkpoint.sqlite import SqliteSaver
from .graph import workflow
from .observability import save_observability_report

# Run the Graph with a configurable Thread Config
# When invoking or streaming the graph, provide a thread_id inside the config object. LangGraph uses the thread_id to index state checkpoints:

config = {"configurable": {"thread_id": "session-1"}}

initial_state = {
    "user_prompt": "Build a full-stack todo app with React and FastAPI.",
    "sendback_count": 0,
}

# # Run the graph
# final_state = graph.invoke(initial_state, config=config)

#1. Open SQLite checkpointer context
with SqliteSaver.from_conn_string("sqlite:///checkpoints.sqlite") as checkpointer:
    # Compile graph with active SQLite checkpointer
    graph = workflow.compile(checkpointer=checkpointer)

    # Run the graph
    final_state = graph.invoke(initial_state, config=config)

    # Inspect state or resume from a checkpoint
    current_snapshot = graph.get_state(config)
    print("Current node next up:", current_snapshot.next)

# Save observability metrics locally
report_path = save_observability_report(report_dir="report")
print(f"Observability metrics report generated at {report_path.resolve()}")
    
# 2. Format state values into readable plain text
text_lines = [
    f"=== LANGGRAPH FINAL STATE REPORT ===",
    f"Thread ID: {config['configurable']['thread_id']}",
    f"Next Node: {current_snapshot.next}",
    f"Checkpoint ID: {current_snapshot.config['configurable'].get('checkpoint_id', 'N/A')}",
    "=" * 40,
    "",
]

# Iterate through state values and append formatted sections
for key, value in current_snapshot.values.items():
    text_lines.append(f"[{key.upper()}]")
    if isinstance(value, dict):
        for sub_k, sub_v in value.items():
            text_lines.append(f"  {sub_k}: {sub_v}")
    else:
        text_lines.append(f"  {value}")
    text_lines.append("")

formatted_text = "\n".join(text_lines)

# 3. Save to a local text file
output_path = Path("final_state.txt")
output_path.write_text(formatted_text, encoding="utf-8")

print(f"Final state text report saved to {output_path.resolve()}")

# # Get the Latest State

# current_snapshot = graph.get_state(config)

# print("Current node next up:", current_snapshot.next)
# print("Latest state values:", current_snapshot.values)



# # Retrieve Full Execution History (Past Checkpoints)
# # To step back through time and view how the state evolved node-by-node:

# # Iterate through all state history for this thread
# for history_item in graph.get_state_history(config):
#     print("Checkpoint ID:", history_item.config["configurable"]["checkpoint_id"])
#     print("Metadata (node that ran):", history_item.metadata)
#     print("State values at this step:", history_item.values)
#     print("-" * 50)


# # Time Travel / Replay from a Specific Historic Checkpoint
# # If you want to resume or re-run execution starting from an earlier checkpoint, pass the historical config (which contains the specific checkpoint_id) back into graph.invoke():

# # Select a historic state checkpoint from the history loop
# history = list(graph.get_state_history(config))
# past_checkpoint_config = history[-2].config  # e.g., state after the 'lead' node

# # Re-run execution starting from that historic point
# new_result = graph.invoke(None, config=past_checkpoint_config)


# # 3. Direct SQL Querying (Optional)
# # If you want to inspect the raw database outside of LangGraph using SQLite CLI or a database viewer like DB Browser for SQLite:

# sqlite3 checkpoints.sqlite "SELECT checkpoint_id, type, blob FROM checkpoints;"