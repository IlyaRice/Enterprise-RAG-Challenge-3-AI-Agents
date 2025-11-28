"""
Agent execution module.

Contains:
- run_agent_loop() - THE unified loop for all agents
- execute_tool_dispatch() - routes to SDK or meta-tool
- execute_meta_tool() - spawns child agent (recursive)
- handle_terminal_action() - terminal + validation logic
- run_task_analyzer() - leaf agent, single LLM call, auto-terminates
- run_bullshit_caller() - leaf agent, single LLM call, auto-terminates

Import hierarchy: This module imports from infrastructure.py and agent_types.py
"""

import time
from typing import List, Union, Callable
from langfuse import observe
from openai.lib._parsing._completions import type_to_response_format_param

import config
from infrastructure import (
    # LLM
    client, LLM_MODEL, LLM_PROVIDER,
    get_next_step,
    # Trace helpers
    next_node_id, create_llm_event,
    # SDK execution
    execute_single_call, execute_batch,
    # Conversation utilities
    build_subagent_context, format_subagent_result, inject_plan,
    # Task context for LLM logging
    TaskContext,
    # Errors
    AgentStepLimitError,
)
from agent_types import (
    AGENT_REGISTRY,
    META_TOOLS, TERMINAL_ACTIONS,
    is_meta_tool, is_terminal_action,
    get_subagent_config,
)
from subagent_prompts import (
    # TaskAnalyzer
    system_prompt_task_analyzer, TaskAnalysisResponse,
    # BullshitCaller
    system_prompt_bullshit_caller, BullshitCallerResponse, bullshit_caller_schema,
    # Terminal actions
    CompleteTask, RefuseTask,
)


# ============================================================================
# LEAF AGENTS
# ============================================================================
# These are special agents that make a single LLM call and auto-terminate.
# They do NOT go through the unified loop.

@observe()
def run_task_analyzer(task_text: str, trace: List[dict], task_ctx: TaskContext = None) -> str:
    """
    Preprocess task to expand implicit requirements before orchestration.
    
    This is a "leaf agent" - single LLM call that auto-terminates.
    Logs as proper llm_call event with node_id="0", depth=-1.
    
    Args:
        task_text: Raw task text from user
        trace: Trace list to append events to
        task_ctx: TaskContext for logging LLM usage to ERC3 platform
    
    Returns:
        The tldr_rephrased_task from structured analysis.
    """
    schema = type_to_response_format_param(TaskAnalysisResponse)
    
    # Proper system/user message separation
    messages = [
        {"role": "system", "content": system_prompt_task_analyzer},
        {"role": "user", "content": task_text},
    ]
    
    llm_start = time.time()
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        response_format=schema,
        extra_body={
            "provider": LLM_PROVIDER,
        },
    )
    llm_duration = time.time() - llm_start
    
    # Log LLM usage to ERC3 platform
    if task_ctx:
        task_ctx.log_llm(duration_sec=llm_duration, usage=response.usage)
    
    # Parse structured response
    parsed = TaskAnalysisResponse.model_validate_json(response.choices[0].message.content)
    reasoning = getattr(response.choices[0].message, 'reasoning', None)
    
    # Record as unified llm_call event
    trace.append(create_llm_event(
        node_id="0",
        parent_node_id=None,
        sibling_index=0,
        context="TaskAnalyzer",
        system_prompt=system_prompt_task_analyzer,
        input_messages=[{"role": "user", "content": task_text}],
        output=parsed.model_dump(),
        reasoning=reasoning,
        timing=llm_duration,
    ))
    
    if config.VERBOSE:
        print(f"Task rephrased to: {parsed.tldr_rephrased_task} ({llm_duration:.2f}s)")
    return parsed.tldr_rephrased_task


@observe()
def run_bullshit_caller(
    original_task: str,
    conversation_log: List[dict],
    terminal_action: Union[CompleteTask, RefuseTask],
    parent_node_id: str,
    sibling_count: int,
    trace: List[dict],
    task_ctx: TaskContext = None,
) -> dict:
    """
    Validate a CompleteTask/RefuseTask terminal action.
    
    This is a "leaf agent" - single LLM call that auto-terminates.
    Always logged as llm_call event regardless of validation result.
    
    Args:
        original_task: The task the agent was supposed to complete
        conversation_log: The agent's conversation history
        terminal_action: The CompleteTask or RefuseTask being attempted
        parent_node_id: Parent's node_id for tree structure
        sibling_count: Number of siblings at this level (for node_id generation)
        trace: Trace list to append events to
        task_ctx: TaskContext for logging LLM usage to ERC3 platform
    
    Returns:
        Dict with keys:
        - is_valid: bool - True if action is legitimate
        - rejection_message: str - Error message if not valid
        - analysis: str - Validator's analysis (always present)
    """
    # Generate node ID for this BullshitCaller call
    node_id = next_node_id(parent_node_id, sibling_count)
    
    action_type = "complete_task" if isinstance(terminal_action, CompleteTask) else "refuse_task"
    
    # Build user message with validation context
    conversation_summary = []
    for msg in conversation_log:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        conversation_summary.append(f"[{role}]: {content}")
    
    user_message = f"""Original task:
{original_task}

Agent's conversation history:
{chr(10).join(conversation_summary)}

Terminal action attempted: {action_type}
Agent's report: {terminal_action.report}

Validate this terminal action. Is the agent actually done, or are they bullshitting?"""

    llm_start = time.time()
    
    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt_bullshit_caller},
                {"role": "user", "content": user_message},
            ],
            response_format=bullshit_caller_schema,
            extra_body={
                "provider": LLM_PROVIDER,
            },
        )
        
        llm_duration = time.time() - llm_start
        
        # Log LLM usage to ERC3 platform
        if task_ctx:
            task_ctx.log_llm(duration_sec=llm_duration, usage=response.usage)
        
        content = response.choices[0].message.content
        parsed = BullshitCallerResponse.model_validate_json(content)
        reasoning = getattr(response.choices[0].message, 'reasoning', None)
        
        # ALWAYS log as unified llm_call event
        trace.append(create_llm_event(
            node_id=node_id,
            parent_node_id=parent_node_id,
            sibling_index=sibling_count,
            context="BullshitCaller",
            system_prompt=system_prompt_bullshit_caller,
            input_messages=[{"role": "user", "content": user_message}],
            output={
                "terminal_action": action_type,
                **parsed.model_dump()
            },
            reasoning=reasoning,
            timing=llm_duration,
        ))
        
        if config.VERBOSE:
            if not parsed.is_valid:
                print(f"    🐂💩 Bullshit called! ({llm_duration:.2f}s)")
                print(f"    → {parsed.rejection_message}")
            else:
                print(f"    ✓ Validated ({llm_duration:.2f}s)")
        
        return {
            "is_valid": parsed.is_valid,
            "rejection_message": parsed.rejection_message,
            "analysis": parsed.analysis
        }
        
    except Exception as e:
        # On error, let the action proceed (fail-open)
        # Still log the attempt
        trace.append(create_llm_event(
            node_id=node_id,
            parent_node_id=parent_node_id,
            sibling_index=sibling_count,
            context="BullshitCaller",
            system_prompt=system_prompt_bullshit_caller,
            input_messages=[{"role": "user", "content": user_message}],
            output={"error": str(e)},
            reasoning=None,
            timing=time.time() - llm_start,
        ))
        
        if config.VERBOSE:
            print(f"    ⚠ Bullshit caller error: {e}")
        return {
            "is_valid": True,
            "rejection_message": "",
            "analysis": f"Validation error: {e}"
        }


# ============================================================================
# TOOL EXECUTION
# ============================================================================

def execute_sdk_tools(
    job,
    benchmark_client,
    benchmark: str,
) -> dict:
    """
    Execute SDK tool(s) from agent's job output.
    
    Handles both single and batch call modes.
    
    Args:
        job: Parsed LLM output with call.function or call.functions
        benchmark_client: SDK client for API calls
        benchmark: Benchmark name (e.g., "store")
    
    Returns:
        dict with:
        - "text": Formatted response for conversation
        - "tool_calls": List of {request, response} dicts for trace
        - "function": The function(s) executed (for display)
    """
    if job.call.call_mode == "single":
        function = job.call.function
        result = execute_single_call(function, benchmark_client, benchmark)
        return {
            "text": result["text"],
            "tool_calls": [result["tool_call"]],
            "function": function,
        }
    elif job.call.call_mode == "batch":
        functions = job.call.functions
        result = execute_batch(functions, benchmark_client, benchmark)
        return {
            "text": result["text"],
            "tool_calls": result["tool_calls"],
            "function": functions,
        }
    else:
        raise ValueError(f"Unknown call_mode: {job.call.call_mode}")


def execute_meta_tool(
    meta_tool_instance,
    orchestrator_log: List[dict],
    benchmark_client,
    trace: List[dict],
    parent_node_id: str,
    task_ctx: TaskContext = None,
) -> dict:
    """
    Execute a meta-tool by spawning a sub-agent.
    
    This recursively calls run_agent_loop for the appropriate sub-agent type.
    
    Args:
        meta_tool_instance: Instance of ProductExplorer, CouponOptimizer, etc.
        orchestrator_log: Orchestrator's full conversation (for context building)
        benchmark_client: SDK client for sub-agent to use
        trace: Trace list to append events to
        parent_node_id: Orchestrator's node ID (e.g., "2")
        task_ctx: TaskContext for logging LLM usage to ERC3 platform
    
    Returns:
        dict with subagent_name, status, report
    """
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
    )
    
    return {
        "subagent_name": agent_config["name"],
        "status": result["status"],
        "report": result["report"],
    }


# ============================================================================
# TERMINAL ACTION HANDLING
# ============================================================================

def handle_terminal_with_validation(
    terminal_action: Union[CompleteTask, RefuseTask],
    original_task: str,
    conversation_log: List[dict],
    node_id: str,
    validation_count: int,
    max_validations: int,
    trace: List[dict],
    task_ctx: TaskContext = None,
) -> dict:
    """
    Handle terminal action with optional BullshitCaller validation.
    
    Args:
        terminal_action: The CompleteTask or RefuseTask
        original_task: Task being validated against
        conversation_log: Agent's conversation history
        node_id: Current node's ID (parent for BullshitCaller)
        validation_count: How many validations have failed so far
        max_validations: Maximum before forcing termination
        trace: Trace list to append events to
        task_ctx: TaskContext for logging LLM usage to ERC3 platform
    
    Returns:
        dict with:
        - "should_terminate": bool - True if agent should stop
        - "is_valid": bool - True if validation passed
        - "rejection_message": str - Message if validation failed
        - "analysis": str - Validator's analysis
    """
    # Run bullshit caller validation
    validation = run_bullshit_caller(
        original_task=original_task,
        conversation_log=conversation_log,
        terminal_action=terminal_action,
        parent_node_id=node_id,
        sibling_count=0,  # BullshitCaller is always first child of terminal node
        trace=trace,
        task_ctx=task_ctx,
    )
    
    is_limit_reached = validation_count >= max_validations - 1
    
    if not validation["is_valid"] and not is_limit_reached:
        # Validation failed, agent should continue
        return {
            "should_terminate": False,
            "is_valid": False,
            "rejection_message": validation["rejection_message"],
            "analysis": validation["analysis"],
        }
    
    # Either valid or limit reached - agent terminates
    return {
        "should_terminate": True,
        "is_valid": validation["is_valid"] or is_limit_reached,
        "rejection_message": "" if validation["is_valid"] else validation["rejection_message"],
        "analysis": validation["analysis"],
        "limit_reached": is_limit_reached and not validation["is_valid"],
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
) -> dict:
    """
    THE unified agent loop that works for both orchestrator and subagents.
    
    This is the core execution engine. It handles:
    - LLM calls via get_next_step()
    - Terminal action validation via BullshitCaller
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
    
    Returns:
        dict with status, report (and for orchestrator: orchestrator_log)
    """
    # Extract config
    agent_name = agent_config["name"]
    base_system_prompt = agent_config["system_prompt"]
    schema = agent_config["schema"]
    max_steps = agent_config["max_steps"]
    max_validations = agent_config.get("max_validations", 2)
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
    validation_count = 0
    step_count = 0
    
    # Main loop
    for i in range(max_steps):
        # Get LLM decision
        llm_result = get_next_step(schema, system_prompt, conversation, task_ctx=task_ctx)
        job = llm_result["parsed"]
        latest_plan = getattr(job, 'remaining_work', None)
        
        # Generate node ID for this step
        node_id = next_node_id(parent_node_id, step_count)
        step_count += 1
        
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
            action_type = "✓" if isinstance(function_to_execute, CompleteTask) else "✗"
            if config.VERBOSE:
                print(f"  {node_id} {action_type} {function_to_execute.report}")
            
            # Log the LLM call (terminal action, no tool_calls)
            trace.append(create_llm_event(
                node_id=node_id,
                parent_node_id=parent_node_id,
                sibling_index=step_count - 1,
                context=agent_name,
                system_prompt=system_prompt,
                input_messages=conversation.copy(),
                output=llm_result["output"],
                reasoning=llm_result["reasoning"],
                timing=llm_result["timing"],
            ))
            
            # Run validation
            validation_result = handle_terminal_with_validation(
                terminal_action=function_to_execute,
                original_task=initial_context,
                conversation_log=full_log,
                node_id=node_id,
                validation_count=validation_count,
                max_validations=max_validations,
                trace=trace,
                task_ctx=task_ctx,
            )
            
            if validation_result["should_terminate"]:
                # Agent terminates
                status = "completed" if isinstance(function_to_execute, CompleteTask) else "refused"
                report = function_to_execute.report
                
                # Add validator note if limit reached
                if validation_result.get("limit_reached"):
                    validator_note = f"\n\n[Validator note after {max_validations} checks: {validation_result['analysis']}]"
                    report = report + validator_note
                    if config.VERBOSE:
                        print(f"    ⚠ Limit reached, allowing termination with validator note")
                
                result = {"status": status, "report": report}
                if orchestrator_log is not None:
                    result["orchestrator_log"] = orchestrator_log
                return result
            
            # Validation failed - continue loop
            validation_count += 1
            tool_name = "complete_task" if isinstance(function_to_execute, CompleteTask) else "refuse_task"
            error_response = f'{{"error": "Validation failed: {validation_result["rejection_message"]}"}}'
            
            # Update conversation
            inject_plan(conversation, latest_plan)
            conversation.append({
                "role": "assistant",
                "content": f'Planned step:\n"{job.next_action}"\n\nRequest:\n`{{"tool": "{tool_name}", "report": "{function_to_execute.report}"}}`\n\nResponse:\n`{error_response}`'
            })
            
            # Update full_log
            inject_plan(full_log, latest_plan)
            full_log.append({
                "role": "assistant",
                "content": f'Planned step:\n"{job.next_action}"\n\nRequest:\n`{{"tool": "{tool_name}", "report": "{function_to_execute.report}"}}`\n\nResponse:\n`{error_response}`'
            })
            continue
        
        # Handle meta-tools (orchestrator delegating to subagent)
        if tool_type == "meta" and is_meta_tool(function_to_execute):
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
                task_ctx=task_ctx,
            )
            
            # Log the orchestrator LLM call with subagent_result attached
            trace.append(create_llm_event(
                node_id=node_id,
                parent_node_id=parent_node_id,
                sibling_index=step_count - 1,
                context=agent_name,
                system_prompt=system_prompt,
                input_messages=conversation.copy(),
                output=llm_result["output"],
                reasoning=llm_result["reasoning"],
                timing=llm_result["timing"],
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
        sdk_result = execute_sdk_tools(job, benchmark_client, "store")
        
        # Log the LLM call with tool_calls attached
        trace.append(create_llm_event(
            node_id=node_id,
            parent_node_id=parent_node_id,
            sibling_index=step_count - 1,
            context=agent_name,
            system_prompt=system_prompt,
            input_messages=conversation.copy(),
            output=llm_result["output"],
            reasoning=llm_result["reasoning"],
            timing=llm_result["timing"],
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

