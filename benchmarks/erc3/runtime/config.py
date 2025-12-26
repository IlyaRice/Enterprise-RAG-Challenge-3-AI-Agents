"""
ERC3 benchmark agent configuration.

Defines:
- AGENT_REGISTRY: Agent configuration
- VALIDATOR_REGISTRY: Step-level validators
- TERMINAL_ACTIONS: Terminal SDK calls (currently /respond only)
- Helper utilities for agent/tool lookup
"""

from erc3.erc3.dtos import (
    Req_ProvideAgentResponse,
    Req_GetCustomer, Req_GetEmployee, Req_GetProject, Req_GetTimeEntry,
    Req_LoadWiki, Req_SearchWiki, Req_UpdateEmployeeInfo, Req_UpdateProjectStatus,
    Req_UpdateProjectTeam, Req_UpdateTimeEntry, Req_UpdateWiki,
    Req_TimeSummaryByEmployee, Req_TimeSummaryByProject,
)

from .prompts import (
    AgentStep,
    StepValidatorResponse,
    prompt_agent,
    prompt_step_validator,
    Req_ListEmployees, Req_SearchEmployees, Req_ListCustomers, Req_SearchCustomers,
    Req_ListProjects, Req_SearchProjects, Req_SearchTimeEntries, Req_LogTimeEntry,
    Req_LoadRespondInstructions,
)

# Terminal action (SDK /respond endpoint)
TERMINAL_ACTIONS = (Req_ProvideAgentResponse,)

# Primary agent configuration
AGENT_REGISTRY = {
    "Agent": {
        "name": "Agent",
        "system_prompt": prompt_agent,
        "schema": AgentStep,
        "max_steps": 40,
        "tool_type": "sdk",
    },
}

# Non-respond tools (all tools except Req_ProvideAgentResponse)
NON_RESPOND_TOOLS = (
    Req_ListEmployees, Req_SearchEmployees, Req_GetEmployee, Req_UpdateEmployeeInfo,
    Req_ListCustomers, Req_SearchCustomers, Req_GetCustomer,
    Req_ListProjects, Req_SearchProjects, Req_GetProject, Req_UpdateProjectTeam, Req_UpdateProjectStatus,
    Req_LoadWiki, Req_SearchWiki, Req_UpdateWiki,
    Req_LogTimeEntry, Req_UpdateTimeEntry, Req_GetTimeEntry, Req_SearchTimeEntries,
    Req_TimeSummaryByProject, Req_TimeSummaryByEmployee, Req_ProvideAgentResponse,
)

# Step validator registry (pre-execution planning guardrail)
VALIDATOR_REGISTRY = {
    "step_validator": {
        "name": "StepValidator",
        "system_prompt": prompt_step_validator,
        "schema": StepValidatorResponse,
        "triggers_on_tools": NON_RESPOND_TOOLS,
        "applies_to_agents": ("Agent",),
        "max_attempts": 2,
    },
}


def is_terminal_action(function) -> bool:
    """Return True if the function is a terminal /respond call."""
    return isinstance(function, TERMINAL_ACTIONS)

