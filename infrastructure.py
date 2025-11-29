"""
Infrastructure module for agent execution.

Contains:
- OpenAI client initialization
- LLM interface (get_next_step) - SINGLE place for all LLM calls
- Trace helpers (next_node_id, calculate_depth, create_trace_event, create_validator_event)
- SDK execution (execute_sdk_tool, execute_batch, dispatch_with_timeout)
- Conversation utilities (build_subagent_context, format_subagent_result, inject_plan)
- Error definitions (AgentError, AgentTimeoutError)

Import hierarchy: This module has NO internal imports.
External imports only: langfuse, openai, erc3, config
"""

import time
import concurrent.futures
from typing import List, Union
from langfuse import get_client
from langfuse.openai import OpenAI
from langfuse import observe
from openai.lib._parsing._completions import type_to_response_format_param
from pydantic import BaseModel
from erc3 import store, ApiException

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
    base_url="https://openrouter.ai/api/v1",
    api_key=config.OPENROUTER_API_KEY
)

# Model configuration - change here to affect all LLM calls
LLM_MODEL = "openai/gpt-oss-120b"
LLM_PROVIDER = {"only": ["Cerebras"]}


# ============================================================================
# TRACE HELPER FUNCTIONS
# ============================================================================

def next_node_id(parent_id: str | None, sibling_count: int) -> str:
    """
    Generate hierarchical node ID for trace tree structure.
    
    Args:
        parent_id: Parent node's ID (None for TaskAnalyzer, "0" for orchestrator children)
        sibling_count: Number of siblings already created under this parent (0-indexed)
    
    Returns:
        Node ID string like "0" (TaskAnalyzer), "1", "2" (orchestrator), 
        "2.1", "2.2" (subagent), "2.2.1" (BullshitCaller)
    
    Examples:
        next_node_id(None, 0) -> "0"        # TaskAnalyzer (first and only root)
        next_node_id("0", 0) -> "1"         # First orchestrator step
        next_node_id("0", 1) -> "2"         # Second orchestrator step
        next_node_id("2", 0) -> "2.1"       # First subagent step under orch step 2
        next_node_id("2.3", 0) -> "2.3.1"   # BullshitCaller under subagent step 2.3
    """
    if parent_id is None:
        return "0"  # TaskAnalyzer is always node 0
    elif parent_id == "0":
        return str(sibling_count + 1)  # Orchestrator steps: "1", "2", "3"...
    else:
        return f"{parent_id}.{sibling_count + 1}"  # Nested: "2.1", "2.1.1"


def calculate_depth(node_id: str) -> int:
    """
    Calculate depth from node ID.
    
    Returns:
        -1 for TaskAnalyzer (node_id="0")
        0 for orchestrator (node_id="1", "2", etc.)
        1 for subagent (node_id="1.1", "2.3", etc.)
        2 for BullshitCaller under subagent (node_id="1.1.1", "2.3.1", etc.)
    """
    if node_id == "0":
        return -1  # TaskAnalyzer
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
        parent_node_id: Parent's node ID (None for TaskAnalyzer)
        sibling_index: 0-indexed position among siblings (for computing prev_sibling_node_id)
        context: Agent name (TaskAnalyzer, Orchestrator, ProductExplorer, etc.)
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
def get_next_step(
    next_step_schema: BaseModel,
    system_prompt: str,
    conversation: List[dict],
    task_ctx: "TaskContext" = None,
) -> dict:
    """
    Get next step from LLM using the provided schema.
    
    This is THE SINGLE PLACE where LLM is called for agent steps.
    Does NOT append to trace - returns data for caller to build trace event.
    Caller is responsible for creating the trace event with tool_calls attached.
    
    Args:
        next_step_schema: Pydantic model for structured output
        system_prompt: System prompt (stored separately in trace)
        conversation: List of user/assistant messages (WITHOUT system prompt)
        task_ctx: TaskContext for logging LLM usage to ERC3 platform
    
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
            
    schema = type_to_response_format_param(next_step_schema)
    
    # Retry logic for rare LLM failures
    for attempt in range(4):
        try:
            llm_start = time.time()
            
            lf = get_client()
            with lf.start_as_current_generation(name="next-step-generation") as gen:
                response = client.chat.completions.create(
                    model=LLM_MODEL,
                    messages=messages,
                    response_format=schema,
                    extra_body={
                        "provider": LLM_PROVIDER,
                    },
                )

                reasoning = response.choices[0].message.reasoning
                gen.update(metadata={"reasoning": reasoning, "attempt": attempt + 1})
            
            llm_duration = time.time() - llm_start
            
            # Log LLM usage to ERC3 platform
            if task_ctx:
                task_ctx.log_llm(duration_sec=llm_duration, usage=response.usage)
            
            content = response.choices[0].message.content
            parsed = next_step_schema.model_validate_json(content)
            
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
# SDK EXECUTION
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


def append_basket_state_if_needed(job_function, benchmark_client, benchmark: str, original_txt: str) -> str:
    """
    Automatically append basket state after state-changing operations.
    
    This is a wrapper behavior that fetches basket state after operations
    that modify it, providing the agent with immediate feedback.
    
    Returns:
        Modified txt with basket contents appended if applicable.
    """
    # Only apply to store benchmark and specific state-changing operations
    if benchmark != "store":
        return original_txt
    
    state_changing_ops = (
        store.Req_ApplyCoupon,
        store.Req_RemoveCoupon,
        store.Req_AddProductToBasket,
        store.Req_RemoveItemFromBasket
    )
    
    if not isinstance(job_function, state_changing_ops):
        return original_txt
    
    # Attempt to fetch current basket state
    try:
        basket_result = benchmark_client.dispatch(store.Req_ViewBasket(tool="/basket/view"))
        basket_json = basket_result.model_dump_json(exclude_none=True, exclude_unset=True)
        return f"{original_txt}\n\nBasket contents:\n{basket_json}"
    except ApiException as e:
        error_msg = e.api_error.error if hasattr(e, 'api_error') else str(e)
        return f"{original_txt}\n\nBasket contents:\n[Error fetching basket: {error_msg}. Please use Req_ViewBasket manually to verify.]"
    except Exception as e:
        return f"{original_txt}\n\nBasket contents:\n[Error fetching basket: {str(e)}. Please use Req_ViewBasket manually to verify.]"


def execute_test_coupons(function, benchmark_client) -> dict:
    """
    Test multiple coupon codes and return comparison results.
    Leaves basket in clean state (no coupon applied) after testing.
    
    Args:
        function: Req_TestCoupons instance with coupons list
        benchmark_client: SDK client for API calls
    
    Returns:
        dict with:
        - "text": formatted response string for conversation log
        - "tool_call": {request, response} dict for trace
    """
    coupons = function.coupons
    results = []
    
    for coupon_code in coupons:
        try:
            # Apply the coupon
            benchmark_client.dispatch(store.Req_ApplyCoupon(coupon=coupon_code))
            # Get basket state to measure effect
            basket = benchmark_client.dispatch(store.Req_ViewBasket())
            
            result_entry = {
                "coupon": coupon_code,
                "valid": True,
                "subtotal": basket.subtotal,
                "discount": basket.discount or 0,
                "total": basket.total,
            }
            results.append(result_entry)
            
        except ApiException as e:
            error_msg = e.api_error.error if hasattr(e, 'api_error') else str(e)
            results.append({
                "coupon": coupon_code,
                "valid": False,
                "error": error_msg,
            })
    
    # Cleanup: remove any active coupon to leave basket clean
    try:
        current_basket = benchmark_client.dispatch(store.Req_ViewBasket())
        if current_basket.coupon:
            benchmark_client.dispatch(store.Req_RemoveCoupon())
    except Exception as e:
        pass  # Best effort cleanup
    
    # Get final clean basket state
    try:
        final_basket = benchmark_client.dispatch(store.Req_ViewBasket())
        final_basket_dict = final_basket.model_dump(exclude_none=True)
    except Exception as e:
        final_basket_dict = {"error": str(e)}
    
    # Format response
    return _format_coupon_test_results(coupons, results, final_basket_dict)


def _format_coupon_test_results(coupons: list, results: list, final_basket: dict) -> dict:
    """Format coupon test results into readable text and structured data."""
    lines = ["Coupon Test Results:", "-" * 30]
    
    coupons_with_discount = []
    coupons_valid_no_discount = []
    
    for r in results:
        if r["valid"]:
            discount = r["discount"]
            subtotal = r["subtotal"]
            
            if discount > 0:
                pct = round(discount / subtotal * 100, 1) if subtotal > 0 else 0
                lines.append(f"{r['coupon']}: Valid - Subtotal: {subtotal}, Discount: {discount} ({pct}%), Total: {r['total']}")
                coupons_with_discount.append(r)
            else:
                lines.append(f"{r['coupon']}: Valid but no discount (Subtotal: {subtotal}, Total: {r['total']})")
                coupons_valid_no_discount.append(r)
        else:
            lines.append(f"{r['coupon']}: Invalid - {r.get('error', 'Unknown error')}")
    
    # Summary
    lines.append("")
    if coupons_with_discount:
        best = max(coupons_with_discount, key=lambda x: x["discount"])
        lines.append(f"Best discount: {best['coupon']} (saves {best['discount']})")
    elif coupons_valid_no_discount:
        lines.append("All coupons valid but provide no discount for current basket")
    else:
        lines.append("No valid coupons found")
    
    # Final basket state (no coupon active)
    lines.append("")
    lines.append("Final Basket State (no coupon active):")
    if "error" in final_basket:
        lines.append(f"  Error: {final_basket['error']}")
    else:
        lines.append(f"  Items: {final_basket.get('items', [])}")
        lines.append(f"  Subtotal: {final_basket.get('subtotal', 'N/A')}")
        lines.append(f"  Coupon: {final_basket.get('coupon', 'None')}")
        lines.append(f"  Total: {final_basket.get('total', 'N/A')}")
    
    text = "\n".join(lines)
    
    return {
        "text": text,
        "tool_call": {
            "request": {"tool": "test_coupons", "coupons": coupons},
            "response": {"results": results, "final_basket": final_basket}
        }
    }


def execute_get_all_products(function, benchmark_client) -> dict:
    """
    Fetch all products from the catalog with automatic pagination.
    
    Args:
        function: Req_GetAllProducts instance
        benchmark_client: SDK client for API calls
    
    Returns:
        dict with:
        - "text": formatted product list for conversation log
        - "tool_call": {request, response} dict for trace
    
    Raises:
        ApiException: If any pagination call fails (fail-fast, no partial results)
    """
    all_products = []
    offset = 0
    pages_fetched = 0
    
    while True:
        # Fetch next page
        response = benchmark_client.dispatch(store.Req_ListProducts(offset=offset, limit=0))
        pages_fetched += 1
        
        products_in_page = response.products or []
        all_products.extend(products_in_page)
        
        # Check if done
        if response.next_offset is None or response.next_offset <= 0:
            break
        
        offset = response.next_offset
    
    # Format response
    return _format_all_products_result(all_products, pages_fetched)


def _format_all_products_result(products: list, pages_fetched: int) -> dict:
    """Format all products into compact readable text and structured data."""
    if not products:
        text = "No products found in catalog."
        return {
            "text": text,
            "tool_call": {
                "request": {"tool": "get_all_products"},
                "response": {"products": [], "pages_fetched": pages_fetched}
            }
        }
    
    # Compact format: one line per product
    lines = ["Products:"]
    for p in products:
        lines.append(f"  {p.sku} | {p.name} | price={p.price} | stock={p.available}")
    
    text = "\n".join(lines)
    
    # Structured response for trace
    products_data = [
        {"sku": p.sku, "name": p.name, "price": p.price, "available": p.available}
        for p in products
    ]
    
    return {
        "text": text,
        "tool_call": {
            "request": {"tool": "get_all_products"},
            "response": {"products": products_data, "pages_fetched": pages_fetched}
        }
    }


def execute_single_call(function, benchmark_client, benchmark: str) -> dict:
    """
    Execute a single SDK tool call.
    
    Args:
        function: SDK request object (e.g., store.Req_ProductsList) or custom wrapper tool
        benchmark_client: SDK client for API calls
        benchmark: Benchmark name (e.g., "store")
    
    Returns:
        dict with:
        - "text": formatted response string for conversation log
        - "tool_call": {request, response} dict for trace
    """
    # Handle custom wrapper tools first
    if hasattr(function, 'tool'):
        if function.tool == "test_coupons":
            return execute_test_coupons(function, benchmark_client)
        elif function.tool == "get_all_products":
            return execute_get_all_products(function, benchmark_client)
    
    # Standard SDK dispatch
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

    # Automatically append basket state after state-changing operations
    txt = append_basket_state_if_needed(function, benchmark_client, benchmark, txt)
    
    return {
        "text": txt,
        "tool_call": {"request": request_dict, "response": response_dict}
    }


def execute_batch(functions_list, benchmark_client, benchmark: str) -> dict:
    """
    Execute a batch of SDK functions serially with fail-fast error handling.
    
    Args:
        functions_list: List of SDK request objects
        benchmark_client: SDK client for API calls
        benchmark: Benchmark name (e.g., "store")
    
    Returns:
        dict with:
        - "text": formatted string for conversation log
        - "tool_calls": list of {request, response} dicts for trace
    """
    text_parts = []
    tool_calls = []
    total_functions = len(functions_list)
    
    for idx, function in enumerate(functions_list, 1):
        request_json = function.model_dump_json()
        request_dict = function.model_dump()
        
        try:
            result = dispatch_with_timeout(benchmark_client, function)
            response_json = result.model_dump_json(exclude_none=True, exclude_unset=True)
            response_dict = result.model_dump(exclude_none=True, exclude_unset=True)
            
            # Auto-append basket state if applicable
            response_with_basket = append_basket_state_if_needed(function, benchmark_client, benchmark, response_json)
            
            text_parts.append(f"Request:\n`{request_json}`\n\nResponse:\n`{response_with_basket}`")
            tool_calls.append({"request": request_dict, "response": response_dict})
            
        except TimeoutError as e:
            error_json = f'{{"error": "{str(e)}"}}'
            text_parts.append(f"Request:\n`{request_json}`\n\nResponse:\n`{error_json}`")
            tool_calls.append({"request": request_dict, "response": {"error": str(e)}})
            
            if idx < total_functions:
                text_parts.append(f"\nThe rest of requests are aborted due to the error.\nExecuted: {idx} out of {total_functions} requested operations.")
            break
            
        except ApiException as e:
            text_parts.append(f"Request:\n`{request_json}`\n\nResponse:\n`{e.detail}`")
            tool_calls.append({"request": request_dict, "response": {"error": e.detail}})
            
            if idx < total_functions:
                text_parts.append(f"\nThe rest of requests are aborted due to the error.\nExecuted: {idx} out of {total_functions} requested operations.")
            break
    
    return {
        "text": "\n\n---\n\n".join(text_parts),
        "tool_calls": tool_calls
    }


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

