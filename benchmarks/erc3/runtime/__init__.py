"""
ERC3 runtime module.

Per-task execution: agent loop, context gathering, SDK tools, rule loading.

Usage:
    from benchmarks.erc3.runtime import run_agent_loop, collect_context_blocks, load_rules_for_session
"""

from .loop import run_agent_loop
from .config import AGENT_REGISTRY, is_terminal_action
from .context import (
    collect_context_blocks,
    build_agent_context,
    whoami_raw,
    load_rules_for_session,
    load_respond_rules_for_session,
    run_context_builder,
)
from .tools import execute_erc3_tools

__all__ = [
    "run_agent_loop",
    "AGENT_REGISTRY",
    "is_terminal_action",
    "collect_context_blocks",
    "build_agent_context",
    "whoami_raw",
    "load_rules_for_session",
    "load_respond_rules_for_session",
    "run_context_builder",
    "execute_erc3_tools",
]

