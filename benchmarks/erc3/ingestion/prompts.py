"""
ERC3 ingestion prompts and schemas.

Used during wiki preparation/ingestion.

Contains:
- Rule extraction: Schemas and prompts for extracting public/authenticated/respond rules
- Wiki indexing: Schemas and prompts for indexing wiki files with metadata
- Validation: Extraction validator used by both rule extraction and wiki indexing
"""

from typing import List, Literal

from pydantic import BaseModel, Field

# ============================================================================
# RULE EXTRACTION - PUBLIC & AUTHENTICATED USER RULES
# ============================================================================

prompt_public_rules_extractor = """
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

prompt_authenticated_rules_extractor = """
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


class FileExtraction(BaseModel):
    """Extracted content from a single wiki file."""
    source_file: str = Field(..., description="Wiki file path (e.g., 'rulebook.md')")
    content: str = Field(..., description="Relevant content from this file, verbatim. Use [...] to mark skipped irrelevant sections.")


class ExtractedRulesResponse(BaseModel):
    """Response from rule extraction LLM."""
    files: List[FileExtraction] = Field(..., description="One entry per file that contains relevant rules")



# ============================================================================
# RESPONSE RULE EXTRACTION
# ============================================================================

prompt_respond_rules_extractor = """
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


class RespondRuleExtraction(BaseModel):
    """Categorized rule extraction for /respond tool behavior."""
    outcome_rules: str = Field(..., description="Rules for when to use each outcome type")
    link_rules: str = Field(..., description="Rules for each link kind")
    message_formatting: str = Field(..., description="Message content rules")
    general_constraints: str = Field(..., description="Cross-cutting rules")



# ============================================================================
# VALIDATOR
# ============================================================================

prompt_extraction_validator = """
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


class ValidatorResponse(BaseModel):
    """Response from validation LLM."""
    analysis: str = Field(..., description="Brief analysis of the work")
    is_valid: bool = Field(..., description="Pass or fail")
    rejection_message: str = Field(default="", description="What's wrong + what to fix")



# ============================================================================
# WIKI INDEXING
# ============================================================================
# Indexes wiki files with metadata (category, summary, has_rules) and extracts company info.

prompt_wiki_indexer = """
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

class CompanyInfo(BaseModel):
    """Company basic information."""
    name: str = Field(..., description="Official company name")
    locations: List[str] = Field(..., description="Office cities only")
    executives: List[str] = Field(..., description="Leadership names with roles")

class IndexedFile(BaseModel):
    """Metadata for a single wiki file."""
    filename: str = Field(..., description="Wiki filename (e.g., 'rulebook.md')")
    category: Literal["agent_directive", "agent_reference", "background_context", "human_flavor", "conditional_entity"] = Field(
        ..., 
        description="Agent-centric utility classification"
    )
    summary: str = Field(..., description="1-3 sentence inventory of file contents following template: 'Contains: [topics]. Includes: [examples].'")
    has_rules: bool = Field(..., description="True if file contains actionable rules/policies that constrain agent behavior")


class WikiIndexResponse(BaseModel):
    """Response from wiki indexer LLM."""
    files: List[IndexedFile] = Field(..., description="Metadata for each wiki file")
    company: CompanyInfo = Field(..., description="Company basic info extracted from wiki files")

