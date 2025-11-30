"""
Agent types and registry module.

Contains:
- AGENT_REGISTRY: Unified registry for all agent types (Orchestrator, ProductExplorer, etc.)
- VALIDATOR_REGISTRY: Validators triggered by tools (not anchored to agents)
- META_TOOLS tuple (for dispatch routing)
- Helper functions for agent/validator lookup

Import hierarchy: This module imports from subagent_prompts.py
"""

from subagent_prompts import (
    # Orchestrator
    system_prompt_orchestrator, NextStepOrchestrator,
    ProductExplorer, BasketBuilder, CheckoutProcessor,
    # Sub-agents (using consistent naming)
    system_prompt_basket_builder, NextStepBasketBuilder,
    system_prompt_checkout_processor, NextStepCheckoutProcessor,
    # Terminal action
    SubmitTask,
    # Validators
    system_prompt_step_validator, step_validator_schema,
)


# ============================================================================
# META-TOOLS DEFINITION
# ============================================================================
# These are orchestrator tools that spawn sub-agents instead of calling SDK.
# Used by execute_tool_dispatch() for routing decisions.

META_TOOLS = (ProductExplorer, BasketBuilder, CheckoutProcessor)


# ============================================================================
# TERMINAL ACTION
# ============================================================================
# Marks the end of an agent's execution.

TERMINAL_ACTIONS = (SubmitTask,)


# ============================================================================
# VALIDATOR REGISTRY
# ============================================================================
# Validators are triggered by specific tools, not anchored to agents.
# 
# Each validator config contains:
# - name: Display name (used in traces and logging)
# - system_prompt: System prompt for the validator LLM call
# - schema: Pydantic schema for structured LLM output
# - triggers_on_tools: Tuple of tool classes that trigger this validator, or "*" for all
# - applies_to_agents: Tuple of agent names, or "*" for all agents
# - max_attempts: How many validation failures before forcing termination

VALIDATOR_REGISTRY = {
    "step_validator": {
        "name": "StepValidator",
        "system_prompt": system_prompt_step_validator,
        "schema": step_validator_schema,
        "triggers_on_tools": "*",  # all tools including terminals
        "applies_to_agents": ("Orchestrator",),
        "max_attempts": 2,
    },
}


# ============================================================================
# AGENT REGISTRY
# ============================================================================
# Unified registry for all agent types.
# 
# Each agent config contains:
# - name: Display name (used in traces and logging)
# - system_prompt: Base system prompt (will be appended with "first step")
# - schema: Pydantic model for structured LLM output
# - max_steps: Maximum iterations before timeout
# - tool_type: "meta" for orchestrator (spawns subagents), "sdk" for subagents (calls SDK)
#
# Note: Validators are now in VALIDATOR_REGISTRY, triggered by tool types not agents.

AGENT_REGISTRY = {
    # Orchestrator - coordinates sub-agents
    "Orchestrator": {
        "name": "Orchestrator",
        "system_prompt": system_prompt_orchestrator,
        "schema": NextStepOrchestrator,
        "max_steps": 30,
        "tool_type": "meta",
    },
    
    # BasketBuilder - configure basket contents and apply coupons
    "BasketBuilder": {
        "name": "BasketBuilder",
        "system_prompt": system_prompt_basket_builder,
        "schema": NextStepBasketBuilder,
        "max_steps": 30,
        "tool_type": "sdk",
    },
    
    # CheckoutProcessor - finalize purchases
    "CheckoutProcessor": {
        "name": "CheckoutProcessor",
        "system_prompt": system_prompt_checkout_processor,
        "schema": NextStepCheckoutProcessor,
        "max_steps": 30,
        "tool_type": "sdk",
    },
}


# ============================================================================
# SUBAGENT TYPE MAPPING
# ============================================================================
# Maps orchestrator meta-tool classes to agent registry keys.
# Used when orchestrator delegates to a sub-agent.
# Note: ProductExplorer handled specially in execute_meta_tool, not in registry.

SUBAGENT_TYPE_MAP = {
    BasketBuilder: "BasketBuilder",
    CheckoutProcessor: "CheckoutProcessor",
}


def get_subagent_config(meta_tool_instance) -> dict:
    """
    Get agent configuration for a meta-tool instance.
    
    Args:
        meta_tool_instance: Instance of ProductExplorer, BasketBuilder, etc.
    
    Returns:
        Agent config dict from AGENT_REGISTRY
    
    Raises:
        ValueError: If meta_tool_instance type is not recognized
    """
    for tool_class, agent_key in SUBAGENT_TYPE_MAP.items():
        if isinstance(meta_tool_instance, tool_class):
            return AGENT_REGISTRY[agent_key]
    
    raise ValueError(f"Unknown meta-tool type: {type(meta_tool_instance)}")


def is_meta_tool(function) -> bool:
    """Check if a function is a meta-tool (spawns subagent) vs SDK tool."""
    return isinstance(function, META_TOOLS)


def is_terminal_action(function) -> bool:
    """Check if a function is a terminal action (SubmitTask)."""
    return isinstance(function, TERMINAL_ACTIONS)


# ============================================================================
# VALIDATOR HELPER FUNCTIONS
# ============================================================================

def get_validators_for_tool(tool, agent_name: str) -> list:
    """
    Get list of validators that should trigger for a given tool and agent.
    
    Args:
        tool: Tool instance (e.g., SubmitTask, ProductExplorer)
        agent_name: Name of the agent calling the tool
    
    Returns:
        List of validator config dicts that should trigger
    """
    matching_validators = []
    
    for validator_key, validator_config in VALIDATOR_REGISTRY.items():
        # Check if tool matches triggers_on_tools
        triggers = validator_config["triggers_on_tools"]
        tool_matches = triggers == "*" or isinstance(tool, triggers)
        
        # Check if agent matches applies_to_agents
        applies_to = validator_config["applies_to_agents"]
        agent_matches = applies_to == "*" or agent_name in applies_to
        
        if tool_matches and agent_matches:
            matching_validators.append(validator_config)
    
    return matching_validators

