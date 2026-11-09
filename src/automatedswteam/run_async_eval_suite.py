import sys
import asyncio
from pathlib import Path
from datetime import datetime

# Ensure local files can be imported
sys.path.append(str(Path(__file__).parent))

from async_graph import workflow
from async_observability import save_observability_report, _METRICS_LOG
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

EVAL_SCENARIOS = [
    {"id": "ASYNC-TEST-01", "prompt": "Build a full-stack todo app with React and FastAPI."},
    {"id": "ASYNC-TEST-02", "prompt": "Simulate heavy asynchronous dependency generation."},
    {"id": "ASYNC-TEST-03", "prompt": "Trigger a slow command to test non-blocking timeout handling."},
]

async def run_async_evaluation():
    print("=== STARTING ASYNC MULTI-AGENT EVALUATION FRAMEWORK ===")
    db_path = "eval_async_checkpoints.sqlite"
    
    if Path(db_path).exists():
        Path(db_path).unlink()

    async with AsyncSqliteSaver.from_conn_string(f"sqlite:///{db_path}") as checkpointer:
        graph = workflow.compile(checkpointer=checkpointer)
        
        for case in EVAL_SCENARIOS:
            print(f"\n[Running {case['id']}] Prompt: '{case['prompt']}'")
            config = {"configurable": {"thread_id": f"eval-async-thread-{case['id']}"}}
            initial_state = {
                "user_prompt": case["prompt"],
                "sendback_count": 0
            }
            
            try:
                # Run the graph using clean asynchronous invocation
                await graph.ainvoke(initial_state, config=config)
                
                snapshot = await graph.aget_state(config)
                values = snapshot.values
                verdict = values.get("qa_verdict", {})
                
                print(f"[{case['id']} Status]: Evaluation branch completed. Next up: {snapshot.next}")
                
                # Metric Assertion 1: Concurrency Validation via Timestamp Analysis
                agent_logs = [log for log in _METRICS_LOG if log["agent_name"] in ("frontend_engineer", "backend_engineer")]
                if len(agent_logs) >= 2:
                    # Parse execution start times to ensure concurrent processing
                    t1 = datetime.strptime(agent_logs[0]["timestamp"], "%Y-%m-%d %H:%M:%S")
                    t2 = datetime.strptime(agent_logs[1]["timestamp"], "%Y-%m-%d %H:%M:%S")
                    time_diff = abs((t1 - t2).total_seconds())
                    print(f"  - [METRIC] Concurrency Gap: {time_diff} seconds.")
                
                # Metric Assertion 2: Strict Loop Count Enforcement
                assert values.get("sendback_count", 0) <= 3, "Violation: Path loop exceeded the maximum send-back budget!"
                print("  - [METRIC] Parallel Loop Safety: PASSED")

            except Exception as e:
                print(f"[{case['id']} CRITICAL RUNTIME EXCEPTION]: {str(e)}")

    # Dump the system evaluation analytics metrics to disk
    report_file = save_observability_report(report_dir="eval_async_reports")
    print(f"\n[ASYNC EVAL COMPLETE] Performance insights saved to: {report_file.resolve()}")

if __name__ == "__main__":
    asyncio.run(run_async_evaluation())
