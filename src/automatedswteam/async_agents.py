"""
Module: async_agents.py
Purpose: Asynchronous agent nodes and tool loop execution.
Owner: Lead Architect
Depends on: tools, observability
"""

import os
import logging
from typing import List, TypedDict, Literal, Optional, Annotated, Any
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, ToolMessage
from pydantic import BaseModel, Field, SecretStr

from .tools import (
    CodeNode,
    get_workspace_root,
    #make_agent_tools,
    scaffold_workspace,
)
from .async_tools import make_async_agent_tools
from .async_observability import track_agent, record_token_usage

load_dotenv()

logger = logging.getLogger(__name__)

MODEL_NAME = "gpt-5.4-nano"
MAX_TOOL_CALL_NUM = 25
MAX_SENDBACK = 5

DOC_RULES = """
Code documentation rules (mandatory):
- Every code file MUST start with a header: Module (path), Purpose, Owner, Depends on.
- Every function/class method MUST have a docstring (Python) or JSDoc (JS/TS) that describes the behavior, Args/params, and Returns.
- Keep files modular. Do not put unrelated features in one file.
- Call lookup_code_index before reading or editing so you touch the right files.
- If you add a new module, call update_codemap_entry for that path.
"""

### Structured Outputs ###
class LeadPlan(BaseModel):
    app_name: str = Field(description="Short filesystem-friendly application name")
    summary: str = Field(description="One-paragraph architecture summary")
    frontend_req: str = Field(description="Numbered frontend requirements")
    backend_req: str = Field(description="Numbered backend requirements")
    qa_req: str = Field(description="Numbered QA requirements")
    contracts: str = Field(description="Shared API routes, payloads, and auth rules both sides must honor")
    frontend_tree: List[CodeNode] = Field(description="Modular frontend files with path, purpose, exports, depends_on")
    backend_tree: List[CodeNode] = Field(description="Modular backend files with path, purpose, exports, depends_on")

class QAVerdict(BaseModel):
    passed: bool
    next_agent: Literal["end", "frontend", "backend"]
    failed_tests: List[str]
    frontend_feedback: Optional[str] = None
    backend_feedback: Optional[str] = None
    summary: str


# Generic reducer strategy for parallel branches: keeps the latest non-empty update
def take_last(left: Any, right: Any) -> Any:
    return right if right is not None and right != "" else left

### Shared Agent State ###
class AgentState(TypedDict):
    user_prompt: Annotated[str, take_last]
    lead_plan: Annotated[dict, take_last]
    frontend_plan: Annotated[str, take_last]
    backend_plan: Annotated[str, take_last]
    qa_plan: Annotated[str, take_last]
    qa_verdict: Annotated[dict, take_last]
    qa_feedback: Annotated[str, take_last]
    error_log: Annotated[str, take_last]
    test_results: Annotated[str, take_last]
    sendback_count: Annotated[int, take_last]
    workspace_root: Annotated[str, take_last]
    codemap: Annotated[str, take_last]


async def handle_tool_calls_async(tool_calls, tool_dict) -> list:
    """Asynchronously executes tool calls returned by the model."""
    tool_msgs = []
    for tool_call in tool_calls:
        if isinstance(tool_call, dict):
            tool_name, tool_args, tool_id = tool_call["name"], tool_call["args"], tool_call["id"]
        else:
            tool_name, tool_args, tool_id = tool_call.name, tool_call.args, tool_call.id
        
        tool = tool_dict.get(tool_name)
        if tool is None:
            tool_output = f"ERROR: unknown tool '{tool_name}'."
        else:
            try:
                # Use ainvoke for async tool execution
                tool_output = await tool.ainvoke(tool_args)
            except Exception as exc:
                tool_output = f"ERROR: {exc}"
                
        if not isinstance(tool_output, str):
            tool_output = str(tool_output)
            
        tool_msg = f"Tool executed. id: {tool_id}, name:{tool_name}, output:{tool_output}"
        logger.info(tool_msg)
        print(tool_msg)
        tool_msgs.append(ToolMessage(content=tool_output, tool_call_id=tool_id))
    return tool_msgs


def _content_to_str(content) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    return str(content)


def _extract_and_record_tokens(response) -> None:
    if hasattr(response, "usage_metadata") and response.usage_metadata:
        prompt_tokens = response.usage_metadata.get("input_tokens", 0)
        completion_tokens = response.usage_metadata.get("output_tokens", 0)
        total_tokens = response.usage_metadata.get("total_tokens", 0)
        record_token_usage(prompt_tokens, completion_tokens, total_tokens)


async def _run_tool_loop_async(prompt: str, llm_tools, tool_dict) -> str:
    """Async tool-calling loop using ainvoke."""
    messages = [HumanMessage(content=prompt)]
    response = await llm_tools.ainvoke(messages)
    _extract_and_record_tokens(response)
    max_call = MAX_TOOL_CALL_NUM

    while getattr(response, "tool_calls", None) and max_call > 0:
        tool_msgs = await handle_tool_calls_async(response.tool_calls, tool_dict)
        messages.extend([response, *tool_msgs])
        response = await llm_tools.ainvoke(messages)
        _extract_and_record_tokens(response)
        max_call -= 1

    if getattr(response, "tool_calls", None):
        messages.append(
            HumanMessage(
                "Stop calling tools. Summarize what you completed, "
                "which CODEMAP paths you changed, and what is still unfinished."
            )
        )
        response = await llm_base.ainvoke(messages)
        _extract_and_record_tokens(response)

    return _content_to_str(response.content)


# LLM instances
llm_base = ChatOpenAI(model=MODEL_NAME, temperature=0, api_key=SecretStr(os.getenv("OPENAI_API_KEY")))
# Replace make_agent_tools calls with make_async_agent_tools:
frontend_tools, frontend_tool_dict = make_async_agent_tools("frontend")
backend_tools, backend_tool_dict = make_async_agent_tools("backend")
qa_tools, qa_tool_dict = make_async_agent_tools("qa")

frontend_llm = ChatOpenAI(model=MODEL_NAME, temperature=0, api_key=SecretStr(os.getenv("OPENAI_API_KEY"))).bind_tools(frontend_tools)
backend_llm = ChatOpenAI(model=MODEL_NAME, temperature=0, api_key=SecretStr(os.getenv("OPENAI_API_KEY"))).bind_tools(backend_tools)
qa_llm = ChatOpenAI(model=MODEL_NAME, temperature=0, api_key=SecretStr(os.getenv("OPENAI_API_KEY"))).bind_tools(qa_tools)


### Async Agent Nodes ###

@track_agent("lead_engineer")
async def lead_engineer_async(state: AgentState) -> AgentState:
    msg = "\n-- [LEAD ENGINEER AGENT] Analyzing user prompt and creating master plan (Async). --"
    logger.info(msg)
    print(msg)
    prompt = f"""You are the lead engineer. Review the user prompt: {state['user_prompt']}

                Plan a two-folder application and their requirements:
                - frontend/: UI/UX only.
                - backend/: API, data, auth, and server logic only.

                Define shared contracts (routes, request/response bodies, auth).
                Define clear and concise requirements for frontend and backend agent respectively.
                Create a hierarchical, modular file tree for frontend and backend.
                Do not write application logic. Your job is architecture, contracts, file index and requirements.
                """
    response = await llm_base.with_structured_output(LeadPlan).ainvoke([HumanMessage(content=prompt)])
    if hasattr(response, "usage_metadata"):
        _extract_and_record_tokens(response)

    frontend_tree = [
        CodeNode.model_validate(node) if not isinstance(node, CodeNode) else node
        for node in response.frontend_tree
    ]
    backend_tree = [
        CodeNode.model_validate(node) if not isinstance(node, CodeNode) else node
        for node in response.backend_tree
    ]
    workspace = scaffold_workspace(
        app_name=response.app_name,
        summary=response.summary,
        contracts=response.contracts,
        frontend_tree=frontend_tree,
        backend_tree=backend_tree,
    )
    state["lead_plan"] = response.model_dump()
    state["workspace_root"] = str(workspace)
    state["codemap"] = (workspace / "CODEMAP.md").read_text(encoding="utf-8")
    state.setdefault("sendback_count", 0)
    return state


@track_agent("frontend_engineer")
async def frontend_engineer_async(state: AgentState) -> AgentState:
    workspace = state.get("workspace_root") or str(get_workspace_root())
    is_sendback = state.get("sendback_count", 0) > 0
    if is_sendback:
        verdict = state.get("qa_verdict") or {}
        prompt = f"""You are the frontend engineer fixing failed QA tests.
                    Workspace: {workspace}
                    Lead frontend requirements: {state['lead_plan']['frontend_req']}
                    Contracts: {state['lead_plan'].get('contracts')}
                    CODEMAP:\n{state.get('codemap')}
                    QA feedback: {verdict.get('frontend_feedback') or state.get('qa_feedback')}
                    {DOC_RULES}
                    """
    else:
        prompt = f"""You are the frontend engineer.
                    Workspace: {workspace}
                    Frontend requirements: {state['lead_plan']['frontend_req']}
                    Shared contracts: {state['lead_plan'].get('contracts')}
                    CODEMAP:\n{state.get('codemap')}
                    {DOC_RULES}
                    Create a numbered plan, then implement it.
                    """
    logger.info("\n-- [FRONTEND ENGINEER AGENT] Executing (Async). --")
    print("\n-- [FRONTEND ENGINEER AGENT] Executing (Async). --")
    fplan = await _run_tool_loop_async(prompt, frontend_llm, frontend_tool_dict)
    # Return ONLY the updated key for frontend
    return {"frontend_plan": fplan} 


@track_agent("backend_engineer")
async def backend_engineer_async(state: AgentState) -> AgentState:
    workspace = state.get("workspace_root") or str(get_workspace_root())
    is_sendback = state.get("sendback_count", 0) > 0
    if is_sendback:
        verdict = state.get("qa_verdict") or {}
        prompt = f"""You are the backend engineer fixing failed QA tests.
Workspace: {workspace}
Lead backend requirements: {state['lead_plan']['backend_req']}
Contracts: {state['lead_plan'].get('contracts')}
CODEMAP:\n{state.get('codemap')}
QA feedback: {verdict.get('backend_feedback') or state.get('qa_feedback')}
{DOC_RULES}
"""
    else:
        prompt = f"""You are the backend engineer.
                    Workspace: {workspace}
                    Backend requirements: {state['lead_plan']['backend_req']}
                    Shared contracts: {state['lead_plan'].get('contracts')}
                    CODEMAP:\n{state.get('codemap')}
                    {DOC_RULES}
                    Create a numbered plan, then implement it.
                    """
    logger.info("\n-- [BACKEND ENGINEER AGENT] Executing (Async). --")
    print("\n-- [BACKEND ENGINEER AGENT] Executing (Async). --")
    bplan = await _run_tool_loop_async(prompt, backend_llm, backend_tool_dict)
    # Return ONLY the updated key for backend
    return {"backend_plan": bplan}


@track_agent("qa_engineer")
async def qa_engineer_async(state: AgentState) -> AgentState:
    workspace = state.get("workspace_root") or str(get_workspace_root())
    prompt = f"""You are the QA engineer.
                Workspace: {workspace}
                QA requirements: {state['lead_plan']['qa_req']}
                Frontend plan: {state.get('frontend_plan')}
                Backend plan: {state.get('backend_plan')}
                {DOC_RULES}
                """
    logger.info("\n-- [QA AGENT] Executing tests (Async). --")
    print("\n-- [QA AGENT] Executing tests (Async). --")
    work_summary = await _run_tool_loop_async(prompt, qa_llm, qa_tool_dict)
    sendbacks_used = state.get("sendback_count", 0)
    print("\n-- [QA AGENT] Routing verdict (Async). --")
    verdict_prompt = f"""Produce a routing verdict from QA results.
                        QA requirements: {state['lead_plan']['qa_req']}
                        Work summary: {work_summary}
                        Send-backs used: {sendbacks_used} of {MAX_SENDBACK}.
                        """
    verdict = await llm_base.with_structured_output(QAVerdict).ainvoke([HumanMessage(content=verdict_prompt)])
    if hasattr(verdict, "usage_metadata"):
        _extract_and_record_tokens(verdict)
        
    next_agent = verdict.next_agent if verdict.passed is False else "end"
    if sendbacks_used >= MAX_SENDBACK or next_agent not in ("frontend", "backend"):
        next_agent = "end"
    elif not verdict.passed:
        state["sendback_count"] = sendbacks_used + 1

    payload = verdict.model_dump()
    payload["next_agent"] = next_agent
    state["qa_verdict"] = payload
    state["qa_plan"] = verdict.summary
    return state