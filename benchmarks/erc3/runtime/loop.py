"""
ERC3 agent execution loop.

Contains:
- run_step_validator and validate_and_retry_step
- run_agent_loop: main ERC3 loop with validation and SDK execution
"""

import time
from typing import List

from langfuse import observe

from infrastructure import (
    AgentStepLimitError,
    TaskContext,
    call_llm,
    create_trace_event,
    create_validator_event,
    inject_plan,
    next_node_id,
)
from .config import VALIDATOR_REGISTRY, is_terminal_action
from .tools import execute_erc3_tools
import config


# ============================================================================
# STEP VALIDATOR (PRE-EXECUTION SAFETY)
# ============================================================================

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
    """Run StepValidator before executing a tool."""
    node_id = next_node_id(parent_node_id, sibling_count)
    validator_name = validator_config["name"]
    system_prompt = validator_config["system_prompt"]
    schema = validator_config["schema"]
    
    separator = "#" * 15
    conversation_turns = []
    for msg in conversation:
        role = msg.get("role", "").upper()
        content = msg.get("content", "")
        conversation_turns.append(f"{role}:\n{content}")
    
    conversation_section = f"\n\n{separator}\n\n".join(conversation_turns)
    
    # Format the call field as readable JSON
    import json
    agent_output_formatted = json.dumps(agent_output, indent=2, ensure_ascii=False)
    
    user_message = f"""AGENT SYSTEM PROMPT:
{agent_system_prompt}

{separator}

{conversation_section}

{separator}

PROPOSED NEXT STEP:
{agent_output_formatted}"""
    
    llm_start = time.time()
    
    
    try:
        llm_result = call_llm(
            schema=schema,
            system_prompt=system_prompt,
            conversation=[{"role": "user", "content": user_message}],
            task_ctx=task_ctx,
        )
        
        parsed = llm_result["parsed"]
        reasoning = llm_result["reasoning"]
        llm_duration = llm_result["timing"]
        
        # All validators use simple analysis field
        analysis_str = parsed.analysis
        output_for_trace = parsed.model_dump()
        
        trace.append(create_validator_event(
            node_id=node_id,
            parent_node_id=parent_node_id,
            sibling_index=sibling_count,
            validates_node_id=validates_node_id,
            validator_name=validator_name,
            validation_passed=parsed.is_valid,
            system_prompt=system_prompt,
            input_messages=[{"role": "user", "content": user_message}],
            output=output_for_trace,
            reasoning=reasoning,
            timing=llm_duration,
        ))
        
        if config.VERBOSE:
            verdict = "✓" if parsed.is_valid else "✗"
            print(f"    {verdict} {validator_name} ({llm_duration:.2f}s)")
        
        return {
            "is_valid": parsed.is_valid,
            "rejection_message": parsed.rejection_message,
            "analysis": analysis_str,
        }
    
    except Exception as exc:
        trace.append(create_validator_event(
            node_id=node_id,
            parent_node_id=parent_node_id,
            sibling_index=sibling_count,
            validates_node_id=validates_node_id,
            validator_name=validator_name,
            validation_passed=True,
            system_prompt=system_prompt,
            input_messages=[{"role": "user", "content": user_message}],
            output={"error": str(exc)},
            reasoning=None,
            timing=time.time() - llm_start,
        ))
        
        if config.VERBOSE:
            print(f"    ✗ {validator_name} error: {exc}")
        
        return {
            "is_valid": True,
            "rejection_message": "",
            "analysis": f"Validation error: {exc}",
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
    current_recursion_depth: int = 0,
) -> dict:
    """
    Validate a proposed step and retry with feedback if rejected.
    """
    agent_name = agent_config["name"]
    job = llm_result["parsed"]
    
    function_to_execute = getattr(job, "function", None)
    if function_to_execute is None:
        node_id = next_node_id(parent_node_id, step_count)
        return {
            "llm_result": llm_result,
            "step_count": step_count + 1,
            "node_id": node_id,
        }
    
    # Find first matching validator
    validator_config = None
    for v_name, v_config in VALIDATOR_REGISTRY.items():
        triggers = v_config["triggers_on_tools"]
        tool_matches = isinstance(function_to_execute, triggers)
        applies_to = v_config["applies_to_agents"]
        agent_matches = applies_to == "*" or agent_name in applies_to
        
        if tool_matches and agent_matches:
            validator_config = v_config
            break
    
    if not validator_config:
        node_id = next_node_id(parent_node_id, step_count)
        return {
            "llm_result": llm_result,
            "step_count": step_count + 1,
            "node_id": node_id,
        }
    
    max_attempts = validator_config.get("max_attempts", 1)
    current_llm_result = llm_result
    current_step_count = step_count
    
    for attempt in range(max_attempts + 1):
        job = current_llm_result["parsed"]
        function_to_execute = getattr(job, "function", None)
        
        # Tool switched outside validator's scope - re-validate with correct validator
        if not isinstance(function_to_execute, validator_config["triggers_on_tools"]):
            if current_recursion_depth >= 3:
                return {"llm_result": current_llm_result, "step_count": current_step_count, "node_id": next_node_id(parent_node_id, current_step_count)}
            return validate_and_retry_step(agent_config, schema, system_prompt, conversation, current_llm_result, 
                                                original_task, parent_node_id, current_step_count, trace, task_ctx, current_recursion_depth + 1)
        
        node_id = next_node_id(parent_node_id, current_step_count)
        
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
            return {
                "llm_result": current_llm_result,
                "step_count": current_step_count + 1,
                "node_id": node_id,
            }
        
        # Move validator event behind agent_step for chronology
        validator_event = trace.pop()
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
        trace.append(validator_event)
        
        current_step_count += 1
        
        if attempt < max_attempts:
            temp_conversation = conversation.copy()
            rejected_output = current_llm_result["output"]
            temp_conversation.append({
                "role": "assistant",
                "content": f'Planned step:\n"{rejected_output.get("next_action", "")}"\n\nPlan rejected by validator.',
            })
            temp_conversation.append({
                "role": "user",
                "content": f"Your plan was rejected: {validation['rejection_message']}\n\nPlease revise your approach.",
            })
            current_llm_result = call_llm(
                schema=schema,
                system_prompt=system_prompt,
                conversation=temp_conversation,
                task_ctx=task_ctx,
            )
    
    # Exhausted retries; proceed with last result (already logged)
    return {
        "llm_result": current_llm_result,
        "step_count": current_step_count,
        "node_id": node_id,
    }


# ============================================================================
# ERC3 AGENT LOOP
# ============================================================================

@observe()
def run_agent_loop(
    agent_config: dict,
    initial_context: str,
    benchmark_client,
    trace: List[dict],
    parent_node_id: str = "0",
    task_ctx: TaskContext = None,
) -> dict:
    """
    Run the ERC3 agent until completion or failure.
    """
    agent_name = agent_config["name"]
    system_prompt = agent_config["system_prompt"]
    schema = agent_config["schema"]
    max_steps = agent_config["max_steps"]
    
    conversation = [
        {"role": "user", "content": initial_context}
    ]
    latest_plan = None
    step_count = 0
    
    for _ in range(max_steps):
        llm_result = call_llm(
            schema=schema,
            system_prompt=system_prompt,
            conversation=conversation,
            task_ctx=task_ctx,
        )
        
        validation = validate_and_retry_step(
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
        
        llm_result = validation["llm_result"]
        node_id = validation["node_id"]
        step_count = validation["step_count"]
        
        job = llm_result["parsed"]
        latest_plan = getattr(job, "remaining_work", None)
        function_to_execute = getattr(job, "function", None)
        
        if function_to_execute is None:
            raise ValueError("Agent produced a step without a function to execute.")
        
        sdk_result = execute_erc3_tools(job, benchmark_client, task_ctx)
        
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
        
        if config.VERBOSE:
            func_name = function_to_execute.tool if hasattr(function_to_execute, "tool") else type(function_to_execute).__name__
            print(f"  {node_id} {func_name} ({llm_result['timing']:.2f}s)")
        
        func_obj = sdk_result["function"]
        assistant_content = f'Step completed.\nAction: {job.next_action}\nTool called: {func_obj.model_dump_json()}\nResponse received: {sdk_result["text"]}'
        
        inject_plan(conversation, latest_plan)
        conversation.append({"role": "assistant", "content": assistant_content})
        
        if is_terminal_action(function_to_execute):
            links = getattr(function_to_execute, "links", [])
            outcome = getattr(function_to_execute, "outcome", "error_internal")
            message = getattr(function_to_execute, "message", "")
            status = "completed" if outcome in ("ok_answer", "ok_not_found") else "refused"
            return {
                "status": status,
                "outcome": outcome,
                "message": message,
                "links": [link.model_dump() for link in links],
                "orchestrator_log": conversation,
            }
    
    raise AgentStepLimitError(f"Agent {agent_name} exceeded {max_steps} steps without completing.")

