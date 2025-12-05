"""
Infrastructure module for agent execution.

Contains universal/benchmark-agnostic components:
- OpenAI client initialization
- LLM interface (call_llm) - SINGLE place for all LLM calls
- Trace helpers (next_node_id, calculate_depth, create_trace_event, create_validator_event)
- SDK execution utilities (dispatch_with_timeout, execute_sdk_call)
- SDK dispatch wrappers (dispatch_with_retry, dispatch_once)
- Conversation utilities (build_subagent_context, format_subagent_result, inject_plan)
- Error definitions (AgentError, AgentTimeoutError, AgentStepLimitError)
- TaskContext for LLM usage logging

Import hierarchy: This module has NO internal imports.
External imports only: langfuse, openai, config, erc3 (ApiException only)
"""

import time
import concurrent.futures
from typing import List
from langfuse import get_client
from langfuse.openai import OpenAI
from langfuse import observe
from openai.lib._parsing._completions import type_to_response_format_param
from pydantic import BaseModel
from erc3 import ApiException

import config


# ============================================================================
# ERROR DEFINITIONS
# ============================================================================

class AgentError(Exception):
    """Base exception for agent-related errors."""
    pass


class AgentTimeoutError(AgentError):
    """Raised when an SDK operation times out."""
    pass


class AgentStepLimitError(AgentError):
    """Raised when agent exceeds maximum step limit."""
    pass


# ============================================================================
# TASK CONTEXT
# ============================================================================
# Holds task-scoped state (erc_client, task_id, model) for logging LLM usage.

class TaskContext:
    """
    Context object for task-scoped operations.
    
    Passed through the call chain to enable log_llm calls at each LLM invocation.
    """
    def __init__(self, erc_client, task_id: str, model: str):
        self.erc_client = erc_client
        self.task_id = task_id
        self.model = model
    
    def log_llm(self, duration_sec: float, usage):
        """Log LLM usage to ERC3 platform."""
        self.erc_client.log_llm(
            task_id=self.task_id,
            model=self.model,
            duration_sec=duration_sec,
            usage=usage
        )


# ============================================================================
# OPENAI CLIENT INITIALIZATION
# ============================================================================
# Single place for LLM client setup. Easy to change provider/model globally.

client = OpenAI(
    base_url="https://api.cerebras.ai/v1",
    api_key=config.CEREBRAS_API_KEY
)

# Model configuration - change here to affect all LLM calls
LLM_MODEL = "gpt-oss-120b"
LLM_MODEL_LOG_NAME = "openai/gpt-oss-120b"  # For SDK logs and traces


# ============================================================================
# TRACE HELPER FUNCTIONS
# ============================================================================

def next_node_id(parent_id: str | None, sibling_count: int) -> str:
    """
    Generate hierarchical node ID for trace tree structure.
    
    Args:
        parent_id: Parent node's ID (None for virtual root, "0" for orchestrator children)
        sibling_count: Number of siblings already created under this parent (0-indexed)
    
    Returns:
        Node ID string like "1", "2" (orchestrator), "2.1", "2.2" (subagent), 
        "2.2.1" (validator)
    
    Examples:
        next_node_id(None, 0) -> "0"        # Virtual root (unused)
        next_node_id("0", 0) -> "1"         # First orchestrator step
        next_node_id("0", 1) -> "2"         # Second orchestrator step
        next_node_id("2", 0) -> "2.1"       # First subagent step under orch step 2
        next_node_id("2.3", 0) -> "2.3.1"   # Validator under subagent step 2.3
    """
    if parent_id is None:
        return "0"  # Virtual root node (no actual trace event)
    elif parent_id == "0":
        return str(sibling_count + 1)  # Orchestrator steps: "1", "2", "3"...
    else:
        return f"{parent_id}.{sibling_count + 1}"  # Nested: "2.1", "2.1.1"


def calculate_depth(node_id: str) -> int:
    """
    Calculate depth from node ID.
    
    Returns:
        -1 for virtual root (node_id="0", unused)
        0 for orchestrator (node_id="1", "2", etc.)
        1 for subagent (node_id="1.1", "2.3", etc.)
        2 for validator under subagent (node_id="1.1.1", "2.3.1", etc.)
    """
    if node_id == "0":
        return -1  # Virtual root (unused)
    return node_id.count(".")  # "1"->0, "1.2"->1, "1.2.3"->2


def create_trace_event(
    node_id: str,
    parent_node_id: str | None,
    sibling_index: int,
    context: str,
    system_prompt: str,
    input_messages: List[dict],
    output: dict,
    reasoning: str | None,
    timing: float,
    event_type: str = "agent_step",
    tool_calls: List[dict] | None = None,
    subagent_result: dict | None = None,
) -> dict:
    """
    Create a trace event for agent steps.
    
    Args:
        node_id: Unique node ID (e.g., "2.3")
        parent_node_id: Parent's node ID (None for root)
        sibling_index: 0-indexed position among siblings (for computing prev_sibling_node_id)
        context: Agent name (Orchestrator, ProductExplorer, etc.)
        system_prompt: The system prompt (stored separately)
        input_messages: Conversation messages WITHOUT system prompt
        output: Parsed LLM response (model_dump())
        reasoning: LLM's reasoning/thinking (if available)
        timing: LLM call duration in seconds
        event_type: Type of event ("agent_step" or "validator_step")
        tool_calls: List of SDK calls made [{request: {}, response: {}}, ...]
        subagent_result: Subagent completion info (orchestrator only)
    
    Returns:
        Properly structured trace event dict
    """
    # Compute prev_sibling_node_id for execution flow edges
    if sibling_index > 0 and parent_node_id is not None:
        prev_sibling = next_node_id(parent_node_id, sibling_index - 1)
    else:
        prev_sibling = None
    
    event = {
        "event": event_type,
        "node_id": node_id,
        "parent_node_id": parent_node_id,
        "prev_sibling_node_id": prev_sibling,
        "depth": calculate_depth(node_id),
        "context": context,
        "system_prompt": system_prompt,
        "input_messages": input_messages,
        "output": output,
        "reasoning": reasoning,
        "timing": round(timing, 2),
    }
    
    if tool_calls:
        event["tool_calls"] = tool_calls
    
    if subagent_result:
        event["subagent_result"] = subagent_result
    
    return event


def create_validator_event(
    node_id: str,
    parent_node_id: str | None,
    sibling_index: int,
    validates_node_id: str,
    validator_name: str,
    validation_passed: bool,
    system_prompt: str,
    input_messages: List[dict],
    output: dict,
    reasoning: str | None,
    timing: float,
) -> dict:
    """
    Create a trace event for validator steps.
    
    Args:
        node_id: Unique node ID for this validator call (e.g., "2.3.1")
        parent_node_id: Parent's node ID (the agent step being validated)
        sibling_index: 0-indexed position among siblings
        validates_node_id: The node_id of the step being validated
        validator_name: Name of the validator (e.g., "BullshitCaller")
        validation_passed: Whether the validator approved the action (schema-independent)
        system_prompt: The validator's system prompt
        input_messages: Messages sent to the validator
        output: Parsed validator response (model_dump())
        reasoning: LLM's reasoning/thinking (if available)
        timing: LLM call duration in seconds
    
    Returns:
        Properly structured validator trace event dict
    """
    # Compute prev_sibling_node_id for execution flow edges
    if sibling_index > 0 and parent_node_id is not None:
        prev_sibling = next_node_id(parent_node_id, sibling_index - 1)
    else:
        prev_sibling = None
    
    return {
        "event": "validator_step",
        "node_id": node_id,
        "parent_node_id": parent_node_id,
        "prev_sibling_node_id": prev_sibling,
        "validates_node_id": validates_node_id,
        "depth": calculate_depth(node_id),
        "validator_name": validator_name,
        "validation_passed": validation_passed,
        "system_prompt": system_prompt,
        "input_messages": input_messages,
        "output": output,
        "reasoning": reasoning,
        "timing": round(timing, 2),
    }


# ============================================================================
# LLM INTERFACE - SINGLE PLACE FOR ALL LLM CALLS
# ============================================================================

@observe()
def call_llm(
    schema: BaseModel,
    system_prompt: str,
    conversation: List[dict],
    task_ctx: "TaskContext" = None,
    reasoning_effort: str = "medium",
) -> dict:
    """
    Call LLM with structured output.
    
    This is THE SINGLE PLACE where LLM is called for agent steps.
    Does NOT append to trace - returns data for caller to build trace event.
    Caller is responsible for creating the trace event with tool_calls attached.
    
    Args:
        schema: Pydantic model for structured output
        system_prompt: System prompt (stored separately in trace)
        conversation: List of user/assistant messages (WITHOUT system prompt)
        task_ctx: TaskContext for logging LLM usage to ERC3 platform
        reasoning_effort: Reasoning effort level ("low", "medium", "high")
    
    Returns:
        dict with:
        - "parsed": Parsed Pydantic model instance
        - "output": model_dump() of parsed response
        - "reasoning": LLM reasoning (if available)
        - "timing": LLM call duration in seconds
    """
    # Build messages with system prompt
    messages = [{"role": "system", "content": system_prompt}]
    for msg in conversation:
        messages.append({"role": msg["role"], "content": msg["content"]})
            
    response_format = type_to_response_format_param(schema)
    
    # Retry logic for rare LLM failures
    for attempt in range(4):
        try:
            llm_start = time.time()
            
            lf = get_client()
            with lf.start_as_current_observation(name="llm-call") as gen:
                response = client.chat.completions.create(
                    model=LLM_MODEL,
                    messages=messages,
                    response_format=response_format,
                    reasoning_effort=reasoning_effort,
                )

                reasoning = getattr(response.choices[0].message, 'reasoning', None)
                gen.update(metadata={"reasoning": reasoning, "attempt": attempt + 1})
            
            llm_duration = time.time() - llm_start
            
            # Log LLM usage to ERC3 platform
            if task_ctx:
                task_ctx.log_llm(duration_sec=llm_duration, usage=response.usage)
            
            content = response.choices[0].message.content
            parsed = schema.model_validate_json(content)
            
            return {
                "parsed": parsed,
                "output": parsed.model_dump(),
                "reasoning": reasoning,
                "timing": llm_duration,
            }
            
        except Exception as e:
            if attempt < 3:
                print(f"  ⚠ Retry {attempt + 1}/3 (error: {type(e).__name__})")
                time.sleep(0.5)
            else:
                raise


# ============================================================================
# SDK EXECUTION UTILITIES
# ============================================================================

def dispatch_with_timeout(benchmark_client, function, timeout_seconds: int = 30):
    """
    Execute SDK dispatch with timeout protection.
    
    Args:
        benchmark_client: SDK client for API calls
        function: SDK request object to dispatch
        timeout_seconds: Timeout in seconds (default 30)
    
    Returns:
        SDK response object
    
    Raises:
        TimeoutError: If operation times out
    """
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(benchmark_client.dispatch, function)
        try:
            return future.result(timeout=timeout_seconds)
        except concurrent.futures.TimeoutError:
            raise TimeoutError(f"SDK operation timed out after {timeout_seconds} seconds")


def execute_sdk_call(function, benchmark_client) -> dict:
    """
    Execute a single SDK call with standard error handling.
    
    This is the base SDK execution function used by all benchmarks.
    Handles dispatch, timeout, and ApiException errors uniformly.
    
    Args:
        function: SDK request object (Pydantic model with model_dump/model_dump_json)
        benchmark_client: SDK client for API calls
    
    Returns:
        dict with:
        - "text": JSON response string for conversation log
        - "tool_call": {request, response} dict for trace
    """
    request_dict = function.model_dump()
    
    try:
        result = dispatch_with_timeout(benchmark_client, function)
        txt = result.model_dump_json(exclude_none=True, exclude_unset=True)
        response_dict = result.model_dump(exclude_none=True, exclude_unset=True)
    except TimeoutError as e:
        txt = f'{{"error": "{str(e)}"}}'
        response_dict = {"error": str(e)}
    except ApiException as e:
        txt = e.detail
        response_dict = {"error": e.detail}
    
    return {
        "text": txt,
        "tool_call": {"request": request_dict, "response": response_dict}
    }


# ============================================================================
# SDK DISPATCH WRAPPERS
# ============================================================================
# Wrappers for SDK dispatch with different retry behaviors.
# Use dispatch_with_retry for read operations, dispatch_once for writes.

def dispatch_with_retry(client, request, max_retries: int = 2, delay: float = 0.1):
    """
    Execute SDK dispatch with retry on transient failures.
    
    For READ operations (list, get, search) where retrying is safe.
    
    Args:
        client: SDK client
        request: SDK request object to dispatch
        max_retries: Maximum retry attempts (default 2, so up to 3 total attempts)
        delay: Delay in seconds between retries (default 0.1s)
    
    Returns:
        SDK response object
    
    Raises:
        Last exception if all retries fail
    """
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            return client.dispatch(request)
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                time.sleep(delay)
    raise last_error


def dispatch_once(client, request):
    """
    Execute SDK dispatch without retry.
    
    For WRITE operations (update, log, delete) where retrying could cause duplicates.
    Thin wrapper for API consistency and explicit intent.
    
    Args:
        client: SDK client
        request: SDK request object to dispatch
    
    Returns:
        SDK response object
    """
    return client.dispatch(request)


# ============================================================================
# CONVERSATION UTILITIES
# ============================================================================

def build_subagent_context(orchestrator_log: List[dict], current_task: str) -> str:
    """
    Build context string for sub-agent from orchestrator's log.
    
    Includes: original user task + previous sub-agent interaction summaries + current task.
    
    Args:
        orchestrator_log: Orchestrator's full conversation log (includes system prompt)
        current_task: The task being delegated to the subagent
    
    Returns:
        Formatted context string for subagent's initial user message
    """
    # Extract original user task (second message in orchestrator log)
    original_task = ""
    for msg in orchestrator_log:
        if msg["role"] == "user":
            original_task = msg["content"]
            break
    
    # Extract previous sub-agent summaries from orchestrator log
    # These are stored as user messages with "Sub-agent:" prefix
    previous_interactions = []
    for msg in orchestrator_log:
        if msg["role"] == "user" and msg["content"].startswith("Sub-agent:"):
            previous_interactions.append(msg["content"])
    
    # Build context string
    context_parts = [f"Original Task: {original_task}"]
    
    if previous_interactions:
        context_parts.append("\nPrevious Sub-agent Results:")
        for interaction in previous_interactions:
            context_parts.append(interaction)
    
    context_parts.append(f"\nYour Current Task: {current_task}")
    
    return "\n".join(context_parts)


def format_subagent_result(subagent_name: str, status: str, report: str) -> str:
    """
    Format sub-agent completion into structured string for orchestrator.
    
    This format is appended to orchestrator's log as sub-agent response.
    
    Args:
        subagent_name: Name of the subagent (e.g., "ProductExplorer")
        status: Completion status ("completed" or "refused")
        report: Subagent's final report
    
    Returns:
        Formatted string for orchestrator conversation
    """
    return f"""Sub-agent: {subagent_name}
Status: {status}
Report: {report}"""


def inject_plan(conversation: List[dict], remaining_work: List[str] | None) -> List[dict]:
    """
    Inject the remaining work plan into conversation, replacing any previous plan.
    
    This is extracted from duplicated code in run_subagent and run_orchestrator.
    
    Args:
        conversation: Current conversation log (will be modified in place)
        remaining_work: List of remaining work items, or None
    
    Returns:
        The modified conversation (same reference as input)
    """
    # Remove any existing plan message
    conversation[:] = [msg for msg in conversation if not msg["content"].startswith("Remaining work:")]
    
    # Add new plan if provided
    if remaining_work:
        plan_text = "\n".join([f"{idx+1}. {step}" for idx, step in enumerate(remaining_work)])
        conversation.append({"role": "user", "content": f"Remaining work:\n{plan_text}"})
    
    return conversation
