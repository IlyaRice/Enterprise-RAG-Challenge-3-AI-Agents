"""
ERC3 benchmark prompts and schemas.

Contains:
- Context builder: ContextSelection schema, system_prompt_context_builder
- Orchestrator prompts and schemas
- Terminal action definitions
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
from erc3.erc3.dtos import Req_LogTimeEntry as Req_LogTimeEntry_Vendor


# ============================================================================
# WRAPPER CLASSES FOR SCHEMA FIXES
# ============================================================================
# Flattened wrappers to fix field ordering issues in vendored DTOs.

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


# ============================================================================
# AUTOPAGINATED WRAPPERS
# ============================================================================
# Simplified wrappers without limit/offset - autopaginated by execute layer.

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


# ============================================================================
# INTERNAL TOOLS (NOT SDK CALLS)
# ============================================================================

class Req_LoadRespondInstructions(BaseModel):
    """Load response formatting instructions. MUST call once before /respond."""
    tool: Literal["/load-respond-instructions"] = "/load-respond-instructions"


# ============================================================================
# CONTEXT BUILDER
# ============================================================================
# Selects relevant context blocks for the task.

class ContextSelection(BaseModel):
    """Context builder's selection of relevant blocks."""
    reasoning: str = Field(..., description="2-4 sentences explaining relevance. Cite specific task requirements.")
    selected_blocks: List[str] = Field(..., description="Block names to include. When uncertain, include rather than exclude.")


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
# ============================================================================
# RULE EXTRACTION (INGESTION-TIME)
# ============================================================================
# Extracts rules from wiki files at ingestion time, stored as markdown files.

class FileExtraction(BaseModel):
    """Extracted content from a single wiki file."""
    source_file: str = Field(..., description="Wiki file path (e.g., 'rulebook.md')")
    content: str = Field(..., description="Relevant content from this file, verbatim. Use [...] to mark skipped irrelevant sections.")


class ExtractedRulesResponse(BaseModel):
    """Response from rule extraction LLM."""
    files: List[FileExtraction] = Field(..., description="One entry per file that contains relevant rules")


class ValidatorResponse(BaseModel):
    """Response from validation LLM."""
    analysis: str = Field(..., description="Brief analysis of the work")
    is_valid: bool = Field(..., description="Pass or fail")
    rejection_message: str = Field(default="", description="What's wrong + what to fix")


class ResponseRuleExtraction(BaseModel):
    """Categorized rule extraction for /respond tool behavior."""
    outcome_rules: str = Field(..., description="Rules for when to use each outcome type")
    link_rules: str = Field(..., description="Rules for each link kind")
    message_formatting: str = Field(..., description="Message content rules")
    general_constraints: str = Field(..., description="Cross-cutting rules")


extraction_prompt_public = """
Your task is to retrieve a subset of rules for a corporate AI chatbot agent. 
However, at this stage, any rules concerning AUTHENTICATED users (logged-in employees, staff members) are completely irrelevant. 
Also completely irrelevant are rules concerning response formatting using the /respond tool.
Extract all rules concerning PUBLIC users (guests, anonymous visitors, unauthenticated users), except for rules about response formatting.


Specifically, omit:
- Any rules concerning determining permissions and access rights for AUTHENTICATED users of any level.
- Any information concerning AUTHENTICATED users.

- Any rules about how to choose the outcome field for the respond (ok_answer, ok_not_found, denied_security, etc.)
- Any rules about attaching links to responses in the respond
- Any rules about formulating response messages in the respond
- Any other guidance on using the /respond tool

Keep everything else:
- All rules about what actions PUBLIC users can perform
- All rules about what information PUBLIC users can access
- All permission and prohibition rules related to PUBLIC users.
- All data access restrictions related to PUBLIC users.
- All other AI agent behavioral rules related to PUBLIC users.
- ALL general rules that cannot be clearly attributed to either PUBLIC or AUTHENTICATED users should be included to ensure complete coverage.

For intertwined content: surgically extract only what's relevant, preserving original phrasing with minimal adaptation.

Return rules preserving original phrasing where possible (non-critical deviations are acceptable), maintaining formatting and headers.
"""

extraction_prompt_authenticated = """
Your task is to retrieve a subset of rules for a corporate AI chatbot agent. 
However, at this stage, any rules concerning PUBLIC users (guests, anonymous visitors, unauthenticated users) are completely irrelevant. 
Also completely irrelevant are rules concerning response formatting using the /respond tool.
Extract all rules concerning AUTHENTICATED users (logged-in employees, staff members), except for rules about response formatting.

Specifically, omit:
- Any rules concerning determining permissions and access rights for PUBLIC users.
- Any information concerning PUBLIC users.

- Any rules about how to choose the outcome field for the respond (ok_answer, ok_not_found, denied_security, etc.)
- Any rules about attaching links to responses in the respond
- Any rules about formulating response messages in the respond
- Any other guidance on using the /respond tool

Keep everything else:
- All rules about what actions AUTHENTICATED users can perform
- All rules about what information AUTHENTICATED users can access
- All permission and prohibition rules related to AUTHENTICATED users.
- All data access restrictions related to AUTHENTICATED users.
- All other AI agent behavioral rules related to AUTHENTICATED users.
- ALL general rules that cannot be clearly attributed to either PUBLIC or AUTHENTICATED users should be included to ensure complete coverage.

For intertwined content: surgically extract only what's relevant, preserving original phrasing with minimal adaptation.

Return rules preserving original phrasing where possible (non-critical deviations are acceptable), maintaining formatting and headers.
"""

extraction_prompt_response = """
<role>
You are a Systems Architect extracting rules for the /respond tool in a categorized structure.
</role>

<system_context>
The AI Agent is a sophisticated tool-using system. It operates in a Thought/Action loop.
Before formulating a response, the agent has access to the following Internal Tools to read/write data:

- Identity/Scope: /whoami
- Data Retrieval: /employees/list, /employees/search, /employees/get, /wiki/list, /wiki/load, /wiki/search, /customers/list, /customers/get, /customers/search, /projects/list, /projects/get, /projects/search, /time/get, /time/search, /time/summary/by-project, /time/summary/by-employee
- Data Modification: /employees/update, /wiki/update, /projects/team/update, /projects/status/update, /time/log, /time/update
- Response: /respond

Target Scope:
You are NOT extracting rules for how to use the search or update tools.
You ARE extracting rules for the final step: the usage of the /respond tool.
</system_context>

<interface_definitions>
The agent MUST use the /respond tool to communicate. You MUST pay special attention to rules governing these specific parameters:

1. Outcomes (The Outcome field):
- ok_answer
- ok_not_found
- denied_security
- none_clarification_needed
- none_unsupported
- error_internal

2. Entity Linking (The Links array):
- employee
- customer
- project
- wiki
- location

3. Message field - the text response to the user

4. Structure: Req_ProvideAgentResponse(message, outcome, links)
</interface_definitions>

<categorization_instructions>
You MUST organize extracted rules into 4 categories:

CATEGORY 1 - outcome_rules:
Extract ALL rules about when to use each outcome type. Include rules for all 6 outcomes:
- When to use ok_answer 
- When to use ok_not_found
- When to use denied_security (permissions, security constraints)
- When to use none_clarification_needed (ambiguous requests)
- When to use none_unsupported (features not available)
- When to use error_internal (system failures)

CATEGORY 2 - link_rules:
Extract ALL rules about the Links array for all 5 entity kinds:
- When to include/exclude employee links
- When to include/exclude customer links
- When to include/exclude project links
- When to include/exclude wiki links
- When to include/exclude location links
- Rules about link IDs (internal vs public visibility)
- Whether to link entities mentioned in denied responses

CATEGORY 3 - message_formatting:
Extract ALL rules about the message content:
- What information is prohibited
- What information is required (e.g., explanations for denials, or specific phrases)
- Tone and style requirements

CATEGORY 4 - general_constraints:
Extract ALL cross-cutting rules that apply across categories:
- Rules that span multiple outcomes or link types
- Any rules that don't fit cleanly into the above 3 categories
</categorization_instructions>

<cohesion_guidelines>
Do not fragment rules. To prevent loss of context:
- If a constraint is embedded in a larger paragraph about permissions, extract the whole paragraph.
- If a section mixes internal logic (checking access) and output logic (what to say), extract the full section.
- It is better to include slightly more context than to cut a rule mid-sentence.
</cohesion_guidelines>

<what_to_exclude>
Skip these even if they mention communication:
- General company culture ("how people interact", "team prefers short updates")
- How EMPLOYEES should communicate with customers
- Company mission, vision, values, history, or background
- Office atmosphere or working style

If it's about human-to-human communication → EXCLUDE
If it's about internal tool usage (not /respond output) → EXCLUDE
</what_to_exclude>
"""

# Temporary piece of prompt
# <output_format>
# Rules must be compact RFC-style, ok to use pseudo code for compactness.
# </output_format>

validator_prompt = """
<role>
You are a quality validator. You assess whether a task was completed correctly.
</role>

<inputs>
You will receive:
1. The INSTRUCTIONS: A system prompt (instructions) and user message (data to process)
2. The OUTPUT: The result produced by an assistant
</inputs>

<job>
Determine if the OUTPUT correctly fulfills the INSTRUCTIONS requirements.

Your validation is critical. Be thorough and precise, but stay focused on what matters most. Don't get lost in minor details at the expense of catching major issues.
</job>

<validation_approach>
- Read the INSTRUCTIONS carefully to identify PRIMARY vs SECONDARY requirements
- PRIMARY: Core objective stated in the task - THIS IS YOUR MAIN FOCUS
- SECONDARY: Formatting and structural details
- Evaluate PRIMARY requirements first - major failures here mean rejection
  * Be especially rigorous here - these are the most important requirements
  * A failure in PRIMARY requirements is always grounds for rejection
- Then check SECONDARY requirements
  * Be thorough but proportionate - don't reject for trivial formatting issues if the core task is done correctly
- In rejection_message, structure feedback as:
  1. Most critical issues (PRIMARY requirements violated)
  2. Secondary issues (if any)
  3. What to fix, in order of importance
</validation_approach>

<output>
- analysis: Brief assessment of the work
- is_valid: True if requirements are met, False otherwise
- rejection_message: If invalid, explain what's wrong and what to fix
</output>
"""


# ============================================================================
# FILE TAGGING (INGESTION-TIME)
# ============================================================================
# Identifies which wiki files contain rules/policies and enriches with metadata.

class CompanyInfo(BaseModel):
    """Company basic information."""
    name: str = Field(..., description="Official company name")
    locations: List[str] = Field(..., description="Office cities only")
    executives: List[str] = Field(..., description="Leadership names with roles")

class FileTag(BaseModel):
    """Metadata for a single wiki file."""
    filename: str = Field(..., description="Wiki filename (e.g., 'rulebook.md')")
    category: Literal["agent_directive", "agent_reference", "background_context", "human_flavor", "conditional_entity"] = Field(
        ..., 
        description="Agent-centric utility classification"
    )
    summary: str = Field(..., description="1-3 sentence inventory of file contents following template: 'Contains: [topics]. Includes: [examples].'")
    has_rules: bool = Field(..., description="True if file contains actionable rules/policies that constrain agent behavior")


class TaggingResponse(BaseModel):
    """Response from file tagging LLM."""
    files: List[FileTag] = Field(..., description="Metadata for each wiki file")
    company: CompanyInfo = Field(..., description="Company basic info extracted from wiki files")


tagging_prompt = """
<role>
You are creating a metadata index for an AI agent system. This index helps the agent decide which wiki files to load for each task.
</role>

<context>
This is NOT documentation for humans - it's an agent utility index. Focus on how the agent will USE each file, not what humans would find interesting.
</context>

<task>
For each wiki file, generate three metadata fields:

1. **category** (single choice): How does the agent USE this file?
   - `agent_directive`: Rules/constraints the agent MUST follow (e.g., rulebook.md, policy files)
   - `agent_reference`: Data for answering queries - hierarchies, systems, skills definitions (e.g., hierarchy.md, skills.md, systems.md)
   - `background_context`: Optional enrichment that improves responses but isn't required (e.g., culture.md, history/background narratives)
   - `human_flavor`: Human-only content with no agent utility (e.g., marketing copy, mission statements)
   - `conditional_entity`: Entity profiles useful only when task mentions that entity (e.g., people/*.md, offices/*.md)

2. **summary** (1-3 sentences, ~150 characters): Inventory of file contents
   - Template: "Contains: [data types/topics]. Includes: [specific examples]."
   - Example: "Contains organizational structure and reporting chains. Includes CEO/CTO roles, department breakdown, manager-employee relationships."
   - Be concrete and specific, not vague

3. **has_rules** (boolean): Does this file contain actionable rules/policies that constrain agent behavior?
   - True if: File defines WHO can do WHAT, access control, permissions, data sensitivity, response requirements
   - True if: Contains MUST/MUST NOT/FORBIDDEN/DENIED/PROHIBITED constraints
   - False if: Pure background, culture, profiles, history, marketing
</task>

<category_examples>
- rulebook.md → agent_directive (defines access rules agent must enforce)
- hierarchy.md → agent_reference (data about org structure for queries)
- skills.md → agent_reference (skill definitions for lookups)
- culture.md → background_context (enrichment but not required)
- mission_vision.md → human_flavor (no agent utility)
- people/felix_baum.md → conditional_entity (only useful if task mentions Felix)
- offices/munich.md → conditional_entity (only useful if task mentions Munich)
- background.md → background_context or human_flavor (depends on content)
</category_examples>

<edge_cases>
- If uncertain between categories, choose based on PRIMARY agent utility
- If file has mixed purpose, select the most important use case
- If file seems useless for agent, mark as human_flavor
</edge_cases>

<output_format>
Return structured metadata for EVERY file provided. Do not skip any files.
Also, extract company name, office city names, and executive names with roles from wiki.
</output_format>
"""


# ============================================================================
# ERC3 ORCHESTRATOR - PROMPTS & SCHEMAS
# ============================================================================

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


class SingleCallERC3(BaseModel):
    """Single-call structure for ERC3 orchestrator."""
    call_mode: Literal["single"]
    function: ERC3_SDK_TOOLS

class NextStepERC3Orchestrator(BaseModel):
    """Structured output for ERC3 orchestrator planning."""
    current_state: str = Field(..., description="Summarize confirmed facts: user identity, data already retrieved, outstanding blockers.")
    remaining_work: List[str] = Field(..., description="Numbered plan (<=5 items) from current state to completion. Update as progress is made.")
    next_action: str = Field(..., description="Describe what to do next and why it moves the plan forward.")
    call: SingleCallERC3 = Field(..., description="SDK call to execute now or /respond to finish.")


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

