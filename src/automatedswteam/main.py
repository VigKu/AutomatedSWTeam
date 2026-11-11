# /// script
# dependencies = [
#     "langgraph>=0.1.0",
#     "langchain-core>=0.2.0",
#     "langchain-openai>=0.1.0",
#     "pydantic>=2.0.0",
#     "python-dotenv>=1.0.0",
# ]
# ///
"""
Module: main.py
Purpose: Main orchestrated entry point to select and run either Sequential or Asynchronous Parallel workflows with environment checks.
Owner: Lead Architect / DevOps Team
Depends on: graph, async_graph, observability, async_observability
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

def verify_environment() -> bool:
    """
    Performs pre-flight checks to ensure the .env file exists and key API tokens 
    are properly mapped into the running uv environment context.
    """
    print("[PRE-FLIGHT] Verifying runtime environment parameters...")
    
    env_path = Path(".env")
    if not env_path.exists():
        print(f"⚠️  WARNING: No local '.env' file detected at path: {env_path.resolve()}")
        print("   Will attempt to fall back onto system-level environment variables.")
    else:
        print(f"✅ Found environment layout manifest at: {env_path.resolve()}")
        load_dotenv(dotenv_path=env_path)

    # Verify key API credentials required by ChatOpenAI
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ CRITICAL ERROR: 'OPENAI_API_KEY' is missing or not exposed to the uv runtime ecosystem.")
        print("   Please map it in your configuration file or export it directly using:")
        print("   export OPENAI_API_KEY=\"your-key-here\"")
        return False
        
    if len(api_key.strip()) < 10 or api_key.startswith("your-"):
        print("❌ CRITICAL ERROR: 'OPENAI_API_KEY' appears to be a placeholder or corrupted string format.")
        return False

    print("✅ Environment check successful. API authorization tokens mapped correctly.\n")
    return True


async def run_sequential(prompt: str):
    """Orchestrates the synchronous sequential workflow compilation and invocation."""
    print("[ORCHESTRATOR] Initializing Synchronous Sequential Workflow Track...")
    try:
        # from langgraph.checkpoint.sqlite import SqliteSaver --> no longer exists
        from langgraph.checkpoint.memory import MemorySaver
        from .graph import workflow
        from .observability import save_observability_report
    except ImportError as err:
        print(f"ERROR: Failed to import synchronous workflow modules. {err}")
        sys.exit(1)

    config = {"configurable": {"thread_id": "sync-orchestrated-session"}}
    initial_state = {
        "user_prompt": prompt,
        "sendback_count": 0,
    }

    # db_path = "checkpoints.sqlite"
    print(f"[ORCHESTRATOR] Binding persistent checkpointer to in memory")
    
    # Initialize a synchronous in-memory checkpointer
    memory = MemorySaver()
    graph = workflow.compile(checkpointer=memory)
    print(f"[ORCHESTRATOR] Graph compiled successfully. Triggering pipeline execution...")
    graph.invoke(initial_state, config=config)
    
    current_snapshot = graph.get_state(config)
    print(f"[ORCHESTRATOR] Execution finished. Next Up node state: {current_snapshot.next}")

    report_path = save_observability_report(report_dir="report")
    print(f"[ORCHESTRATOR] Synchronous metrics analysis logged at: {report_path.resolve()}")


async def run_parallel_async(prompt: str):
    """Orchestrates the asynchronous parallel workflow compilation and invocation."""
    print("[ORCHESTRATOR] Initializing Asynchronous Parallel Workflow Track...")
    try:
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        from .async_graph import workflow
        from .async_observability import save_observability_report
    except ImportError as err:
        print(f"ERROR: Failed to import asynchronous parallel workflow modules. {err}")
        sys.exit(1)

    config = {"configurable": {"thread_id": "async-orchestrated-session"}}
    initial_state = {
        "user_prompt": prompt,
        "sendback_count": 0,
    }

    db_path = "checkpoints_async.sqlite"
    print(f"[ORCHESTRATOR] Binding asynchronous persistent checkpointer to sqlite:///{db_path}")

    #async with AsyncSqliteSaver.from_conn_string(f"sqlite:///{db_path}") as checkpointer:
    async with AsyncSqliteSaver.from_conn_string(db_path) as checkpointer:
        graph = workflow.compile(checkpointer=checkpointer)
        print(f"[ORCHESTRATOR] Async Graph compiled successfully. Initializing concurrent loops...")
        await graph.ainvoke(initial_state, config=config)
        
        current_snapshot = await graph.aget_state(config)
        print(f"[ORCHESTRATOR] Async Execution finished. Next Up node state: {current_snapshot.next}")

    report_path = save_observability_report(report_dir="report")
    print(f"[ORCHESTRATOR] Asynchronous metrics analysis logged at: {report_path.resolve()}")


def main():
    parser = argparse.ArgumentParser(
        description="AutomatedSWTeam Orchestration Manager: Unified Interface for Multi-Agent Software Development Systems."
    )
    
    parser.add_argument(
        "--mode",
        type=str,
        choices=["sequential", "parallel"],
        default="parallel",
        help="Specify the pipeline architecture mode to execute. Default is 'parallel'."
    )
    
    parser.add_argument(
        "--prompt",
        type=str,
        default="Build a full-stack todo app with React and FastAPI.",
        help="The specific product building feature statement/prompt for the autonomous engineering team."
    )

    args = parser.parse_args()

    print("=" * 60)
    print(f" AUTOMATED SOFTWARE DEVELOPMENT TEAM ORCHESTRATOR ")
    print(f" Target Mode   : {args.mode.upper()}")
    print(f" Custom Prompt : '{args.prompt}'")
    print("=" * 60)

    # Perform runtime verification before running logic blocks
    if not verify_environment():
        print("❌ Execution halted due to configuration errors.")
        sys.exit(1)

    if args.mode == "sequential":
        asyncio.run(run_sequential(args.prompt))
    elif args.mode == "parallel":
        asyncio.run(run_parallel_async(args.prompt))

if __name__ == "__main__":
    main()


### CMD line @AutomatedSWTeam\src\automatedswteam :
## 1. async:
# For frontier models:
# uv run python -m automatedswteam.main --mode parallel --prompt "Build a small stocks trading prototype using python and gradio. Ensure to have users to create account with name and buy and sell stocks APPLE, ADI, UCTT,MU, AMD, GOOGL, QCOM, META. Create a dummy api to call default prices from a text file and this is to be scalable in future and replaced with a live api. Create a readme file in workspace folder on the usage. Limit the number of files created and test cases. Focus on making the protoype work."
# For local models:
# uv run python -m automatedswteam.main --mode parallel --prompt "Build a small stocks trading prototype using python and gradio. Ensure to have users to create account with name and buy and sell stocks APPLE, ADI, UCTT,MU, AMD, GOOGL, QCOM, META. Create a dummy api to call default prices from a text file and this is to be scalable in future and replaced with a live api. Create a readme file in workspace folder on the usage. Limit the number of files created and test cases. Focus on writing full code and making the protoype work. Do not stop at just the comments in code files, write full logic code." 
## 2. sync:
# uv run python -m automatedswteam.main --mode sequential --prompt "Build a simple chat interface using React."
