import os
import subprocess
from typing import List, Dict, Any, TypedDict, Literal, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, ToolMessage
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

### TODO: Add which tool to call and when in each agent prompt

MODEL_NAME = "gpt-5.4-nano"
MAX_TOOL_CALL_NUM = 5
MAX_SENDBACK = 3

### Define Structured Outputs ###
class LeadPlan(BaseModel):
    frontend_req:str
    backend_req:str
    qa_req:str

class QAVerdict(BaseModel):
    passed: bool
    next_agent: Literal["end", "frontend", "backend"]
    failed_tests: List[str]
    frontend_feedback: Optional[str] = None
    backend_feedback: Optional[str] = None
    summary: str

### Define Shared Agent State ###
class AgentState(TypedDict):
    user_prompt:str
    lead_plan:dict
    frontend_plan:str
    backend_plan:str
    qa_plan:str
    qa_verdict:dict
    qa_feedback:str
    error_log:str
    test_results:str
    sendback_count:int

### Function to handle tool calls###
def handle_tool_calls(tool_calls):
    tool_msgs = []
    for tool_call in tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_id = tool_call["id"]
        tool_output = tool_dict[tool_name].invoke(tool_args)
        tool_msg = f"Tool executed. id: {tool_id}, name:{tool_name}, output:{tool_output}"
        print(tool_msg)
        logger.info(tool_msg)
        tool_msgs.append(ToolMessage(content=tool_output, tool_call_id=tool_id))
    return tool_msgs

        
### Initialize LLM with tools ###
tools = [ # temp tools
    Tool(
        name="lead_plan",
        description="Plan the lead generation strategy",
        func=lead_plan
    ),
    Tool(
        name="frontend_plan",
        description="Plan the frontend development",
        func=frontend_plan
    ),
]

# Not To Do Pointers:
# 1. Do not reuse llm_with_tools for lead “and just parse the text.” You lose the schema guarantee.
# 2. Do not bind_tools([]) on the already-bound runnable to “turn tools off.” Use the base llm.
# 3. Do not give lead the same file/shell tools. Lead only splits requirements; tools belong to implementers.
llm_base = ChatOpenAI(model=MODEL_NAME, temperature=0)
llm_with_tools = ChatOpenAI(model=MODEL_NAME, temperature=0).bind_tools(tools)



### Define Agent Nodes as functions ###

def lead_engineer(state: AgentState) -> AgentState:
    """
    Lead Engineer Agent: Plans the application architecture and passes the requirements to the frontend, backend and QA agents.
    """
    msg = "\n-- [LEAD ENGINEER AGENT] Analyzing user prompt and creating a master plan. --"
    print(msg)
    logger.info(msg)
    prompt = f"""You are the lead engineer and review the user prompt: {state['user_prompt']}.
    Create a comprehensive plan for the application architecture and requirements for frontend, backend and QA agents in a numbered list format:
    - Frontend Engineer Agent: Works on the frontend development for the UI and UX.
    - Backend Engineer Agent: Works on the backend development including API endpoints, security, database schema and integration with frontend.
    - QA Engineer Agent: Works on the QA testing and provides feedback on the quality of the code.

    Ensure the plan is comprehensive and detailed enough for each agent to work on their respective tasks in numbered list format.
    """
    response = llm_base.with_structured_output(LeadPlan).invoke([HumanMessage(content=prompt)])
    state['lead_plan'] = {"frontend_req": response.frontend_req, "backend_req": response.backend_req, "qa_req": response.qa_req}
    state.setdefault("sendback_count", 0)
    return state

def frontend_engineer(state: AgentState) -> AgentState:
    """
    Frontend Engineer Agent: Works on the frontend development for the UI and UX.
    """
    is_sendback = state.get("sendback_count", 0) > 0
    if is_sendback:
        msg = "\n-- [FRONTEND ENGINEER AGENT] Applying QA send-back fixes. --"
        verdict = state.get("qa_verdict") or {}
        prompt = f"""You are the frontend engineer fixing failed QA tests. Do not rebuild the app from scratch.
    Lead frontend requirements: {state['lead_plan']['frontend_req']}
    QA feedback: {verdict.get('frontend_feedback') or state.get('qa_feedback')}
    Failed tests: {verdict.get('failed_tests') or state.get('test_results')}
    Current frontend plan: {state.get('frontend_plan')}
    Fix only the reported frontend failures, then summarize files changed.
    """
    else:
        msg = "\n-- [FRONTEND ENGINEER AGENT] Creating a frontend plan from lead requirements and write code. --"
        prompt = f"""You are the frontend engineer and review the frontend requirements from lead plan: {state['lead_plan']['frontend_req']}.
    Create a comprehensive plan for the frontend development for the UI and UX in a numbered list format:
    - UI/UX Design: Create a design for the UI and UX.
    - Frontend Development: Write the code for the frontend.
    - Unit Tests: Write the unit tests for the frontend.
    - Performance Tests: Write the performance tests for the frontend.
    - Security Tests: Write the security tests for the frontend.
    - Execute all frontend test cases.
    """
    print(msg)
    logger.info(msg)
    messages = [HumanMessage(content=prompt)]
    response = llm_with_tools.invoke(messages)
    max_call = MAX_TOOL_CALL_NUM


    while response.tool_calls and max_call > 0:
        tool_msgs = handle_tool_calls(response.tool_calls)
        messages.extend([response, *tool_msgs])
        response = llm_with_tools.invoke(messages)
        max_call -= 1
    
    # if tool call still exists after max attempt, then summarize
    if response.tool_calls:
        messages.append(HumanMessage(
            "Stop calling tools. Summarize what you completed, "
            "what files you changed, and what is still unfinished."
        ))
        response = llm_base.invoke(messages)   # no tools


    state['frontend_plan'] = response.content
    return state

def backend_engineer(state: AgentState) -> AgentState:
    """
    Backend Engineer Agent: Works on the backend development including API endpoints, security, database schema and integration with frontend.
    """
    is_sendback = state.get("sendback_count", 0) > 0
    if is_sendback:
        msg = "\n-- [BACKEND ENGINEER AGENT] Applying QA send-back fixes. --"
        verdict = state.get("qa_verdict") or {}
        prompt = f"""You are the backend engineer fixing failed QA tests. Do not rebuild the app from scratch.
    Lead backend requirements: {state['lead_plan']['backend_req']}
    Frontend plan: {state.get('frontend_plan')}
    QA feedback: {verdict.get('backend_feedback') or state.get('qa_feedback')}
    Failed tests: {verdict.get('failed_tests') or state.get('test_results')}
    Current backend plan: {state.get('backend_plan')}
    Fix only the reported backend failures, then summarize files changed.
    """
    else:
        msg = "\n-- [BACKEND ENGINEER AGENT] Creating a backend plan from lead requirements and integration plan from frontend plan and write code. --"
        prompt = f"""You are the backend engineer and review the backend requirements from lead plan and frontend plan for integration.
    backend requirements: {state['lead_plan']['backend_req']}
    frontend plan: {state['frontend_plan']}
    Create a comprehensive plan for the backend and UI integration development in a numbered list format:
    - Backend Design: Create a backend architecture design.
    - Backend Development: Write the code for the backend architecture including for algorithms, database schema(optional), API endpoints and authentication.
    - Integration Development: Write the code to integrate with UI.
    - Unit Tests: Write the unit tests for the backend.
    - Performance Tests: Write the performance tests for the backend.
    - Security Tests: Write the security tests for the backend.
    - Execute all backend test cases.
    """
    print(msg)
    logger.info(msg)
    messages = [HumanMessage(content=prompt)]
    response = llm_with_tools.invoke(messages)
    max_call = MAX_TOOL_CALL_NUM


    while response.tool_calls and max_call > 0:
        tool_msgs = handle_tool_calls(response.tool_calls)
        messages.extend([response, *tool_msgs])
        response = llm_with_tools.invoke(messages)
        max_call -= 1
    
    # if tool call still exists after max attempt, then summarize
    if response.tool_calls:
        messages.append(HumanMessage(
            "Stop calling tools. Summarize what you completed, "
            "what files you changed, and what is still unfinished."
        ))
        response = llm_base.invoke(messages)   # no tools


    state["backend_plan"] = response.content 
    return state

def qa_engineer(state: AgentState) -> AgentState:
    """
    Works on the QA testing and provides feedback on the quality of the code based on test cases.
    """
    msg = "\n-- [QA AGENT] Creating a QA plan from lead requirements and test plan from frontend and backend plan and write code. --"
    print(msg)
    logger.info(msg)

    prompt = f"""You are the QA engineer  who reviews the requierments from {state["lead_plan"]["qa_req"]}.
    Analyze frontend plan: {state["frontend_plan"]} and backend plan: {state["backend_plan"]} to write workflow unit tests."
    Create a comprehensive plan for the workflow tests in a numbered list format:
    - Unit Tests: Write the unit tests for the workflow.
    - Performance Tests: Write the performance tests for end to end.
    - Security Tests: Write the security tests for end to end.
    - Execute all test cases from QA.
    - Write how to initate the app in a single line.
    """

    messages = [HumanMessage(content=prompt)]
    response = llm_with_tools.invoke(messages)
    max_call = MAX_TOOL_CALL_NUM


    while response.tool_calls and max_call > 0:
        tool_msgs = handle_tool_calls(response.tool_calls)
        messages.extend([response, *tool_msgs])
        response = llm_with_tools.invoke(messages)
        max_call -= 1
    
    # if tool call still exists after max attempt, then summarize
    if response.tool_calls:
        messages.append(HumanMessage(
            "Stop calling tools. Summarize what you completed, "
            "what files you changed, and what is still unfinished."
        ))
        response = llm_base.invoke(messages)   # no tools

    work_summary = response.content or ""
    sendbacks_used = state.get("sendback_count", 0)
    remaining = max(MAX_SENDBACK - sendbacks_used, 0)
    verdict_prompt = f"""You already ran QA work. Produce a routing verdict from the results.
    QA requirements: {state["lead_plan"]["qa_req"]}
    Work summary: {work_summary}
    Send-backs already used: {sendbacks_used} of {MAX_SENDBACK} ({remaining} remaining).

    Rules:
    - passed=true only if executed tests succeeded. Then next_agent must be "end".
    - If tests failed, pick exactly one next_agent: "frontend" or "backend" (the primary owner this round). If both failed, pick the more blocking owner.
    - If remaining send-backs are 0, next_agent must be "end" even if tests failed.
    - If you cannot determine a fix owner, next_agent="end".
    - frontend_feedback / backend_feedback: concrete fix instructions for that engineer.
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
