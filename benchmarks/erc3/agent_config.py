"""
ERC3 benchmark agent configuration.

Defines:
- AGENT_REGISTRY: Orchestrator configuration
- VALIDATOR_REGISTRY: Step-level validators
- TERMINAL_ACTIONS: Terminal SDK calls (currently /respond only)
- Helper utilities for agent/tool lookup
"""

from erc3.erc3.dtos import Req_ProvideAgentResponse

from .prompts import (
    NextStepERC3Orchestrator,
    ERC3StepValidatorResponse,
    system_prompt_erc3_orchestrator,
    system_prompt_erc3_step_validator,
)

# No meta-tools for ERC3 (single-agent architecture)
META_TOOLS = ()

# Terminal action (SDK /respond endpoint)
TERMINAL_ACTIONS = (Req_ProvideAgentResponse,)

# Primary orchestrator configuration
AGENT_REGISTRY = {
    "ERC3Orchestrator": {
        "name": "ERC3Orchestrator",
        "system_prompt": system_prompt_erc3_orchestrator,
        "schema": NextStepERC3Orchestrator,
        "max_steps": 20,
        "tool_type": "sdk",
    },
}

# Step validator registry (pre-execution planning guardrail)
VALIDATOR_REGISTRY = {
    "step_validator": {
        "name": "ERC3StepValidator",
        "system_prompt": system_prompt_erc3_step_validator,
        "schema": ERC3StepValidatorResponse,
        "triggers_on_tools": "*",
        "applies_to_agents": ("ERC3Orchestrator",),
        "max_attempts": 1,
    },
}


def is_terminal_action(function) -> bool:
    """Return True if the function is a terminal /respond call."""
    return isinstance(function, TERMINAL_ACTIONS)