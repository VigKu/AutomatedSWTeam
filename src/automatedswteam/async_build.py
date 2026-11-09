"""
Module: async_build.py
Purpose: Asynchronous entry point to run the compiled graph.
Owner: DevOps / Execution Lead
Depends on: async_graph, observability
"""

import asyncio
from pathlib import Path
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from .async_graph import workflow
from .async_observability import save_observability_report


async def main():
    config = {"configurable": {"thread_id": "async-session-1"}}
    initial_state = {
        "user_prompt": "Build a full-stack todo app with React and FastAPI.",
        "sendback_count": 0,
    }

    # Open Async SQLite Checkpointer
    # async with AsyncSqliteSaver.from_conn_string("sqlite:///checkpoints.sqlite") as checkpointer:
    async with AsyncSqliteSaver.from_conn_string("checkpoints.sqlite") as checkpointer:
        graph = workflow.compile(checkpointer=checkpointer)

        # Execute Graph Asynchronously
        print("Starting asynchronous execution of graph...")
        final_state = await graph.ainvoke(initial_state, config=config)

        current_snapshot = await graph.aget_state(config)
        print("Current node next up:", current_snapshot.next)

    # Save metrics report
    report_path = save_observability_report(report_dir="report")
    print(f"Observability metrics report generated at {report_path.resolve()}")

    # Format state to text report
    text_lines = [
        "=== LANGGRAPH ASYNC FINAL STATE REPORT ===",
        f"Thread ID: {config['configurable']['thread_id']}",
        f"Next Node: {current_snapshot.next}",
        "=" * 40,
        "",
    ]

    for key, value in current_snapshot.values.items():
        text_lines.append(f"[{key.upper()}]")
        if isinstance(value, dict):
            for sub_k, sub_v in value.items():
                text_lines.append(f"  {sub_k}: {sub_v}")
        else:
            text_lines.append(f"  {value}")
        text_lines.append("")

    output_path = Path("final_state_async.txt")
    output_path.write_text("\n".join(text_lines), encoding="utf-8")
    print(f"Final state saved to {output_path.resolve()}")


if __name__ == "__main__":
    asyncio.run(main())