"""
Context and rule selection utilities for ERC3.

Contains:
- run_context_builder: selects relevant context blocks for a task
"""

from typing import Any, List

from langfuse import observe

from infrastructure import call_llm
from .tools import CollectedContext
from .prompts import (
    ContextSelection,
    system_prompt_context_builder,
)
from infrastructure import TaskContext


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
