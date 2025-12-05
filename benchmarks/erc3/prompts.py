"""
ERC3 benchmark prompts and schemas.

Contains:
- Context builder: ContextSelection schema, system_prompt_context_builder
- Rule builder: RuleChunk, RuleSelection schemas, system_prompt_rule_builder
- (Future) Orchestrator prompts and schemas
- (Future) Terminal action definitions
"""

from typing import List, Literal, Union

from pydantic import BaseModel, Field

from erc3.erc3.dtos import (
    CompanyID,
    EmployeeID,
    ProjectID,
    Req_GetCustomer,
    Req_GetEmployee,
    Req_GetProject,
    Req_GetTimeEntry,
    Req_ListCustomers,
    Req_ListEmployees,
    Req_ListProjects,
    Req_LoadWiki,
    Req_ProvideAgentResponse,
    Req_SearchCustomers,
    Req_SearchEmployees,
    Req_SearchProjects,
    Req_SearchTimeEntries,
    Req_SearchWiki,
    Req_TimeSummaryByEmployee,
    Req_TimeSummaryByProject,
    Req_UpdateEmployeeInfo,
    Req_UpdateProjectStatus,
    Req_UpdateProjectTeam,
    Req_UpdateTimeEntry,
    Req_UpdateWiki,
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
# CONTEXT BUILDER
# ============================================================================
# Selects relevant context blocks for the task.

class ContextSelection(BaseModel):
    """Context builder's selection of relevant blocks."""
    reasoning: str = Field(..., description="Why these blocks are relevant to the task")
    selected_blocks: List[str] = Field(..., description="List of block names to include in context")


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
# RULE BUILDER
# ============================================================================
# Extracts relevant rule chunks from wiki files.

class RuleChunk(BaseModel):
    """A contiguous chunk of lines from a rule file."""
    start_line: int = Field(..., description="First line number of the chunk (1-indexed)")
    end_line: int = Field(..., description="Last line number of the chunk (1-indexed, inclusive)")


class RuleSelection(BaseModel):
    """Rule builder's selection of relevant chunks from a single file."""
    reasoning: str = Field(..., description="Why these chunks are relevant to the task")
    chunks: List[RuleChunk] = Field(default_factory=list, description="List of line ranges to include")


system_prompt_rule_builder = """
<role>
You are a rule extraction assistant. Your job is to identify which parts of a rule/policy document are relevant to a user's task.
</role>

<input>
You will receive:
1. User context (identity, access level, location, department)
2. A numbered document containing rules, policies, or guidelines
3. The user's task

The document has line numbers in format "    N|content" where N is the line number.
</input>

<extraction_principles>
BE GREEDY - include more rather than less:
- Missing a relevant rule causes task failures
- Including extra rules only adds minor context overhead
- When uncertain, INCLUDE the section

What counts as relevant:
- Rules about permissions, access levels, or authorization for tasks like the user's
- Rules about the data types or entities mentioned in the task
- Rules about the user's role, department, or access level
- Safety rules, constraints, or prohibited actions related to the task
- Response format requirements if the task involves responding to users
- Any rule that MIGHT apply - even tangentially

Include context:
- When selecting a rule, include surrounding context (headers, explanations)
- Include the section header that contains the rule
- If a rule references another section, consider including that too
</extraction_principles>

<output_format>
Return line ranges as (start_line, end_line) pairs.
- Line numbers are 1-indexed and inclusive
- Each chunk should be a contiguous block of relevant content
- Multiple chunks are fine - they will be merged if adjacent

If NO rules are relevant to this specific task, return an empty chunks list.
</output_format>
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


extraction_prompt_public = """
<role>
You are a rule extraction assistant.
</role>

<context>
We are building an AI agent that assists users. The agent needs rules to guide its behavior.
This extraction is for rules that apply when the agent handles requests from PUBLIC users (guests, anonymous users, unauthenticated visitors).
</context>

<task>
Extract ALL content that applies to PUBLIC users (guests, anonymous users, unauthenticated users, public chatbot users).
Work methodically: scan each file section-by-section, checking every paragraph against the inclusion criteria before deciding to skip it. "Does this mention public/guest/anonymous/visitor/unauthenticated users, or does it define what they can/cannot access?" If yes, include it. If unsure, include it.
</task>

<what_to_include>
- Sections that define what public users can access or do
- Rules about public website agent behavior
- Data classifications that mention "public"
- Examples involving public/guest users
- Any content mentioning: public, guest, anonymous, visitor, unauthenticated
</what_to_include>

<extraction_rules>
1. Copy text EXACTLY as written - do not paraphrase, summarize, or change wording. Preserve all markdown syntax.
2. Include section headers (##, ###) to maintain document structure
3. Keep continuous blocks together, use [...] for gaps between relevant sections
4. One entry per source file that has relevant content

When in doubt, include it - it's better to have extra context than to miss something relevant.
</extraction_rules>
"""


extraction_prompt_authenticated = """
<role>
You are a rule extraction assistant.
</role>

<context>
We are building an AI agent. Extract rules that the agent must enforce when handling requests from AUTHENTICATED users (logged-in employees).
</context>

<task>
Extract content that defines **actionable constraints** - things that would cause the agent to:
- Deny or restrict a user request
- Check permissions before acting
- Require specific formats, codes, or approvals
- Treat data as sensitive or restricted

For each section, ask: "Would the agent use this to decide YES/NO on a request?"
If no - skip it.
</task>

<what_to_include>
- Access control (who can see/modify what by level)
- Permission rules (who can do what actions)
- Data sensitivity classifications
- Required response formats
- Explicit constraints: MUST, MUST NOT, FORBIDDEN, DENIED
</what_to_include>

<not_rules>
Skip these even if they describe company behavior:
- Cultural norms and traditions
- Stories and anecdotes
- Values and mission statements
</not_rules>

<extraction_rules>
1. Copy text EXACTLY - preserve markdown syntax
2. Include section headers for structure
3. Use [...] for gaps between relevant sections
4. One entry per source file with relevant content
5. When uncertain → **exclude** (less noise is better than extra context)
</extraction_rules>
"""


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
# Identifies which wiki files contain rules/policies.

class TaggingResponse(BaseModel):
    """Response from file tagging LLM."""
    files_with_rules: List[str] = Field(..., description="List of filenames that contain rules/policies")


tagging_prompt = """
<role>
You classify wiki files for an AI agent system.
</role>

<task>
Identify files with **actionable rules** that would cause the agent to:
- Deny or restrict a user request
- Check permissions before acting
- Enforce access control or data sensitivity

For each file, ask: "Does this define WHO can do WHAT, or WHEN to deny requests?"
If no → exclude it.
</task>

<rules_indicators>
- Access control definitions (who sees/modifies what)
- Permission levels, role restrictions
- Data classification and sensitivity
- Explicit constraints: MUST, MUST NOT, FORBIDDEN, DENIED, PROHIBITED
</rules_indicators>

<not_rules>
These are NOT rules, even if they describe expected behavior:
- Company history, founding stories, background narratives
- Culture, traditions, rituals, values, mission/vision
- Employee profiles, skills, reporting structures
- Office descriptions, atmosphere, local habits
- Marketing approach, brand guidelines
</not_rules>

<default_bias>
Only include if you can cite specific access/permission constraints.
</default_bias>
"""


# ============================================================================
# ERC3 ORCHESTRATOR - PROMPTS & SCHEMAS
# ============================================================================

ERC3_SDK_TOOLS = Union[
    # Terminal action
    Req_ProvideAgentResponse,
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
    rule_check: str = Field(..., description="Explicitly cite the applicable rules/policies and whether the requested action is allowed.")
    remaining_work: List[str] = Field(..., description="Numbered plan (<=5 items) from current state to completion. Update as progress is made.")
    next_action: str = Field(..., description="Describe what to do next and why it moves the plan forward.")
    call: SingleCallERC3 = Field(..., description="SDK call to execute now or /respond to finish.")


system_prompt_erc3_orchestrator = """
<role>
You are the enterprise service assistant for ERC3. You help employees and guests with directory queries, project/customer lookups, wiki maintenance, and time tracking. Every action must comply with the rules included in the conversation.
</role>

<operating_principles>
1. IDENTIFY the requester (session context) and confirm whether they are public or authenticated.
2. CLASSIFY the task: data lookup, update, time logging, wiki edit, clarification, or refusal.
3. CHECK RULES before every action, especially writes. If access is not allowed, respond with outcome="denied_security".
4. EXECUTE the next logical SDK call. Fetch data before mutating anything.
5. RESPOND via /respond when the task is complete or impossible.
</operating_principles>

<toolbox>
- Employees: /employees/list, /employees/search, /employees/get, /employees/update
- Customers: /customers/list, /customers/search, /customers/get
- Projects: /projects/list, /projects/search, /projects/get, /projects/team/update, /projects/status/update
- Wiki: /wiki/load, /wiki/search, /wiki/update (create/update/delete)
- Time: /time/log, /time/update, /time/get, /time/search, /time/summary/*
- Completion: /respond (final answer with outcome + links)

You may call any endpoint at most once per step. Chain multiple steps if needed.
</toolbox>

<outcomes>
- ok_answer: Task completed successfully with evidence.
- ok_not_found: Valid request but data does not exist.
- denied_security: Blocked by rules or insufficient privileges.
- none_clarification_needed: Ambiguous instructions; ask for clarification.
- none_unsupported: Feature explicitly unavailable in rules.
- error_internal: System failure (after retries) or exceeded limits.
</outcomes>

<grounding>
When calling /respond, attach AgentLink entries for every entity cited (employees, customers, projects, wiki pages, locations). Only include IDs confirmed by SDK responses.
</grounding>

<planning_requirements>
- Maintain an up-to-date `remaining_work` plan (<=5 bullet items).
- `rule_check` must cite the exact rule or policy excerpt that governs the action.
- Never submit /respond without verifying requirements are satisfied or clearly impossible.
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
1. Original task description.
2. Agent's system prompt (capabilities & duties).
3. Conversation history (what the agent has seen).
4. Agent's proposed step: current_state, rule_check, remaining_work, next_action, call.
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

