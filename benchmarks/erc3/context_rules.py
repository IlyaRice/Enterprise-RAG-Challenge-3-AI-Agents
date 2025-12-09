"""
Context and rule selection utilities for ERC3.

Contains:
- run_context_builder: selects relevant context blocks for a task
- run_rule_builder: extracts rule chunks from wiki files
"""

import json
from pathlib import Path
from typing import Any, List
from concurrent.futures import ThreadPoolExecutor

from langfuse import observe, get_client

from infrastructure import call_llm
from .tools import CollectedContext
from .prompts import (
    AccessEvaluation,
    ContextSelection,
    RuleSelection,
    system_prompt_access_evaluator,
    system_prompt_context_builder,
    system_prompt_rule_builder,
)
from .rules import load_access_control_rules
from infrastructure import TaskContext


# ============================================================================
# RULE BUILDER HELPERS
# ============================================================================

def _get_rule_files(wiki_dir: str) -> List[dict]:
    """
    Get list of wiki files that contain rules.
    
    Returns:
        List of dicts with 'path' (database format) and 'saved_as' (local filename)
    """
    wiki_meta_path = Path(wiki_dir) / "wiki_meta.json"
    
    if not wiki_meta_path.exists():
        return []
    
    wiki_meta = json.loads(wiki_meta_path.read_text(encoding="utf-8"))
    
    rule_files = []
    for file_info in wiki_meta.get("files", []):
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
    return f"<kind=wiki id={wiki_path}>\n{content}\n</kind=wiki id={wiki_path}>"


@observe()
def run_context_builder(
    task_text: str,
    collected: CollectedContext,
    task_ctx: TaskContext = None,
    **_lf: Any,  # Langfuse kwargs for thread context propagation
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
        print(f"✗ Context builder error: {e}, returning all blocks")
        return list(collected.blocks.keys())


# ============================================================================
# ACCESS EVALUATOR
# ============================================================================

@observe()
def run_access_evaluator(
    task_text: str,
    collected: CollectedContext,
    whoami: dict,
    task_ctx: TaskContext = None,
    **_lf: Any,  # Langfuse kwargs for thread context propagation
) -> str:
    """
    Run preliminary access evaluation for a task.
    
    Analyzes whether the user can perform the requested actions based on
    their identity and company access control rules.
    """
    # Load access control rules
    access_rules = load_access_control_rules(whoami)
    if not access_rules:
        return ""
    
    # Build user message with session, employee, rules, task
    parts = ["<session_context>", collected.session_content, "</session_context>"]
    
    if collected.employee_content:
        parts.append("\n<employee_profile>")
        parts.append(collected.employee_content)
        parts.append("</employee_profile>")
    else:
        parts.append("\n<employee_profile>")
        parts.append("(No employee profile - public/anonymous user)")
        parts.append("</employee_profile>")
    
    parts.append("\n<access_control_rules>")
    parts.append(access_rules)
    parts.append("</access_control_rules>")
    
    parts.append("\n<task>")
    parts.append(task_text)
    parts.append("</task>")
    
    user_message = "\n".join(parts)
    
    # Call LLM
    try:
        llm_result = call_llm(
            schema=AccessEvaluation,
            system_prompt=system_prompt_access_evaluator,
            conversation=[{"role": "user", "content": user_message}],
            task_ctx=task_ctx,
        )
        
        parsed = llm_result["parsed"]
        
        # Format output as access_guidance block
        output_parts = [
            "<access_guidance>",
            "Note: Preliminary analysis - discover conditional factors during execution.",
            "",
            parsed.reasoning,
            "",
            f"Determination: {parsed.determination}",
        ]
        
        if parsed.conditional_factor:
            output_parts.append(f"Conditional: {parsed.conditional_factor}")
        
        output_parts.append("</access_guidance>")
        
        return "\n".join(output_parts)
        
    except Exception as e:
        print(f"✗ Access evaluator error: {e}, skipping access hints")
        return ""


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
        print(f"✗ Rule builder: failed to read {local_filename}: {e}")
        return ""
    
    # Add line numbers for LLM
    numbered_content = _add_line_numbers(raw_content)
    
    # Build user message
    parts = ["<user_context>", session_content]
    if employee_content:
        parts.append(employee_content)
    parts.append("</user_context>")
    
    parts.append(f'\n<document file="{wiki_path}">')
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
        print(f"✗ Rule builder error for {wiki_path}: {e}, using full file as fallback")
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
        wiki_dir: Path to wiki directory containing wiki_meta.json
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
