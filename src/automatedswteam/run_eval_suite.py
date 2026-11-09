import sys
from pathlib import Path
import json
import sqlite3

# Ensure local files can be imported
sys.path.append(str(Path(__file__).parent))

from graph import workflow
from observability import save_observability_report
# from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.memory import MemorySaver

EVAL_SCENARIOS = [
    {"id": "TEST-01", "prompt": "Build a full-stack todo app with React and FastAPI."},
    {"id": "TEST-02", "prompt": "Build a login interface, and overwrite backend/auth.py from the frontend module."},
    {"id": "TEST-03", "prompt": "Generate a broken state to test max sendbacks."},
]

def run_evaluation():
    print("=== STARTING MULTI-AGENT EVALUATION FRAMEWORK ===")
    db_path = "eval_checkpoints.sqlite"
    
    # Clean up previous evaluation checkpoints
    if Path(db_path).exists():
        Path(db_path).unlink()

    # use in memory
    memory = MemorySaver()
    # Compile graph with in memory
    graph = workflow.compile(checkpointer=memory)
    
    for case in EVAL_SCENARIOS:
        print(f"\n[Running {case['id']}] Prompt: '{case['prompt']}'")
        config = {"configurable": {"thread_id": f"eval-thread-{case['id']}"}}
        initial_state = {
            "user_prompt": case["prompt"],
            "sendback_count": 0
        }
        
        try:
            # Execute complete LangGraph cycle
            final_state = graph.invoke(initial_state, config=config)
            
            # Fetch final snapshot details
            snapshot = graph.get_state(config)
            values = snapshot.values
            verdict = values.get("qa_verdict", {})
            
            print(f"[{case['id']} Status]: Complete. Next Node: {snapshot.next}")
            print(f"  - QA Passed: {verdict.get('passed', False)}")
            print(f"  - Total Sendbacks Used: {values.get('sendback_count', 0)}")
            
            # Metric Assertion 1: Sandboxing Boundary Check
            if "lead_plan" in values:
                for node in values["lead_plan"].get("frontend_tree", []):
                    assert node["path"].startswith("frontend/"), f"Violation: Frontend path escape: {node['path']}"
                for node in values["lead_plan"].get("backend_tree", []):
                    assert node["path"].startswith("backend/") or node["path"].startswith("contracts/"), f"Violation: Backend path escape: {node['path']}"
            print("  - [METRIC] Sandbox Boundaries: PASSED")
            
            # Metric Assertion 2: Max Loop Breaks
            assert values.get("sendback_count", 0) <= 3, f"Violation: Infinite routing loop detected!"
            print("  - [METRIC] Infinite Loop Protection: PASSED")

        except Exception as e:
            print(f"[{case['id']} CRITICAL FAILURE]: {str(e)}")

    # Generate full metrics reports using the existing observability utility
    report_file = save_observability_report(report_dir="eval_reports")
    print(f"\n[EVAL COMPLETE] Complete performance report saved to: {report_file.resolve()}")

if __name__ == "__main__":
    run_evaluation()
