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
# ACCESS EVALUATOR
# ============================================================================
# Preliminary access control analysis for tasks.

class AccessEvaluation(BaseModel):
    """Access evaluator's preliminary permission analysis."""
    reasoning: str = Field(..., description="Structured analysis: user level, action type, applicable rule, conditional factor if any")
    determination: Literal["PERMITTED", "DENIED", "CONDITIONAL"] = Field(..., description="PERMITTED if allowed, DENIED if prohibited, CONDITIONAL if depends on discoverable factor")
    conditional_factor: str | None = Field(default=None, description="If CONDITIONAL: specific factor to check during execution, phrased as clear condition")


system_prompt_access_evaluator = """
<role>
You are a preliminary access analyst. Your output guides an AI agent that will execute the user's task.
Analyze whether the AI agent can execute the user's request based on the user's identity and access control rules.
</role>

<scope>
Focus ONLY on permission rules based on user identity and role.
Ask yourself: "Is this about WHO can do this action, or about WHETHER this specific input is valid?"
- WHO can do it → in scope (user level, role, relationships, ownership)
- WHETHER input is valid → out of scope (data formats, business process compliance, JIRA requirements)
</scope>

<reasoning_structure>
Follow this structure (one sentence each):
1. User's access level and how determined
2. Action category (read/write/admin)
3. Applicable rule outcome
4. Conditional factor if permission depends on discoverable data
5. Why you chose PERMITTED/DENIED/CONDITIONAL

Do not cite rule section numbers or copy rule text verbatim.
</reasoning_structure>

<determinations>
- PERMITTED: Rules clearly allow this action for this user
- DENIED: Rules clearly prohibit this action for this user
- CONDITIONAL: Permission depends on a factor that can be discovered through normal tool execution
</determinations>

<conditional_factor_guidance>
If CONDITIONAL, specify what must be true for permission. Be specific about:
- The exact relationship to check (e.g., "whether user is lead of the mentioned project")
- The parties involved (use names from the task)
- The expected outcomes: if true → permitted, if false → denied

The agent will discover this through normal data retrieval, not by asking the user.
</conditional_factor_guidance>
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
    reasoning: str = Field(..., description="2-4 sentences explaining relevance. Cite specific task requirements.")
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

Return empty chunks list ONLY if clearly certain no rules apply.
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


class ResponseRuleExtraction(BaseModel):
    """Categorized rule extraction for /respond tool behavior."""
    outcome_rules: str = Field(..., description="Rules for when to use each outcome type")
    link_rules: str = Field(..., description="Rules for each link kind")
    message_formatting: str = Field(..., description="Message content rules")
    general_constraints: str = Field(..., description="Cross-cutting rules")


class AccessControlRuleExtraction(BaseModel):
    """Categorized access control rule extraction."""
    access_level_rules: str = Field(..., description="Core access levels and determination")
    action_permission_matrix: str = Field(..., description="Which levels can perform which actions")
    role_based_modifiers: str = Field(..., description="How job roles affect permissions")
    project_based_modifiers: str = Field(..., description="How project participation affects permissions")
    relationship_modifiers: str = Field(..., description="Manager-report, team, customer relationships")
    special_exceptions: str = Field(..., description="Named individuals or category exceptions")
    contextual_factors: str = Field(..., description="Time, location, data sensitivity")


# ============================================================================
# GLOSSARY EXTRACTION (INGESTION-TIME)
# ============================================================================

class CompanyInfo(BaseModel):
    name: str
    locations: List[str] = Field(..., description="City names only")
    executives: List[str] = Field(..., description="Full names of leadership team only")

class SkillOrWill(BaseModel):
    name: str
    description: str

class SkillsAndWills(BaseModel):
    items: List[SkillOrWill] = Field(..., description="All skills and wills mixed together")
    general_notes: str = Field(..., description="Context about skills/wills system usage")

class CategoryItem(BaseModel):
    value: str
    description: str

class TermCategory(BaseModel):
    items: List[CategoryItem]
    general_notes: str = Field(..., description="Context about category purpose")

class AgentGlossary(BaseModel):
    company: CompanyInfo
    skills_and_wills: SkillsAndWills
    deal_phases: TermCategory
    team_roles: TermCategory
    time_entry_statuses: TermCategory


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

extraction_prompt_user_specific = """
Your task is to retrieve a subset of rules for a corporate AI chatbot agent that works for a SPECIFIC employee.
The employee's full profile is provided in the user message.
However, at this stage, any rules concerning PUBLIC users (guests, anonymous visitors, unauthenticated users) are completely irrelevant.
Also completely irrelevant are rules concerning response formatting using the /respond tool.
Extract all rules that apply to this specific employee, except for rules about response formatting.

Specifically, omit:
- Any rules concerning determining permissions and access rights for PUBLIC users.
- Any information concerning PUBLIC users.

- Any rules about how to choose the outcome field for the respond (ok_answer, ok_not_found, denied_security, etc.)
- Any rules about attaching links to responses in the respond
- Any rules about formulating response messages in the respond
- Any other guidance on using the /respond tool

Keep everything else:
- All rules about what actions this employee can perform
- All rules about what information this employee can access
- All permission and prohibition rules relevant to this employee based on their department, location, role, or seniority
- All data access restrictions that apply to this employee
- Any rules that mention this employee by name
- All other AI agent behavioral rules relevant to this employee
- ALL general rules for authenticated users that cannot be clearly excluded based on the employee's profile should be included to ensure complete coverage.

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

extraction_prompt_respond_public = """
Your task is to extract ALL respond/response rules for PUBLIC users from wiki files.

CONTEXT: You will see ALREADY EXTRACTED PUBLIC RULES for reference only. Ignore them when deciding what to extract.

Extract ALL rules about /respond for PUBLIC users, including:
- When to use each outcome (ok_answer, ok_not_found, denied_security, none_clarification_needed, none_unsupported, error_internal)
- How to attach links (AgentLink) for PUBLIC users
- How to formulate response messages for PUBLIC users
- Any Req_ProvideAgentResponse guidance for PUBLIC mode

DUPLICATION IS OK: Extract respond rules even if similar content appears in the already extracted rules. We want a complete standalone respond ruleset.

NEVER RETURN EMPTY: You must extract rules. The wiki files contain Response Contract section - extract it.

DO NOT extract:
- General access control/permission rules unrelated to /respond output
- Rules about internal tool usage (search, update, etc.)
- Rules that apply only to AUTHENTICATED users

Return rules preserving original phrasing, maintaining formatting and headers.
"""

extraction_prompt_respond_authenticated = """
Your task is to extract ALL respond/response rules for AUTHENTICATED users from wiki files.

CONTEXT: You will see ALREADY EXTRACTED AUTHENTICATED RULES for reference only. Ignore them when deciding what to extract.

Extract ALL rules about /respond for AUTHENTICATED users, including:
- When to use each outcome (ok_answer, ok_not_found, denied_security, none_clarification_needed, none_unsupported, error_internal)
- How to attach links (AgentLink) for AUTHENTICATED users
- How to formulate response messages for AUTHENTICATED users
- Any Req_ProvideAgentResponse guidance for AUTHENTICATED/internal mode

DUPLICATION IS OK: Extract respond rules even if similar content appears in the already extracted rules. We want a complete standalone respond ruleset.

NEVER RETURN EMPTY: You must extract rules. The wiki files contain Response Contract section - extract it.

DO NOT extract:
- General access control/permission rules unrelated to /respond output
- Rules about internal tool usage (search, update, etc.)
- Rules that apply only to PUBLIC users

Return rules preserving original phrasing, maintaining formatting and headers.
"""

extraction_prompt_glossary = """
<role>
Extract operational vocabulary that the AI agent needs to understand entities and concepts.
</role>

<task>
Scan wiki files and extract:

1. COMPANY INFO
   - Primary company name (official legal name if available)
   - Office locations (cities where company operates)
   - Executives (leadership team: CEO, CTO, COO, etc.) - include names and roles

2. SKILLS AND WILLS
   - Find all skill/will definitions with names and descriptions
   - Usually in skills.md or people profiles
   - Provide general_notes about how skills/wills are used in the system

3. DEAL PHASES
   - Extract meaning for: idea, exploring, active, paused, archived
   - Provide general_notes about phase lifecycle

4. TEAM ROLES
   - Extract meaning for: Lead, Engineer, Designer, QA, Ops, Other
   - Provide general_notes about team role system

5. TIME ENTRY STATUSES
   - Extract meaning for: "" (empty string), draft, submitted, approved, invoiced, voided
   - Provide general_notes about status workflow

<extraction_principles>
Extract ALL information related to each entity exhaustively. Include every detail found in the wiki.
Do NOT infer or guess - only extract what is explicitly stated in the source material.
If information is not found in the wiki, state "No info in company docs" rather than inferring or inventing details. If concept present but not defined - note accordingly.
Capture complete descriptions, examples, and any related context that helps understand each concept.
</extraction_principles>
"""

extraction_prompt_access_control = """
<task>
You are distilling company wiki files into a compact access control rulebook for an AI agent.

Your goal: Transform scattered policy documents into a structured, actionable checklist that the agent can use to make access decisions in real-time.

Process:
1. Read through all wiki files systematically
2. Identify every access control rule, policy, and permission statement
3. Reorganize rules into 7 logical categories (see below)
4. Rewrite each rule in compact, decision-friendly format
5. Resolve conflicts and clarify ambiguities
6. Create a coherent rulebook that answers: "Can user X perform action Y on resource Z?"
Rules must be compact RFC-style, ok to use pseudo code for compactness.
</task>

<questions_by_category>
Scan wiki files to answer these questions. Extract all relevant text verbatim.

ACCESS LEVEL RULES:
- How many access levels exist and what are they called?
- How is a user's base access level determined?
- What user attributes determine access level (role, department, seniority)?
- Are there default levels for new users or public/anonymous users?

ACTION PERMISSION MATRIX:
- What read actions can each level perform?
- What write actions can each level perform?
- What actions are explicitly denied to each level?
- Are there action categories or groups?
- Can lower levels perform any admin actions?

ROLE-BASED MODIFIERS:
- What employee roles exist (PM, Dev, Manager, etc.)?
- Do roles grant additional permissions beyond access level?
- Can roles restrict permissions despite access level?
- Are there role hierarchies or role combinations?

PROJECT-BASED MODIFIERS:
- Does project participation affect permissions?
- What can project team members do that non-members cannot?
- What can project leads do that regular team members cannot?
- Can project permissions override access level restrictions?
- Are there different types of project participation (active vs historical)?

RELATIONSHIP MODIFIERS:
- Does manager-report relationship affect permissions?
- Can managers access their reports' data?
- Can managers act on behalf of their reports?
- Does team membership (beyond projects) grant permissions?
- Do customer relationships affect permissions (e.g., account manager privileges)?

SPECIAL EXCEPTIONS:
- Are there named individuals with special permissions?
- Are there employee categories with special rules?
- What are the criteria for exception categories?
- How do exceptions interact with standard rules (override, supplement)?

CONTEXTUAL FACTORS:
- Do temporal factors affect permissions (e.g., can only modify recent data)?
- Do data sensitivity levels exist and affect access?
- Does data ownership affect permissions (e.g., own time entries, own projects)?
- Are there location-based or department-based access rules?
</questions_by_category>
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
# Identifies which wiki files contain rules/policies and enriches with metadata.

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

<access_guidance_usage>
If access_guidance block is present, use it to inform your approach. For CONDITIONAL determinations, discover the specified factor through normal tool execution - do not ask the user to verify it.
</access_guidance_usage>

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


system_prompt_erc3_respond_validator = """
<role>
You are a meticulous compliance validator for /respond calls. Your task is to enforce response formatting rules with extreme rigor through structured analysis before execution.
</role>

<what_you_receive>
1. AGENT SYSTEM PROMPT (capabilities & duties of agent you validating).
2. CONVERSATION HISTORY (what the agent has seen).
3. PROPOSED NEXT STEP (current_state, rule_check, remaining_work, next_action, call).
4. Response formatting rules from wiki (embedded in this validator's system prompt below)
</what_you_receive>

<response_formatting_rules>
{response_formatting_rules}
</response_formatting_rules>

<validation_approach>
You will perform validation in 4 phases, evaluating each component of the /respond call systematically:

PHASE 1: LINK DISCOVERY
PHASE 2: OUTCOME EVALUATION  
PHASE 3: MESSAGE CONTENT ANALYSIS
PHASE 4: FINAL VERDICT

Each phase builds on the previous to ensure comprehensive validation.
</validation_approach>

<phase_1_link_discovery>
OBJECTIVE: Identify all entity candidates that appeared anywhere in the workflow.

SCAN THESE SOURCES:
- Initial context blocks (session info, employee profile, context data)
- All tool call results (employees/get, projects/search, customers/list, wiki/load, etc.)
- Agent's proposed message text
- Any entity mentioned by ID or name throughout the conversation

EXTRACT ENTITIES:
For each entity found, create a LinkAnalysis entry with:
- kind: employee, customer, project, wiki, or location
- id: The entity's identifier as it appears
- arguments_for_including: Why this entity should be linked (was it used to answer? mentioned in message? directly relevant?)
- arguments_against_including: Why this entity should NOT be linked (tangential? prohibited by rules? not in agent's chosen links?)

GUIDANCE:
- When uncertain whether an entity is relevant, INCLUDE it in link_candidates
- Focus on entities directly related to answering the user's question
- Consider linking rules from response_formatting_rules (e.g., denied_security = no internal links)

OUTPUT: Populate link_candidates field
</phase_1_link_discovery>

<phase_2_outcome_evaluation>
OBJECTIVE: Evaluate whether the agent chose the correct outcome.

THE AGENT CHOSE: Look at the proposed call to see which outcome the agent selected.

YOUR TASK: For ALL 6 outcomes, provide dialectical reasoning.

GUIDANCE:
- Even if an outcome is clearly irrelevant, briefly explain why (e.g., "Not applicable - no system error occurred")
- Outcome correctness is the foundation - if wrong outcome, everything else is moot
- Be especially critical of the agent's chosen outcome

OUTPUT: Fill all 12 outcome_* fields
</phase_2_outcome_evaluation>

<phase_3_message_content>
OBJECTIVE: Analyze what should and shouldn't be in the message field.

Based on the agent's chosen outcome and the response_formatting_rules:

what_should_be_included:
- Format: "Required by rules: [X, Y]. Answer components: [A, B, C]."
- List mandatory elements from rules (e.g., acquisition name for public mode, denial explanation for denied_security)
- List factual answer components that should be present
- Cite specific rules where applicable

what_should_not_be_included:
- Format: "Prohibited: [X, Y] per [rule citation]."
- List prohibited content from rules (e.g., salaries, internal IDs in public mode, sensitive data)
- Cite specific rule violations if agent's message contains prohibited content

DEPENDENCIES:
- Message requirements vary by outcome (denied_security requires explanation, ok_answer requires answer content)
- Public vs authenticated mode affects what can be disclosed

OUTPUT: Fill message_analysis field
</phase_3_message_content>

<phase_4_final_verdict>
OBJECTIVE: Synthesize all analyses into final validation decision.

EVALUATE HOLISTICALLY:
- Is the chosen outcome correct per your Phase 2 analysis?
- Does the message comply with requirements per your Phase 3 analysis?
- Are the links correct per your Phase 1 analysis and linking rules?

is_valid:
- Set TRUE only if ALL components are correct
- A single violation in any component = FALSE

rejection_message:
- If invalid, structure feedback as: "OUTCOME: [issue with outcome_* fields]. MESSAGE: [issue with message_analysis]. LINKS: [issue with link_candidates]."
- Reference specific field names from your analysis (e.g., "See outcome_denied_security_for - this outcome is more appropriate because...")
- Be specific and actionable - what exactly must change?
- Cite rules verbatim where applicable

VALIDATION RIGOR:
- You MUST approve ONLY if the response fully complies with every single rule without exception
- A single rule violation MUST result in rejection
- You MUST NOT approve responses that are "mostly correct" - full compliance is mandatory
- Be extremely thorough - this is the final safeguard before response execution

OUTPUT: Fill is_valid and rejection_message fields
</phase_4_final_verdict>
"""
# For write operations (updates, creates, deletes), include links to both the modified entity and the user who performed the action, unless rules explicitly state otherwise.

class LinkAnalysis(BaseModel):
    """Analysis of a single entity link candidate."""
    kind: Literal["employee", "customer", "project", "wiki", "location"] = Field(..., description="Type of entity")
    id: str = Field(..., description="Entity identifier")
    arguments_for_including: str = Field(..., description="Reasoning why this entity should be linked")
    arguments_against_including: str = Field(..., description="Reasoning why this entity should not be linked")


class MessageAnalysis(BaseModel):
    """Analysis of message content requirements."""
    what_should_be_included: str = Field(..., description="What content should be in the message (category-based with rule citations)")
    what_should_not_be_included: str = Field(..., description="What content must not be in the message (with rule citations)")


class ERC3RespondValidatorResponse(BaseModel):
    """Structured validator response for /respond calls with dialectical reasoning."""
    # Link discovery and analysis
    link_candidates: List[LinkAnalysis] = Field(default_factory=list, description="All entities found in workflow with for/against arguments")
    
    # Outcome evaluation (all 6 outcomes)
    outcome_ok_answer_for: str = Field(..., description="Evidence and reasoning supporting ok_answer outcome")
    outcome_ok_answer_against: str = Field(..., description="Evidence and reasoning against ok_answer outcome")
    outcome_ok_not_found_for: str = Field(..., description="Evidence and reasoning supporting ok_not_found outcome")
    outcome_ok_not_found_against: str = Field(..., description="Evidence and reasoning against ok_not_found outcome")
    outcome_denied_security_for: str = Field(..., description="Evidence and reasoning supporting denied_security outcome")
    outcome_denied_security_against: str = Field(..., description="Evidence and reasoning against denied_security outcome")
    outcome_none_clarification_needed_for: str = Field(..., description="Evidence and reasoning supporting none_clarification_needed outcome")
    outcome_none_clarification_needed_against: str = Field(..., description="Evidence and reasoning against none_clarification_needed outcome")
    outcome_none_unsupported_for: str = Field(..., description="Evidence and reasoning supporting none_unsupported outcome")
    outcome_none_unsupported_against: str = Field(..., description="Evidence and reasoning against none_unsupported outcome")
    outcome_error_internal_for: str = Field(..., description="Evidence and reasoning supporting error_internal outcome")
    outcome_error_internal_against: str = Field(..., description="Evidence and reasoning against error_internal outcome")
    
    # Message content analysis
    message_analysis: MessageAnalysis = Field(..., description="Analysis of message content requirements and prohibitions")
    
    # Final verdict
    is_valid: bool = Field(..., description="True only if ALL components (outcome, message, links) are correct")
    rejection_message: str = Field(default="", description="Structured feedback referencing specific field names when invalid")


class ERC3StepValidatorResponse(BaseModel):
    """Validator response for ERC3 planning checks."""
    analysis: str = Field(..., description="Brief reasoning about the plan's strengths/weaknesses.")
    is_valid: bool = Field(..., description="True if the plan is safe to execute.")
    rejection_message: str = Field(default="", description="Actionable feedback when rejecting.")

