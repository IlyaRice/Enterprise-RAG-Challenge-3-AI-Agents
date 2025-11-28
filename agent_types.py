"""
Agent types and registry module.

Contains:
- AGENT_REGISTRY (replaces SUBAGENT_REGISTRY, unified for all agent types)
- Agent configs (Orchestrator, ProductExplorer, BasketBuilder, CouponOptimizer, CheckoutProcessor)
- META_TOOLS tuple (for dispatch routing)

Note: TaskAnalyzer and BullshitCaller are "leaf agents" - not in registry.
They are single LLM call agents that auto-terminate and don't go through the unified loop.

Import hierarchy: This module imports from infrastructure.py and subagent_prompts.py
"""

from subagent_prompts import (
    # Orchestrator
    system_prompt_orchestrator, NextStepOrchestrator,
    ProductExplorer, CouponOptimizer, BasketBuilder, CheckoutProcessor,
    # Sub-agents (using consistent naming)
    system_prompt_product_explorer, NextStepProductExplorer,
    system_prompt_coupon_optimizer, NextStepCouponOptimizer,
    system_prompt_basket_builder, NextStepBasketBuilder,
    system_prompt_checkout_processor, NextStepCheckoutProcessor,
    # Terminal actions
    CompleteTask, RefuseTask,
)


# ============================================================================
# META-TOOLS DEFINITION
# ============================================================================
# These are orchestrator tools that spawn sub-agents instead of calling SDK.
# Used by execute_tool_dispatch() for routing decisions.

META_TOOLS = (ProductExplorer, CouponOptimizer, BasketBuilder, CheckoutProcessor)


# ============================================================================
# TERMINAL ACTIONS
# ============================================================================
# These mark the end of an agent's execution.

TERMINAL_ACTIONS = (CompleteTask, RefuseTask)


# ============================================================================
# AGENT REGISTRY
# ============================================================================
# Unified registry for all agent types. Replaces the old SUBAGENT_REGISTRY.
# 
# Each agent config contains:
# - name: Display name (used in traces and logging)
# - system_prompt: Base system prompt (will be appended with "first step")
# - schema: Pydantic model for structured LLM output
# - max_steps: Maximum iterations before timeout
# - validator: Name of validator function ("bullshit_caller") or None
# - max_validations: How many validation failures before forcing termination
# - tool_type: "meta" for orchestrator (spawns subagents), "sdk" for subagents (calls SDK)

AGENT_REGISTRY = {
    # Orchestrator - coordinates sub-agents
    "Orchestrator": {
        "name": "Orchestrator",
        "system_prompt": system_prompt_orchestrator,
        "schema": NextStepOrchestrator,
        "max_steps": 30,
        "validator": "bullshit_caller",
        "max_validations": 3,
        "tool_type": "meta",
    },
    
    # ProductExplorer - search and analyze products (read-only)
    "ProductExplorer": {
        "name": "ProductExplorer",
        "system_prompt": system_prompt_product_explorer,
        "schema": NextStepProductExplorer,
        "max_steps": 30,
        "validator": "bullshit_caller",
        "max_validations": 2,
        "tool_type": "sdk",
    },
    
    # CouponOptimizer - test and apply discount codes
    "CouponOptimizer": {
        "name": "CouponOptimizer",
        "system_prompt": system_prompt_coupon_optimizer,
        "schema": NextStepCouponOptimizer,
        "max_steps": 30,
        "validator": "bullshit_caller",
        "max_validations": 2,
        "tool_type": "sdk",
    },
    
    # BasketBuilder - add/remove products from basket
    "BasketBuilder": {
        "name": "BasketBuilder",
        "system_prompt": system_prompt_basket_builder,
        "schema": NextStepBasketBuilder,
        "max_steps": 30,
        "validator": "bullshit_caller",
        "max_validations": 2,
        "tool_type": "sdk",
    },
    
    # CheckoutProcessor - finalize purchases
    "CheckoutProcessor": {
        "name": "CheckoutProcessor",
        "system_prompt": system_prompt_checkout_processor,
        "schema": NextStepCheckoutProcessor,
        "max_steps": 30,
        "validator": "bullshit_caller",
        "max_validations": 2,
        "tool_type": "sdk",
    },
}


# ============================================================================
# SUBAGENT TYPE MAPPING
# ============================================================================
# Maps orchestrator meta-tool classes to agent registry keys.
# Used when orchestrator delegates to a sub-agent.

SUBAGENT_TYPE_MAP = {
    ProductExplorer: "ProductExplorer",
    CouponOptimizer: "CouponOptimizer",
    BasketBuilder: "BasketBuilder",
    CheckoutProcessor: "CheckoutProcessor",
}


def get_subagent_config(meta_tool_instance) -> dict:
    """
    Get agent configuration for a meta-tool instance.
    
    Args:
        meta_tool_instance: Instance of ProductExplorer, CouponOptimizer, etc.
    
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
    """Check if a function is a terminal action (CompleteTask/RefuseTask)."""
    return isinstance(function, TERMINAL_ACTIONS)

