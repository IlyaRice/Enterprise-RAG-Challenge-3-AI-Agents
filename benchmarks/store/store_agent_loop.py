"""
Store benchmark agent execution loop.

This module contains THE unified loop for store agents (orchestrator + subagents),
including pre-execution validation, meta-tool delegation, SDK tool execution,
and trace logging.
"""

import time
from typing import List, Callable
from langfuse import observe

from infrastructure import (
    # LLM
    call_llm,
    # Trace helpers
    next_node_id, create_trace_event, create_validator_event,
    # Conversation utilities
    build_subagent_context, format_subagent_result, inject_plan,
    # Task context for LLM logging
    TaskContext,
    # Errors
    AgentStepLimitError,
)

# Import from store benchmark (execute_meta_tool is store-specific)
from benchmarks.store.agent_config import (
    VALIDATOR_REGISTRY,
    is_meta_tool, is_terminal_action,
    get_subagent_config,
)
from benchmarks.store.prompts import (
    # Validators
    StepValidatorResponse,
    # ProductExplorer
    ProductExplorerResponse, ProductExplorer,
    prompt_product_explorer,
)
from benchmarks.store.tools import execute_get_all_products, execute_store_tools

import config

# ============================================================================
# VALIDATORS
# ============================================================================
# Validators: Triggered by tools via VALIDATOR_REGISTRY, not agents

@observe()
def run_step_validator(
    validator_config: dict,
    original_task: str,
    agent_system_prompt: str,
    conversation: List[dict],
    agent_output: dict,
    validates_node_id: str,
    parent_node_id: str,
    sibling_count: int,
    trace: List[dict],
    task_ctx: TaskContext = None,
) -> dict:
    """
    Run StepValidator on an agent's planned action BEFORE execution.
    
    This validates plans before they execute, catching mistakes early.
    Different from run_validator() which validates terminal actions after.
    
    Args:
        validator_config: Config from VALIDATOR_REGISTRY
        original_task: The original task (for context)
        agent_system_prompt: The agent's system prompt (to understand capabilities)
        conversation: The conversation the agent saw
        agent_output: The agent's full output (current_state, remaining_work, next_action, call)
        validates_node_id: The node_id of the step being validated
        parent_node_id: Parent's node_id for tree structure
        sibling_count: Number of siblings at this level (for node_id generation)
        trace: Trace list to append events to
        task_ctx: TaskContext for logging LLM usage to ERC3 platform
    
    Returns:
        Dict with keys:
        - is_valid: bool - True if plan is approved
        - rejection_message: str - What's wrong if not valid
        - analysis: str - Validator's analysis
    """
    # Generate node ID for this validator call
    node_id = next_node_id(parent_node_id, sibling_count)
    
    # Get validator config
    validator_name = validator_config["name"]
    system_prompt = validator_config["system_prompt"]
    schema = validator_config["schema"]
    
    # Build conversation summary
    conversation_summary = []
    for msg in conversation:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        conversation_summary.append(f"[{role}]: {content}")
    
    # Build user message with full validation context
    user_message = f"""Original task:
{original_task}

Agent's system prompt (defines agent capabilities):
{agent_system_prompt}

Conversation history (what agent has seen):
{"\n".join(conversation_summary)}

Agent's planned next step:
- Current state: {agent_output.get('current_state', 'N/A')}
- Remaining work: {agent_output.get('remaining_work', [])}
- Next action: {agent_output.get('next_action', 'N/A')}
- Call: {agent_output.get('call', {})}

Validate this plan. Is it sound, or are there issues?"""

    llm_start = time.time()
    
    try:
        llm_result = call_llm(
            schema=StepValidatorResponse,
            system_prompt=system_prompt,
            conversation=[{"role": "user", "content": user_message}],
            task_ctx=task_ctx,
        )
        
        parsed = llm_result["parsed"]
        reasoning = llm_result["reasoning"]
        llm_duration = llm_result["timing"]
        
        # Log as validator_step event
        trace.append(create_validator_event(
            node_id=node_id,
            parent_node_id=parent_node_id,
            sibling_index=sibling_count,
            validates_node_id=validates_node_id,
            validator_name=validator_name,
            validation_passed=parsed.is_valid,
            system_prompt=system_prompt,
            input_messages=[{"role": "user", "content": user_message}],
            output=parsed.model_dump(),
            reasoning=reasoning,
            timing=llm_duration,
        ))
        
        if config.VERBOSE:
            if not parsed.is_valid:
                print(f"    ✗ {validator_name} rejected ({llm_duration:.2f}s): {parsed.rejection_message}")
            else:
                print(f"    ✓ {validator_name} approved ({llm_duration:.2f}s)")
        
        return {
            "is_valid": parsed.is_valid,
            "rejection_message": parsed.rejection_message,
            "analysis": parsed.analysis
        }
        
    except Exception as e:
        # On error, let the plan proceed (fail-open)
        trace.append(create_validator_event(
            node_id=node_id,
            parent_node_id=parent_node_id,
            sibling_index=sibling_count,
            validates_node_id=validates_node_id,
            validator_name=validator_name,
            validation_passed=True,  # fail-open
            system_prompt=system_prompt,
            input_messages=[{"role": "user", "content": user_message}],
            output={"error": str(e)},
            reasoning=None,
            timing=time.time() - llm_start,
        ))
        
        if config.VERBOSE:
            print(f"    ў?я {validator_name} error: {e}")
        return {
            "is_valid": True,
            "rejection_message": "",
            "analysis": f"Validation error: {e}"
        }


def validate_and_retry_step(
    agent_config: dict,
    schema,
    system_prompt: str,
    conversation: List[dict],
    llm_result: dict,
    original_task: str,
    parent_node_id: str,
    step_count: int,
    trace: List[dict],
    task_ctx: TaskContext = None,
) -> dict:
    """
    Pre-execution validation with retry capability.
    
    Validates agent's plan BEFORE execution. If rejected, agent replans
    with feedback (but rejection is removed from final conversation).
    
    Only logs REJECTED attempts to trace. The final approved attempt
    is NOT logged here - the caller logs it with execution results.
    
    Args:
        agent_config: Agent configuration from registry
        schema: Agent's output schema for call_llm
        system_prompt: Agent's system prompt
        conversation: Current conversation (will NOT be modified)
        llm_result: Initial LLM result from call_llm
        original_task: Original task for context
        parent_node_id: Parent node ID for trace
        step_count: Current step count (for node_id generation)
        trace: Trace list to append events to
        task_ctx: TaskContext for logging
    
    Returns:
        dict with:
        - "llm_result": The approved (or force-approved) LLM result
        - "step_count": Updated step count (may have incremented due to retries)
        - "node_id": The node_id for the approved step (to be logged by caller)
    """
    agent_name = agent_config["name"]
    job = llm_result["parsed"]
    
    # Get the function to check for validator matching
    if hasattr(job.call, 'function'):
        function_to_execute = job.call.function
    elif hasattr(job.call, 'functions'):
        function_to_execute = job.call.functions[0] if job.call.functions else None
    else:
        function_to_execute = None
    
    if function_to_execute is None:
        # No function, can't validate
        node_id = next_node_id(parent_node_id, step_count)
        return {
            "llm_result": llm_result,
            "step_count": step_count + 1,
            "node_id": node_id,
        }
    
    # Find StepValidator for this agent/tool (excluding terminal_validator by name)
    step_validators = []
    for key, validator_cfg in VALIDATOR_REGISTRY.items():
        if validator_cfg["name"] == "StepValidator":
            triggers = validator_cfg["triggers_on_tools"]
            tool_matches = triggers == "*" or isinstance(function_to_execute, triggers)
            applies_to = validator_cfg["applies_to_agents"]
            agent_matches = applies_to == "*" or agent_name in applies_to
            if tool_matches and agent_matches:
                step_validators.append(validator_cfg)
    
    if not step_validators:
        # No StepValidator for this agent/tool - proceed without validation
        node_id = next_node_id(parent_node_id, step_count)
        return {
            "llm_result": llm_result,
            "step_count": step_count + 1,
            "node_id": node_id,
        }
    
    validator_config = step_validators[0]
    max_attempts = validator_config.get("max_attempts", 2)
    
    current_llm_result = llm_result
    current_step_count = step_count
    
    # Loop through max_attempts + 1 times to validate the final attempt too
    for attempt in range(max_attempts + 1):
        job = current_llm_result["parsed"]
        node_id = next_node_id(parent_node_id, current_step_count)
        
        # Run StepValidator (appends validator_step to trace)
        validation = run_step_validator(
            validator_config=validator_config,
            original_task=original_task,
            agent_system_prompt=system_prompt,
            conversation=conversation,
            agent_output=current_llm_result["output"],
            validates_node_id=node_id,
            parent_node_id=node_id,
            sibling_count=0,
            trace=trace,
            task_ctx=task_ctx,
        )
        
        if validation["is_valid"]:
            # Approved - return without logging (caller will log with execution results)
            return {
                "llm_result": current_llm_result,
                "step_count": current_step_count + 1,
                "node_id": node_id,
            }
        
        # Rejected - reorder trace for chronological correctness
        # validator_step was just appended, but agent_step should come first
        validator_event = trace.pop()  # Remove validator_step temporarily
        
        # Log agent_step (the rejected attempt)
        trace.append(create_trace_event(
            node_id=node_id,
            parent_node_id=parent_node_id,
            sibling_index=current_step_count,
            context=agent_name,
            system_prompt=system_prompt,
            input_messages=conversation.copy(),
            output=current_llm_result["output"],
            reasoning=current_llm_result["reasoning"],
            timing=current_llm_result["timing"],
            event_type="agent_step",
        ))
        
        # Re-add validator_step after agent_step (correct chronological order)
        trace.append(validator_event)
        
        current_step_count += 1
        
        # Retry if not the last attempt
        if attempt < max_attempts:
            # Build temp conversation with rejection for retry
            temp_conversation = conversation.copy()
            
            # Add the rejected plan as assistant message
            rejected_output = current_llm_result["output"]
            temp_conversation.append({
                "role": "assistant",
                "content": f'Planned step:\n"{rejected_output.get("next_action", "")}"\n\nPlan rejected by validator.'
            })
            
            # Add rejection feedback as user message
            temp_conversation.append({
                "role": "user",
                "content": f"Your plan was rejected: {validation['rejection_message']}\n\nPlease reconsider and provide a revised plan."
            })
            
            # Get new plan from agent
            current_llm_result = call_llm(schema, system_prompt, temp_conversation, task_ctx=task_ctx)
    
    # All attempts exhausted and rejected - force approve the last one
    # (Already logged in the loop above)
    return {
        "llm_result": current_llm_result,
        "step_count": current_step_count,
        "node_id": node_id,
    }


# ============================================================================
# META-TOOL EXECUTION (Store-specific)
# ============================================================================

@observe()
def execute_product_explorer_direct(
    task_string: str,
    orchestrator_log: List[dict],
    benchmark_client,
    trace: List[dict],
    parent_node_id: str,
    task_ctx: TaskContext = None,
) -> dict:
    """
    Execute ProductExplorer with single LLM call (no agent loop).
    
    Automatically fetches all products and asks LLM to analyze them.
    
    Args:
        task_string: The task for ProductExplorer
        orchestrator_log: Orchestrator's full conversation (for context building)
        benchmark_client: SDK client for API calls
        trace: Trace list to append events to
        parent_node_id: Orchestrator's node ID (e.g., "2")
        task_ctx: TaskContext for logging LLM usage to ERC3 platform
    
    Returns:
        dict with subagent_name="ProductExplorer", status="completed", report=...
    """
    # Generate node ID for this call
    node_id = next_node_id(parent_node_id, 0)
    
    # Step 1: Fetch all products automatically
    products_result = execute_get_all_products(None, benchmark_client)
    products_text = products_result["text"]
    
    # Step 2: Build context for LLM
    subagent_context = build_subagent_context(orchestrator_log, task_string)
    
    # Step 3: Build prompt with task + products
    user_message = f"""{subagent_context}

PRODUCT CATALOG:
{products_text}

Analyze the products above and answer the task."""
    
    # Step 4: Single LLM call with simple schema
    llm_start = time.time()
    
    try:
        llm_result = call_llm(
            schema=ProductExplorerResponse,
            system_prompt=prompt_product_explorer,
            conversation=[{"role": "user", "content": user_message}],
            task_ctx=task_ctx,
        )
        
        parsed = llm_result["parsed"]
        reasoning = llm_result["reasoning"]
        llm_duration = llm_result["timing"]
        
        # Step 5: Log to trace
        trace.append(create_trace_event(
            node_id=node_id,
            parent_node_id=parent_node_id,
            sibling_index=0,
            context="ProductExplorer",
            system_prompt=prompt_product_explorer,
            input_messages=[{"role": "user", "content": user_message}],
            output=parsed.model_dump(),
            reasoning=reasoning,
            timing=llm_duration,
            event_type="agent_step",
            tool_calls=[products_result["tool_call"]],
        ))
        
        if config.VERBOSE:
            print(f"  {node_id} ProductExplorer ({llm_duration:.2f}s)")
        
        # Step 6: Return result
        return {
            "subagent_name": "ProductExplorer",
            "status": "completed",
            "report": parsed.report,
        }
        
    except Exception as e:
        # On error, return refusal
        error_report = f"Failed to analyze products: {str(e)}"
        trace.append(create_trace_event(
            node_id=node_id,
            parent_node_id=parent_node_id,
            sibling_index=0,
            context="ProductExplorer",
            system_prompt=prompt_product_explorer,
            input_messages=[{"role": "user", "content": user_message}],
            output={"error": str(e)},
            reasoning=None,
            timing=time.time() - llm_start,
            event_type="agent_step",
        ))
        
        return {
            "subagent_name": "ProductExplorer",
            "status": "refused",
            "report": error_report,
        }


def execute_meta_tool(
    meta_tool_instance,
    orchestrator_log: List[dict],
    benchmark_client,
    trace: List[dict],
    parent_node_id: str,
    tool_executor: Callable,
    task_ctx: TaskContext = None,
) -> dict:
    """
    Execute a meta-tool by spawning a sub-agent.
    
    ProductExplorer is handled specially with execute_product_explorer_direct().
    Other subagents use run_agent_loop.
    
    Args:
        meta_tool_instance: Instance of ProductExplorer, BasketBuilder, etc.
        orchestrator_log: Orchestrator's full conversation (for context building)
        benchmark_client: SDK client for API calls
        trace: Trace list to append events to
        parent_node_id: Orchestrator's node ID (e.g., "2")
        tool_executor: Function to execute SDK tools (passed to subagent loop)
        task_ctx: TaskContext for logging LLM usage to ERC3 platform
    
    Returns:
        dict with subagent_name, status, report
    """
    # Special handling for ProductExplorer
    if isinstance(meta_tool_instance, ProductExplorer):
        return execute_product_explorer_direct(
            task_string=meta_tool_instance.task,
            orchestrator_log=orchestrator_log,
            benchmark_client=benchmark_client,
            trace=trace,
            parent_node_id=parent_node_id,
            task_ctx=task_ctx,
        )
    
    # Get the task string from the meta-tool
    task_string = meta_tool_instance.task
    
    # Get agent config for this meta-tool type
    agent_config = get_subagent_config(meta_tool_instance)
    
    # Build context for subagent
    subagent_context = build_subagent_context(orchestrator_log, task_string)
    
    # Run the subagent via unified loop
    result = run_agent_loop(
        agent_config=agent_config,
        initial_context=subagent_context,
        benchmark_client=benchmark_client,
        trace=trace,
        parent_node_id=parent_node_id,
        orchestrator_log=None,  # Subagents don't pass this down
        task_ctx=task_ctx,
        tool_executor=tool_executor,
    )
    
    return {
        "subagent_name": agent_config["name"],
        "status": result["status"],
        "report": result["report"],
    }


# ============================================================================
# UNIFIED AGENT LOOP
# ============================================================================

@observe()
def run_agent_loop(
    agent_config: dict,
    initial_context: str,
    benchmark_client,
    trace: List[dict],
    parent_node_id: str,
    orchestrator_log: List[dict] | None = None,
    task_ctx: TaskContext = None,
    tool_executor: Callable = None,
) -> dict:
    """
    THE unified agent loop that works for both orchestrator and subagents.
    
    This is the core execution engine. It handles:
    - LLM calls via call_llm()
    - Pre-execution validation via StepValidator
    - Tool execution (SDK or meta-tool dispatch)
    - Conversation management
    - Trace event generation
    
    Args:
        agent_config: Configuration from AGENT_REGISTRY
        initial_context: Initial user message (task or subagent context)
        benchmark_client: SDK client for API calls
        trace: Trace list to append events to
        parent_node_id: Parent's node ID ("0" for orchestrator, "N" for subagent under step N)
        orchestrator_log: Orchestrator's full log (only for orchestrator, None for subagents)
        task_ctx: TaskContext for logging LLM usage to ERC3 platform
        tool_executor: Function to execute SDK tools (benchmark-specific)
    
    Returns:
        dict with status, report (and for orchestrator: orchestrator_log)
    """
    # Extract config
    agent_name = agent_config["name"]
    base_system_prompt = agent_config["system_prompt"]
    schema = agent_config["schema"]
    max_steps = agent_config["max_steps"]
    tool_type = agent_config.get("tool_type", "sdk")
    
    # Build system prompt
    system_prompt = f"{base_system_prompt}first step"
    
    # Initialize conversation (without system prompt - stored separately)
    conversation = [{"role": "user", "content": initial_context}]
    
    # For orchestrator, also maintain full log for subagent context
    if orchestrator_log is not None:
        # Orchestrator mode - orchestrator_log was passed and should be updated
        full_log = orchestrator_log
        if not full_log:  # If empty, initialize
            full_log.append({"role": "system", "content": system_prompt})
            full_log.append({"role": "user", "content": initial_context})
    else:
        # Subagent mode - create local full_log for validation
        full_log = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": initial_context},
        ]
    
    # Track state
    latest_plan = None
    step_count = 0
    
    # Main loop
    for i in range(max_steps):
        # Get LLM decision
        llm_result = call_llm(schema, system_prompt, conversation, task_ctx=task_ctx)
        
        # Pre-execution validation (StepValidator)
        # May produce new llm_result if rejected and retried
        # Logs rejected attempts to trace; approved attempt logged by branches below
        validation_result = validate_and_retry_step(
            agent_config=agent_config,
            schema=schema,
            system_prompt=system_prompt,
            conversation=conversation,
            llm_result=llm_result,
            original_task=initial_context,
            parent_node_id=parent_node_id,
            step_count=step_count,
            trace=trace,
            task_ctx=task_ctx,
        )
        
        # Use validated result
        llm_result = validation_result["llm_result"]
        step_count = validation_result["step_count"]
        node_id = validation_result["node_id"]
        
        job = llm_result["parsed"]
        latest_plan = getattr(job, 'remaining_work', None)
        
        # Get the function to execute
        if hasattr(job.call, 'function'):
            function_to_execute = job.call.function
        elif hasattr(job.call, 'functions'):
            # Batch mode - first check if these are terminal (they shouldn't be)
            function_to_execute = job.call.functions
        else:
            raise ValueError(f"Unknown call structure: {job.call}")
        
        # Handle terminal actions
        if is_terminal_action(function_to_execute):
            action_type = "✓" if function_to_execute.outcome == "success" else "✗"
            if config.VERBOSE:
                print(f"  {node_id} {action_type} {function_to_execute.report}")
            
            # Log the agent step (terminal action, no tool_calls)
            trace.append(create_trace_event(
                node_id=node_id,
                parent_node_id=parent_node_id,
                sibling_index=step_count - 1,
                context=agent_name,
                system_prompt=system_prompt,
                input_messages=conversation.copy(),
                output=llm_result["output"],
                reasoning=llm_result["reasoning"],
                timing=llm_result["timing"],
                event_type="agent_step",
            ))
            
            # Agent terminates - map outcome to status
            status = "completed" if function_to_execute.outcome == "success" else "refused"
            report = function_to_execute.report
            
            result = {"status": status, "report": report}
            if orchestrator_log is not None:
                result["orchestrator_log"] = orchestrator_log
            return result
        
        # Handle meta-tools (orchestrator delegating to subagent)
        if tool_type == "meta" and is_meta_tool(function_to_execute):
            # Get subagent name (ProductExplorer handled specially, others from registry)
            if isinstance(function_to_execute, ProductExplorer):
                subagent_name = "ProductExplorer"
            else:
                subagent_name = get_subagent_config(function_to_execute)["name"]
            
            task_string = function_to_execute.task
            
            if config.VERBOSE:
                print(f"Step {node_id}: {subagent_name} - {task_string} ({llm_result['timing']:.2f}s)")
                if latest_plan:
                    print(f"  Plan: {' → '.join(latest_plan)}")
            
            # Execute meta-tool (spawns subagent)
            subagent_result = execute_meta_tool(
                meta_tool_instance=function_to_execute,
                orchestrator_log=full_log,
                benchmark_client=benchmark_client,
                trace=trace,
                parent_node_id=node_id,
                tool_executor=tool_executor,
                task_ctx=task_ctx,
            )
            
            # Log the orchestrator agent step with subagent_result attached
            trace.append(create_trace_event(
                node_id=node_id,
                parent_node_id=parent_node_id,
                sibling_index=step_count - 1,
                context=agent_name,
                system_prompt=system_prompt,
                input_messages=conversation.copy(),
                output=llm_result["output"],
                reasoning=llm_result["reasoning"],
                timing=llm_result["timing"],
                event_type="agent_step",
                subagent_result={
                    "subagent_name": subagent_result["subagent_name"],
                    "status": subagent_result["status"],
                    "report": subagent_result["report"],
                },
            ))
            
            # Format sub-agent result
            result_formatted = format_subagent_result(
                subagent_name=subagent_result["subagent_name"],
                status=subagent_result["status"],
                report=subagent_result["report"]
            )
            
            # Update conversation
            inject_plan(conversation, latest_plan)
            conversation.append({
                "role": "assistant",
                "content": f'Planned step:\n"{job.next_action}"\n\nDelegated to: {subagent_result["subagent_name"]}\nTask: {task_string}'
            })
            conversation.append({"role": "user", "content": result_formatted})
            
            # Update full_log
            inject_plan(full_log, latest_plan)
            full_log.append({
                "role": "assistant",
                "content": f'Planned step:\n"{job.next_action}"\n\nDelegated to: {subagent_result["subagent_name"]}\nTask: {task_string}'
            })
            full_log.append({"role": "user", "content": result_formatted})
            continue
        
        # Handle SDK tools (subagent executing SDK calls)
        sdk_result = tool_executor(job, benchmark_client)
        
        # Log the agent step with tool_calls attached
        trace.append(create_trace_event(
            node_id=node_id,
            parent_node_id=parent_node_id,
            sibling_index=step_count - 1,
            context=agent_name,
            system_prompt=system_prompt,
            input_messages=conversation.copy(),
            output=llm_result["output"],
            reasoning=llm_result["reasoning"],
            timing=llm_result["timing"],
            event_type="agent_step",
            tool_calls=sdk_result["tool_calls"],
        ))
        
        # Verbose output
        if config.VERBOSE:
            func = sdk_result["function"]
            if isinstance(func, list):
                tools = " | ".join(f.tool if hasattr(f, 'tool') else str(type(f).__name__) for f in func)
            else:
                tools = func.tool if hasattr(func, 'tool') else str(type(func).__name__)
            
            errors = [tc["response"].get("error") for tc in sdk_result["tool_calls"] if "error" in tc["response"]]
            if errors:
                print(f"  {node_id} ✗ {tools}: {errors[0]}")
            else:
                print(f"  {node_id} {tools} ({llm_result['timing']:.2f}s)")
        
        # Build assistant message content
        if job.call.call_mode == "single":
            func = sdk_result["function"]
            assistant_content = f'Planned step:\n"{job.next_action}"\n\nRequest:\n`{func.model_dump_json()}`\n\nResponse:\n`{sdk_result["text"]}`'
        else:
            assistant_content = f'Planned step:\n"{job.next_action}"\n\n{sdk_result["text"]}'
        
        # Update conversation
        inject_plan(conversation, latest_plan)
        conversation.append({"role": "assistant", "content": assistant_content})
        
        # Update full_log
        inject_plan(full_log, latest_plan)
        full_log.append({"role": "assistant", "content": assistant_content})
    
    # Agent exceeded step limit
    raise AgentStepLimitError(f"Agent {agent_name} exceeded {max_steps}-step limit without completing")
