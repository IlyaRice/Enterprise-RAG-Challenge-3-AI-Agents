"""
ERC3 benchmark agent execution.

Contains LLM-calling functions for the ERC3 agent pipeline:
- run_context_builder(): Selects relevant context blocks for a task
- run_rule_builder(): Extracts relevant rule chunks from wiki files
- run_erc3_agent_loop(): Main orchestrator loop with StepValidator
"""

import json
import time
from pathlib import Path
from typing import List, Any
from concurrent.futures import ThreadPoolExecutor

from langfuse import observe, get_client
import config
from infrastructure import (
    AgentStepLimitError,
    TaskContext,
    call_llm,
    create_trace_event,
    create_validator_event,
    inject_plan,
    next_node_id,
)
from .agent_config import (
    VALIDATOR_REGISTRY,
    is_terminal_action,
)
from .tools import CollectedContext, execute_erc3_tools
from .prompts import (
    ContextSelection,
    ERC3StepValidatorResponse,
    RuleSelection,
    system_prompt_context_builder,
    system_prompt_rule_builder,
)


# ============================================================================
# RULE BUILDER HELPERS
# ============================================================================

def _get_rule_files(wiki_dir: str) -> List[dict]:
    """
    Get list of wiki files that contain rules.
    
    Returns:
        List of dicts with 'path' (database format) and 'saved_as' (local filename)
    """
    manifest_path = Path(wiki_dir) / "manifest.json"
    
    if not manifest_path.exists():
        return []
    
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    
    rule_files = []
    for file_info in manifest.get("files", []):
        if file_info.get("has_rules", False):
            rule_files.append({
                "path": file_info["path"],
                "saved_as": file_info["saved_as"],
            })
    
    return rule_files


def _add_line_numbers(text: str) -> str:
    """Add line numbers to text for LLM input. Format: '    1|first line'"""
    lines = text.split("\n")
    return "\n".join(f"{i + 1:>5}|{line}" for i, line in enumerate(lines))


def _merge_chunks(chunks: List[tuple], gap_threshold: int = 3) -> List[tuple]:
    """Sort and merge overlapping/adjacent line ranges."""
    if not chunks:
        return []
    
    sorted_chunks = sorted(chunks, key=lambda x: x[0])
    merged = [sorted_chunks[0]]
    
    for current in sorted_chunks[1:]:
        last = merged[-1]
        if current[0] <= last[1] + gap_threshold + 1:
            merged[-1] = (last[0], max(last[1], current[1]))
        else:
            merged.append(current)
    
    return merged


def _extract_chunks(text: str, chunks: List[tuple]) -> str:
    """Extract specified line ranges from text with [...] separators."""
    if not chunks:
        return ""
    
    lines = text.split("\n")
    extracted_parts = []
    
    for start, end in chunks:
        start_idx = max(0, start - 1)
        end_idx = min(len(lines), end)
        extracted_parts.append("\n".join(lines[start_idx:end_idx]))
    
    return "\n\n[...]\n\n".join(extracted_parts)


def _format_rule_block(wiki_path: str, content: str) -> str:
    """Format extracted rules as a wiki block."""
    if not content.strip():
        return ""
    return f"<wiki:{wiki_path}>\n{content}\n</wiki:{wiki_path}>"

@observe()
def run_context_builder(
    task_text: str,
    collected: CollectedContext,
    task_ctx: TaskContext = None,
) -> List[str]:
    """
    Run context builder to select relevant blocks for a task.
    
    Args:
        task_text: The user's task text
        collected: CollectedContext from collect_context_blocks()
        task_ctx: TaskContext for logging LLM usage
    
    Returns:
        List of selected block names (empty for public users)
    """
    # Skip LLM call for public users - no blocks to choose from
    if not collected.blocks:
        return []
    
    # Build user message with all context
    parts = ["<session_content>", collected.session_content, "</session_content>"]
    
    if collected.employee_content:
        parts.append("\n<employee_profile>")
        parts.append(collected.employee_content)
        parts.append("</employee_profile>")
    
    parts.append("\n<available_content_blocks>")
    for block in collected.blocks.values():
        parts.append(block.content)
    parts.append("</available_content_blocks>")
    
    # Add recap of all block IDs for easy reference
    parts.append("\n<block_ids_to_choose_from>")
    parts.append("\n".join(collected.blocks.keys()))
    parts.append("</block_ids_to_choose_from>")
    
    parts.append("\n<task>")
    parts.append(task_text)
    parts.append("</task>")
    
    user_message = "\n".join(parts)
    
    # Call LLM
    try:
        llm_result = call_llm(
            schema=ContextSelection,
            system_prompt=system_prompt_context_builder,
            conversation=[{"role": "user", "content": user_message}],
            task_ctx=task_ctx,
        )
        
        parsed = llm_result["parsed"]
        
        # Filter to only valid block names
        valid_blocks = [b for b in parsed.selected_blocks if b in collected.blocks]
        
        return valid_blocks
        
    except Exception as e:
        # On error, return all blocks (fail-safe)
        print(f"⚠ Context builder error: {e}, returning all blocks")
        return list(collected.blocks.keys())


# ============================================================================
# RULE BUILDER
# ============================================================================

@observe()
def _process_single_rule_file(
    file_info: dict,
    wiki_dir: str,
    task_text: str,
    session_content: str,
    employee_content: str | None,
    task_ctx: TaskContext = None,
    **_lf: Any,  # Langfuse kwargs (trace_id, parent_observation_id)
) -> str:
    """
    Process a single rule file to extract relevant chunks.
    
    Args:
        file_info: Dict with 'path' (database) and 'saved_as' (local filename)
        wiki_dir: Path to wiki directory
        task_text: User's task
        session_content: Formatted session context
        employee_content: Formatted employee context (or None)
        task_ctx: TaskContext for logging LLM usage
        **_lf: Langfuse trace propagation kwargs
    
    Returns:
        Formatted wiki block with extracted rules, or empty string
    """
    wiki_path = file_info["path"]
    local_filename = file_info["saved_as"]
    file_path = Path(wiki_dir) / local_filename
    
    # Read file content
    try:
        raw_content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"⚠ Rule builder: failed to read {local_filename}: {e}")
        return ""
    
    # Add line numbers for LLM
    numbered_content = _add_line_numbers(raw_content)
    
    # Build user message
    parts = ["<user_context>", session_content]
    if employee_content:
        parts.append(employee_content)
    parts.append("</user_context>")
    
    parts.append(f"\n<document file=\"{wiki_path}\">")
    parts.append(numbered_content)
    parts.append("</document>")
    
    parts.append("\n<task>")
    parts.append(task_text)
    parts.append("</task>")
    
    user_message = "\n".join(parts)
    
    # Call LLM
    try:
        llm_result = call_llm(
            schema=RuleSelection,
            system_prompt=system_prompt_rule_builder,
            conversation=[{"role": "user", "content": user_message}],
            task_ctx=task_ctx,
        )
        
        parsed = llm_result["parsed"]
        
        # Extract and format chunks
        if not parsed.chunks:
            return ""
        
        # Convert to tuples and merge
        chunk_tuples = [(c.start_line, c.end_line) for c in parsed.chunks]
        merged = _merge_chunks(chunk_tuples)
        
        # Extract from raw content (no line numbers)
        extracted = _extract_chunks(raw_content, merged)
        
        return _format_rule_block(wiki_path, extracted)
        
    except Exception as e:
        # Fallback: return entire file content
        print(f"⚠ Rule builder error for {wiki_path}: {e}, using full file as fallback")
        return _format_rule_block(wiki_path, raw_content)

@observe()
def _run_rule_builder_parallel(
    rule_files: List[dict],
    wiki_dir: str,
    task_text: str,
    session_content: str,
    employee_content: str | None,
    task_ctx: TaskContext = None,
) -> List[str]:
    """
    Process multiple rule files in parallel.
    
    Args:
        rule_files: List of file info dicts from get_rule_files()
        wiki_dir: Path to wiki directory
        task_text: User's task
        session_content: Formatted session context
        employee_content: Formatted employee context (or None)
        task_ctx: TaskContext for logging LLM usage
    
    Returns:
        List of formatted wiki blocks (may include empty strings)
    """
    # Get Langfuse trace context for propagation
    lf = get_client()
    trace_id = lf.get_current_trace_id()
    parent_obs_id = lf.get_current_observation_id()
    
    with ThreadPoolExecutor(max_workers=len(rule_files)) as executor:
        futures = [
            executor.submit(
                _process_single_rule_file,
                file_info,
                wiki_dir,
                task_text,
                session_content,
                employee_content,
                task_ctx,
                langfuse_trace_id=trace_id,
                langfuse_parent_observation_id=parent_obs_id,
            )
            for file_info in rule_files
        ]
        return [f.result() for f in futures]


@observe()
def run_rule_builder(
    task_text: str,
    session_content: str,
    employee_content: str | None,
    wiki_dir: str,
    task_ctx: TaskContext = None,
) -> str:
    """
    Extract relevant rules from all wiki files marked as containing rules.
    
    Args:
        task_text: User's task
        session_content: Formatted session context (from format_whoami)
        employee_content: Formatted employee context (from format_employee), or None
        wiki_dir: Path to wiki directory containing manifest.json
        task_ctx: TaskContext for logging LLM usage
    
    Returns:
        Concatenated wiki blocks with relevant rules, or empty string
    """
    # Get list of files with rules
    rule_files = _get_rule_files(wiki_dir)
    
    if not rule_files:
        return ""
    
    # Process files in parallel
    blocks = _run_rule_builder_parallel(
        rule_files,
        wiki_dir,
        task_text,
        session_content,
        employee_content,
        task_ctx,
    )
    
    # Filter out empty blocks and concatenate
    non_empty = [b for b in blocks if b.strip()]
    
    return "\n\n".join(non_empty)


# ============================================================================
# STEP VALIDATOR (PRE-EXECUTION SAFETY)
# ============================================================================

@observe()
def run_erc3_step_validator(
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
    """Run ERC3 StepValidator before executing a tool."""
    node_id = next_node_id(parent_node_id, sibling_count)
    validator_name = validator_config["name"]
    system_prompt = validator_config["system_prompt"]
    
    conversation_summary = []
    for msg in conversation:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        conversation_summary.append(f"[{role}]: {content}")
    
    user_message = f"""Original task:
{original_task}

Agent system prompt:
{agent_system_prompt}

Conversation history:
{"\n".join(conversation_summary)}

Proposed step:
- Current state: {agent_output.get('current_state', 'N/A')}
- Rule check: {agent_output.get('rule_check', 'N/A')}
- Remaining work: {agent_output.get('remaining_work', [])}
- Next action: {agent_output.get('next_action', 'N/A')}
- Call: {agent_output.get('call', {})}

Is this plan safe and policy compliant?"""
    
    llm_start = time.time()
    
    try:
        llm_result = call_llm(
            schema=ERC3StepValidatorResponse,
            system_prompt=system_prompt,
            conversation=[{"role": "user", "content": user_message}],
            task_ctx=task_ctx,
        )
        
        parsed = llm_result["parsed"]
        reasoning = llm_result["reasoning"]
        llm_duration = llm_result["timing"]
        
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
            verdict = "✓" if parsed.is_valid else "⚠"
            print(f"    {verdict} {validator_name} ({llm_duration:.2f}s)")
        
        return {
            "is_valid": parsed.is_valid,
            "rejection_message": parsed.rejection_message,
            "analysis": parsed.analysis,
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
            print(f"    ⚠ {validator_name} error: {exc}")
        
        return {
            "is_valid": True,
            "rejection_message": "",
            "analysis": f"Validation error: {exc}",
        }


def validate_and_retry_erc3_step(
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
    Validate a proposed step and retry with feedback if rejected.
    """
    agent_name = agent_config["name"]
    job = llm_result["parsed"]
    
    function_to_execute = getattr(job.call, "function", None)
    if function_to_execute is None:
        node_id = next_node_id(parent_node_id, step_count)
        return {
            "llm_result": llm_result,
            "step_count": step_count + 1,
            "node_id": node_id,
        }
    
    validator_config = VALIDATOR_REGISTRY.get("step_validator")
    if not validator_config:
        node_id = next_node_id(parent_node_id, step_count)
        return {
            "llm_result": llm_result,
            "step_count": step_count + 1,
            "node_id": node_id,
        }
    
    triggers = validator_config["triggers_on_tools"]
    tool_matches = triggers == "*" or isinstance(function_to_execute, triggers)
    applies_to = validator_config["applies_to_agents"]
    agent_matches = applies_to == "*" or agent_name in applies_to
    if not (tool_matches and agent_matches):
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
        node_id = next_node_id(parent_node_id, current_step_count)
        
        validation = run_erc3_step_validator(
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
# ERC3 ORCHESTRATOR LOOP
# ============================================================================

@observe()
def run_erc3_agent_loop(
    agent_config: dict,
    initial_context: str,
    benchmark_client,
    trace: List[dict],
    parent_node_id: str = "0",
    task_ctx: TaskContext = None,
) -> dict:
    """
    Run the ERC3 orchestrator agent until completion or failure.
    """
    agent_name = agent_config["name"]
    system_prompt = agent_config["system_prompt"]
    schema = agent_config["schema"]
    max_steps = agent_config["max_steps"]
    
    conversation = [
        {"role": "system", "content": system_prompt},
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
        
        validation = validate_and_retry_erc3_step(
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
        function_to_execute = getattr(job.call, "function", None)
        
        if function_to_execute is None:
            raise ValueError("ERC3 orchestrator produced a step without a function to execute.")
        
        sdk_result = execute_erc3_tools(job, benchmark_client)
        
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
        
        if job.call.call_mode == "single":
            func_obj = sdk_result["function"]
            assistant_content = f'Step completed.\nAction: {job.next_action}\nTool called: {func_obj.model_dump_json()}\nResponse received: {sdk_result["text"]}'
        else:
            assistant_content = f'Step completed.\nAction\n"{job.next_action}"\n\n{sdk_result["text"]}'
        
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

