from typing import List, TypedDict, Literal, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, ToolMessage
from pydantic import BaseModel, Field
import logging

from .tools import (
    CodeNode,
    get_workspace_root,
    make_agent_tools,
    scaffold_workspace,
)

logger = logging.getLogger(__name__)

MODEL_NAME = "gpt-5.4-nano"
MAX_TOOL_CALL_NUM = 15
MAX_SENDBACK = 3

DOC_RULES = """
Code documentation rules (mandatory):
- Every code file MUST start with a header: Module (path), Purpose, Owner, Depends on.
- Every function/class method MUST have a docstring (Python) or JSDoc (JS/TS) that describes the behavior, Args/params, and Returns.
- Keep files modular. Do not put unrelated features in one file.
- Call lookup_code_index before reading or editing so you touch the right files.
- If you add a new module, call update_codemap_entry for that path.
"""


### Define Structured Outputs ###
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


### Define Shared Agent State ###
class AgentState(TypedDict):
    user_prompt: str
    lead_plan: dict
    frontend_plan: str
    backend_plan: str
    qa_plan: str
    qa_verdict: dict
    qa_feedback: str
    error_log: str
    test_results: str
    sendback_count: int
    workspace_root: str
    codemap: str


def handle_tool_calls(tool_calls, tool_dict) -> list:
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
                tool_output = tool.invoke(tool_args)
            except Exception as exc:  # noqa: BLE001 — surface tool failures to the agent
                tool_output = f"ERROR: {exc}"
        if not isinstance(tool_output, str):
            tool_output = str(tool_output)
        tool_msg = f"Tool executed. id: {tool_id}, name:{tool_name}, output:{tool_output}"
        print(tool_msg)
        logger.info(tool_msg)
        tool_msgs.append(ToolMessage(content=tool_output, tool_call_id=tool_id))
    return tool_msgs


def _content_to_str(content) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    return str(content)


def _run_tool_loop(prompt: str, llm_tools, tool_dict) -> str:
    messages = [HumanMessage(content=prompt)]
    response = llm_tools.invoke(messages)
    max_call = MAX_TOOL_CALL_NUM

    while getattr(response, "tool_calls", None) and max_call > 0:
        tool_msgs = handle_tool_calls(response.tool_calls, tool_dict)
        messages.extend([response, *tool_msgs])
        response = llm_tools.invoke(messages)
        max_call -= 1

    if getattr(response, "tool_calls", None):
        messages.append(
            HumanMessage(
                "Stop calling tools. Summarize what you completed, "
                "which CODEMAP paths you changed, and what is still unfinished."
            )
        )
        response = llm_base.invoke(messages)

    return _content_to_str(response.content)


# Not To Do Pointers:
# 1. Do not reuse llm_with_tools for lead “and just parse the text.” You lose the schema guarantee.
# 2. Do not bind_tools([]) on the already-bound runnable to “turn tools off.” Use the base llm.
# 3. Do not give lead the same file/shell tools. Lead only splits requirements and owns CODEMAP; tools belong to implementers.
llm_base = ChatOpenAI(model=MODEL_NAME, temperature=0)
frontend_tools, frontend_tool_dict = make_agent_tools("frontend")
backend_tools, backend_tool_dict = make_agent_tools("backend")
qa_tools, qa_tool_dict = make_agent_tools("qa")
frontend_llm = ChatOpenAI(model=MODEL_NAME, temperature=0).bind_tools(frontend_tools)
backend_llm = ChatOpenAI(model=MODEL_NAME, temperature=0).bind_tools(backend_tools)
qa_llm = ChatOpenAI(model=MODEL_NAME, temperature=0).bind_tools(qa_tools)


### Define Agent Nodes as functions ###

def lead_engineer(state: AgentState) -> AgentState:
    """
    Lead Engineer Agent: Plans the application architecture and passes the requirements to the frontend, backend and QA agents.
    """
    msg = "\n-- [LEAD ENGINEER AGENT] Analyzing user prompt and creating a master plan. --"
    print(msg)
    logger.info(msg)
    prompt = f"""You are the lead engineer. Review the user prompt: {state['user_prompt']}

Plan a two-folder application:
- frontend/: UI/UX only. The frontend agent may change only this folder.
- backend/: API, data, auth, and server logic only. The backend agent may change only this folder.

Also define shared contracts (routes, request/response bodies, auth) that both agents must follow.
Write the requirements.txt in the workspace that is used in sandbox to download packages.

Create a hierarchical, modular file tree (not one giant file per side). Each CodeNode must include:
- path (always under frontend/ or backend/)
- purpose (one line)
- exports (public symbols)
- depends_on (other files or API routes)

Requirements for frontend, backend, and QA must be numbered lists detailed enough to implement.

Do not write application logic. Your job is architecture, contracts, and the file index.
"""
    response = llm_base.with_structured_output(LeadPlan).invoke([HumanMessage(content=prompt)])
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
    lead_plan = response.model_dump()
    state["lead_plan"] = lead_plan
    state["workspace_root"] = str(workspace)
    state["codemap"] = (workspace / "CODEMAP.md").read_text(encoding="utf-8")
    state.setdefault("sendback_count", 0)
    scaffold_msg = f"-- [LEAD ENGINEER AGENT] Scaffolded workspace at {workspace} --"
    print(scaffold_msg)
    logger.info(scaffold_msg)
    return state


def frontend_engineer(state: AgentState) -> AgentState:
    """
    Frontend Engineer Agent: Works on the frontend development for the UI and UX.
    """
    workspace = state.get("workspace_root") or str(get_workspace_root())
    is_sendback = state.get("sendback_count", 0) > 0
    if is_sendback:
        msg = "\n-- [FRONTEND ENGINEER AGENT] Applying QA send-back fixes. --"
        verdict = state.get("qa_verdict") or {}
        prompt = f"""You are the frontend engineer fixing failed QA tests. Do not rebuild the app from scratch.
    Workspace: {workspace}
    You may WRITE only under frontend/. Other folders are read-only.
    Lead frontend requirements: {state['lead_plan']['frontend_req']}
    Contracts: {state['lead_plan'].get('contracts')}
    CODEMAP:
    {state.get('codemap')}
    QA feedback: {verdict.get('frontend_feedback') or state.get('qa_feedback')}
    Failed tests: {verdict.get('failed_tests') or state.get('test_results')}
    Current frontend plan: {state.get('frontend_plan')}
    {DOC_RULES}
    Use lookup_code_index to find the failing modules, fix only those frontend files, keep headers/docstrings, update CODEMAP if you add files, then summarize CODEMAP paths changed.
    """
    else:
        msg = "\n-- [FRONTEND ENGINEER AGENT] Creating a frontend plan from lead requirements and write code. --"
        prompt = f"""You are the frontend engineer.
    Workspace: {workspace}
    You may WRITE only under frontend/. Read CODEMAP, contracts/, and backend/ as needed. Never modify backend/.

    Frontend requirements from lead: {state['lead_plan']['frontend_req']}
    Shared contracts: {state['lead_plan'].get('contracts')}
    CODEMAP (authoritative file index):
    {state.get('codemap')}

    Workflow:
    1. Call lookup_code_index for each feature before editing.
    2. Implement the stubbed frontend files (and add modules only when necessary, then update_codemap_entry).
    3. Follow contracts; do not invent conflicting APIs.
    4. Write unit/UI tests under frontend/ if appropriate; run them with run_command.
    {DOC_RULES}

    Create a numbered plan, then implement it. Summarize CODEMAP paths you changed.
    """
    print(msg)
    logger.info(msg)
    state["frontend_plan"] = _run_tool_loop(prompt, frontend_llm, frontend_tool_dict)
    return state


def backend_engineer(state: AgentState) -> AgentState:
    """
    Backend Engineer Agent: Works on the backend development including API endpoints, security, database schema and integration with frontend.
    """
    workspace = state.get("workspace_root") or str(get_workspace_root())
    is_sendback = state.get("sendback_count", 0) > 0
    if is_sendback:
        msg = "\n-- [BACKEND ENGINEER AGENT] Applying QA send-back fixes. --"
        verdict = state.get("qa_verdict") or {}
        prompt = f"""You are the backend engineer fixing failed QA tests. Do not rebuild the app from scratch.
    Workspace: {workspace}
    You may WRITE only under backend/ and contracts/. Never modify frontend/.
    Lead backend requirements: {state['lead_plan']['backend_req']}
    Frontend plan: {state.get('frontend_plan')}
    Contracts: {state['lead_plan'].get('contracts')}
    CODEMAP:
    {state.get('codemap')}
    QA feedback: {verdict.get('backend_feedback') or state.get('qa_feedback')}
    Failed tests: {verdict.get('failed_tests') or state.get('test_results')}
    Current backend plan: {state.get('backend_plan')}
    {DOC_RULES}
    Use lookup_code_index to find the failing modules, fix only those backend files, keep headers/docstrings, update CODEMAP if you add files, then summarize CODEMAP paths changed.
    """
    else:
        msg = "\n-- [BACKEND ENGINEER AGENT] Creating a backend plan from lead requirements and integration plan from frontend plan and write code. --"
        prompt = f"""You are the backend engineer.
    Workspace: {workspace}
    You may WRITE only under backend/ and contracts/. Read CODEMAP and frontend/ as needed. Never modify frontend/.

    Backend requirements from lead: {state['lead_plan']['backend_req']}
    Frontend plan: {state['frontend_plan']}
    Shared contracts: {state['lead_plan'].get('contracts')}
    CODEMAP (authoritative file index):
    {state.get('codemap')}

    Workflow:
    1. Call lookup_code_index for each feature before editing.
    2. Implement stubbed backend files (algorithms, schema, API, auth) to match contracts and frontend integration needs.
    3. If you change an API, update contracts/api.md and CODEMAP.
    4. Write and run backend tests with run_command.
    {DOC_RULES}

    Create a numbered plan, then implement it. Summarize CODEMAP paths you changed.
    """
    print(msg)
    logger.info(msg)
    state["backend_plan"] = _run_tool_loop(prompt, backend_llm, backend_tool_dict)
    return state


def qa_engineer(state: AgentState) -> AgentState:
    """
    Works on the QA testing and provides feedback on the quality of the code based on test cases.
    """
    msg = "\n-- [QA AGENT] Creating a QA plan from lead requirements and test plan from frontend and backend plan and write code. --"
    print(msg)
    logger.info(msg)
    workspace = state.get("workspace_root") or str(get_workspace_root())

    prompt = f"""You are the QA engineer.
    Workspace: {workspace}
    You may WRITE only under qa/. Frontend and backend are read-only.
    Use lookup_code_index and read_file to inspect the implementation.

    QA requirements: {state["lead_plan"]["qa_req"]}
    Frontend plan: {state["frontend_plan"]}
    Backend plan: {state["backend_plan"]}
    CODEMAP:
    {state.get("codemap")}

    Create a numbered plan then:
    - Write workflow, performance, and security tests under qa/.
    - Fail the build if application code files lack a Module/Purpose header or public functions lack Args/Returns (or JSDoc @param/@returns).
    - Execute tests with run_command.
    - Write how to start the app in a single line.
    Do not rewrite product code; report owners via the verdict.
    {DOC_RULES}
    """

    work_summary = _run_tool_loop(prompt, qa_llm, qa_tool_dict)
    sendbacks_used = state.get("sendback_count", 0)
    remaining = max(MAX_SENDBACK - sendbacks_used, 0)
    verdict_prompt = f"""You already ran QA work. Produce a routing verdict from the results.
    QA requirements: {state["lead_plan"]["qa_req"]}
    Work summary: {work_summary}
    Send-backs already used: {sendbacks_used} of {MAX_SENDBACK} ({remaining} remaining).

    Rules:
    - passed=true only if executed tests succeeded. Then next_agent must be "end".
    - If tests failed, pick exactly one next_agent: "frontend" or "backend" (the primary owner this round). If both failed, pick the more blocking owner.
    - Missing file headers or function Args/Returns docstrings are failures for the folder that owns the file.
    - If remaining send-backs are 0, next_agent must be "end" even if tests failed.
    - If you cannot determine a fix owner, next_agent="end".
    - frontend_feedback / backend_feedback: concrete fix instructions for that engineer, including CODEMAP paths.
    """
    verdict = llm_base.with_structured_output(QAVerdict).invoke([HumanMessage(content=verdict_prompt)])

    next_agent = verdict.next_agent
    if verdict.passed:
        next_agent = "end"
    elif sendbacks_used >= MAX_SENDBACK or next_agent not in ("frontend", "backend"):
        next_agent = "end"
    else:
        state["sendback_count"] = sendbacks_used + 1

    payload = verdict.model_dump()
    payload["next_agent"] = next_agent
    state["qa_verdict"] = payload
    state["qa_plan"] = verdict.summary
    if verdict.failed_tests:
        state["test_results"] = "\n".join(verdict.failed_tests)
    elif verdict.passed:
        state["test_results"] = "passed"
    else:
        state["test_results"] = work_summary
    if next_agent == "frontend":
        state["qa_feedback"] = verdict.frontend_feedback or verdict.summary
    elif next_agent == "backend":
        state["qa_feedback"] = verdict.backend_feedback or verdict.summary
    else:
        state["qa_feedback"] = verdict.summary

    route_msg = f"-- [QA AGENT] passed={verdict.passed} next_agent={next_agent} sendbacks={state.get('sendback_count', 0)}/{MAX_SENDBACK} --"
    print(route_msg)
    logger.info(route_msg)
    return state
