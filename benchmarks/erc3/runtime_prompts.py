"""
ERC3 runtime prompts and schemas.

Used during task execution

Contains:
- SDK wrappers: Req_* classes for autopagination and schema fixes
- Context builder: ContextSelection schema, system_prompt_context_builder
- Orchestrator: NextStepERC3Orchestrator schema, system_prompt_erc3_orchestrator
- Step validator: ERC3StepValidatorResponse schema, system_prompt_erc3_step_validator
"""

from typing import List, Literal, Union

from pydantic import BaseModel, Field

from erc3.erc3.dtos import (
    BillableFilter,
    CompanyID,
    DealPhase,
    EmployeeID,
    ProjectID,
    ProjectTeamFilter,
    Req_GetCustomer,
    Req_GetEmployee,
    Req_GetProject,
    Req_GetTimeEntry,
    Req_LoadWiki,
    Req_ProvideAgentResponse,
    Req_SearchWiki,
    Req_TimeSummaryByEmployee,
    Req_TimeSummaryByProject,
    Req_UpdateEmployeeInfo,
    Req_UpdateProjectStatus,
    Req_UpdateProjectTeam,
    Req_UpdateTimeEntry,
    Req_UpdateWiki,
    SkillFilter,
    TimeEntryStatus,
)


# ============================================================================
# ERC3 ORCHESTRATOR - PROMPTS & SCHEMAS
# ============================================================================

system_prompt_erc3_orchestrator = """
<role>
You are the enterprise AI assistant for {company_name}. Every action must comply with the rules included in the conversation.

Company locations: {company_locations}
Company executives: {company_execs}
</role>

<operating_principles>
1. IDENTIFY the requester (session context) and confirm whether they are public or authenticated.
2. CLASSIFY the task: data lookup, update, time logging, wiki edit, clarification, or refusal.
3. CHECK CAPABILITIES: If the task explicitly references a system, feature, or tool not listed in your toolbox, respond with outcome="none_unsupported" - do not ask for clarification about how to use something that doesn't exist.
4. EXECUTE the next logical SDK call. Fetch data before mutating anything.
5. LOAD RESPOND INSTRUCTIONS: Before calling /respond, call /load-respond-instructions ONCE.
6. RESPOND via /respond when the task is complete or impossible.
</operating_principles>

<respond_instructions_requirement>
CRITICAL: Before calling /respond, you MUST call /load-respond-instructions to load response formatting rules.
- Call it EXACTLY ONCE per session, when ready to formulate your final response
- Do NOT call it more than once - rules don't change during a session
- Do NOT call /respond without loading instructions first
</respond_instructions_requirement>

<toolbox>
- Response: /load-respond-instructions (MUST call once before /respond)
- Employees: /employees/list, /employees/search, /employees/get, /employees/update
- Customers: /customers/list, /customers/search, /customers/get
- Projects: /projects/list, /projects/search, /projects/get, /projects/team/update, /projects/status/update
- Wiki: /wiki/load, /wiki/search, /wiki/update (create/update/delete)
- Time: /time/log, /time/update, /time/get, /time/search, /time/summary/project, /time/summary/employee
- Completion: /respond (final answer with outcome + links) - requires /load-respond-instructions first

You may call any endpoint at most once per step. Chain multiple steps if needed.
</toolbox>

<search_strategies>
- Use /list to find an employee/customer/project by name only (no other filters). Use /search when you need to apply specific filters (e.g., location, status, department).
- If a search tool returns no results, try easing the filters (remove or broaden criteria) before concluding data doesn't exist.
- If unsure what to do or what rule applies to a situation, search the wiki using keywords from the task - it may contain relevant guidance or policies.
</search_strategies>

<update_operations>
CRITICAL: The /employees/update endpoint requires ALL fields to be provided. Omitted fields will be cleared/overwritten with empty values.
Before calling /employees/update:
1. First fetch the current employee data (via /employees/get)
2. In the update call, include ALL existing field values
3. Only modify the specific fields you intend to change
</update_operations>

<outcomes>
- ok_answer: Task completed successfully with evidence.
- ok_not_found: Valid request but data does not exist.
- denied_security: Blocked by rules or insufficient privileges.
- none_clarification_needed: Ambiguous instructions for an OTHERWISE VALID operation; ask for clarification.
- none_unsupported: Feature, system, or capability explicitly not in your toolbox.
- error_internal: System failure (after retries) or exceeded limits.
</outcomes>
<grounding>
When calling /respond, attach AgentLink entries for every entity cited (possible kinds: employee, customer, project, wiki, location). Include ALL entities in the chain that led to your answer.
Entities mentioned in the original task should typically be linked if they appear in respond, unless rules say otherwise.
Note: Follow any additional specific linking rules and restrictions in the <rules>.
</grounding>

<planning_requirements>
- Maintain an up-to-date `remaining_work` plan (<=5 bullet items).
</planning_requirements>
"""

# --- Wrapper Classes for Schema Fixes ---

class Req_LogTimeEntry(BaseModel):
    """Log a time entry. Tool field ordered first for proper schema discrimination."""
    tool: Literal["/time/log"] = "/time/log"
    employee: EmployeeID
    customer: CompanyID | None = None
    project: ProjectID | None = None
    date: str
    hours: float
    work_category: str
    notes: str
    billable: bool
    status: TimeEntryStatus
    logged_by: EmployeeID


# --- Autopaginated Wrappers ---

class Req_ListEmployees(BaseModel):
    """List all employees (autopaginated)."""
    tool: Literal["/employees/list"] = "/employees/list"


class Req_SearchEmployees(BaseModel):
    """Search employees with filters (autopaginated)."""
    tool: Literal["/employees/search"] = "/employees/search"
    query: str | None = None
    location: str | None = None
    department: str | None = None
    manager: str | None = None
    skills: List[SkillFilter] = Field(default_factory=list)
    wills: List[SkillFilter] = Field(default_factory=list)


class Req_ListCustomers(BaseModel):
    """List all customers (autopaginated)."""
    tool: Literal["/customers/list"] = "/customers/list"


class Req_SearchCustomers(BaseModel):
    """Search customers with filters (autopaginated)."""
    tool: Literal["/customers/search"] = "/customers/search"
    query: str | None = None
    deal_phase: List[DealPhase] = Field(default_factory=list)
    account_managers: List[EmployeeID] = Field(default_factory=list)
    locations: List[str] = Field(default_factory=list)


class Req_ListProjects(BaseModel):
    """List all projects (autopaginated)."""
    tool: Literal["/projects/list"] = "/projects/list"


class Req_SearchProjects(BaseModel):
    """Search projects with filters (autopaginated)."""
    tool: Literal["/projects/search"] = "/projects/search"
    query: str | None = None
    customer_id: CompanyID | None = None
    status: List[DealPhase] = Field(default_factory=list)
    team: ProjectTeamFilter | None = None
    include_archived: bool = False


class Req_SearchTimeEntries(BaseModel):
    """Search time entries with filters (autopaginated)."""
    tool: Literal["/time/search"] = "/time/search"
    employee: EmployeeID | None = None
    customer: CompanyID | None = None
    project: ProjectID | None = None
    date_from: str | None = None
    date_to: str | None = None
    work_category: str | None = None
    billable: BillableFilter = ""
    status: TimeEntryStatus = ""


# --- Internal Tools (Not SDK Calls) ---

class Req_LoadRespondInstructions(BaseModel):
    """Load response formatting instructions. MUST call once before /respond."""
    tool: Literal["/load-respond-instructions"] = "/load-respond-instructions"

 # --- All Tools ---

ERC3_SDK_TOOLS = Union[
    # Terminal action
    Req_ProvideAgentResponse,
    # Internal tools
    Req_LoadRespondInstructions,
    # Employee directory
    Req_ListEmployees,
    Req_SearchEmployees,
    Req_GetEmployee,
    Req_UpdateEmployeeInfo,
    # Customers
    Req_ListCustomers,
    Req_SearchCustomers,
    Req_GetCustomer,
    # Projects
    Req_ListProjects,
    Req_SearchProjects,
    Req_GetProject,
    Req_UpdateProjectTeam,
    Req_UpdateProjectStatus,
    # Wiki
    Req_LoadWiki,
    Req_SearchWiki,
    Req_UpdateWiki,
    # Time tracking
    Req_LogTimeEntry,
    Req_UpdateTimeEntry,
    Req_GetTimeEntry,
    Req_SearchTimeEntries,
    Req_TimeSummaryByProject,
    Req_TimeSummaryByEmployee,
]


class NextStepERC3Orchestrator(BaseModel):
    """Structured output for ERC3 orchestrator planning."""
    current_state: str = Field(..., description="Summarize confirmed facts: user identity, data already retrieved, outstanding blockers.")
    remaining_work: List[str] = Field(..., description="Numbered plan (<=5 items) from current state to completion. Update as progress is made.")
    next_action: str = Field(..., description="Describe what to do next and why it moves the plan forward.")
    function: ERC3_SDK_TOOLS = Field(..., description="SDK call to execute now or /respond to finish.")



# ============================================================================
# CONTEXT BUILDER
# ============================================================================
# Selects relevant context blocks for the task.

system_prompt_context_builder = """
<role>
You are a context selection assistant. Your job is to identify which context blocks are relevant to the user's task.
</role>

<input>
You will receive:
1. A session block (user identity, date, location)
2. An employee profile (current user's details)
3. A list of available context blocks with their content
4. The user's task
</input>

<selection_principles>
Bias toward inclusion:
- When uncertain whether a block is relevant, INCLUDE it
- Missing relevant context causes failures; extra context does not
- Err on the side of inclusion

Collection references:
- If the task references a CATEGORY of entities, include ALL blocks of that type
- Words like "all", "every", "my" (referring to collections), or plural nouns signal this

Semantic matching:
- Match by MEANING, not exact strings
- Entity references may be paraphrased, abbreviated, or described indirectly
- If a block's content matches the intent of what the task is asking about, include it

Entity vs system tasks:
- Entity tasks operate on user's data (projects, customers, time entries) - include relevant entity blocks
- System tasks operate on global resources (wiki, employee directory, dates) - entity blocks usually NOT relevant

Empty/error blocks:
- Blocks like [no_user_projects] or [error_user_customers] ARE relevant when the task asks about that data type
- They indicate absence or unavailability of data
</selection_principles>

<output>
Output the block names exactly as shown in the available blocks list.
</output>
"""

class ContextSelection(BaseModel):
    """Context builder's selection of relevant blocks."""
    reasoning: str = Field(..., description="2-4 sentences explaining relevance. Cite specific task requirements.")
    selected_blocks: List[str] = Field(..., description="Block names to include. When uncertain, include rather than exclude.")



# ============================================================================
# STEP VALIDATOR PROMPT & SCHEMA
# ============================================================================

system_prompt_erc3_step_validator = """
<role>
You validate the ERC3 orchestrator's next step before it runs. Stop rule violations, missing prerequisites, or premature completion.
</role>

<what_you_receive>
1. AGENT SYSTEM PROMPT (capabilities & duties of agent you validating).
2. CONVERSATION HISTORY (what the agent has seen).
3. PROPOSED NEXT STEP (current_state, rule_check, remaining_work, next_action, call).
</what_you_receive>

<validation_focus>
- RULE ALIGNMENT: Does `rule_check` cite the correct policy? Is the action permitted for this user?
- DATA READINESS: Are prerequisites satisfied (e.g., project IDs known before updates)?
- PLAN QUALITY: Does `next_action` advance the first item in `remaining_work`? Is the plan realistic?
- TERMINAL ACTIONS: Is /respond justified? Have all requirements been met or denied with evidence?
</validation_focus>

<output_guidelines>
- Approve only if the plan is sound and compliant.
- If rejecting, set is_valid=false and explain what must change.
- Keep feedback concise and actionable.
</output_guidelines>
"""


class ERC3StepValidatorResponse(BaseModel):
    """Validator response for ERC3 planning checks."""
    analysis: str = Field(..., description="Brief reasoning about the plan's strengths/weaknesses.")
    is_valid: bool = Field(..., description="True if the plan is safe to execute.")
    rejection_message: str = Field(default="", description="Actionable feedback when rejecting.")
