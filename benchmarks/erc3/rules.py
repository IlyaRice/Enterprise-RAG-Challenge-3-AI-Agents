"""
Wiki rule extraction for ERC3 benchmarks.

Extracts rules from wiki files at ingestion time, saving them as markdown files.
Uses extraction + validation loop pattern.

Usage:
    from benchmarks.erc3.rules import extract_all_rules, load_rules
    
    # At ingestion time:
    extract_all_rules(wiki_dir)  # Creates rules/public.md and rules/authenticated.md
    
    # At runtime:
    rules = load_rules(wiki_dir, "public")  # Returns markdown string or None
"""

import json
from pathlib import Path
from typing import List

from infrastructure import call_llm
from .prompts import (
    FileExtraction, ExtractedRulesResponse, ValidatorResponse,
    ResponseRuleExtraction, AccessControlRuleExtraction, AgentGlossary,
    extraction_prompt_public, extraction_prompt_authenticated, 
    extraction_prompt_response, extraction_prompt_access_control,
    extraction_prompt_glossary, validator_prompt,
)


CATEGORY_PROMPTS = {
    "public": extraction_prompt_public,
    "authenticated": extraction_prompt_authenticated,
    "response": extraction_prompt_response,
    "access_control": extraction_prompt_access_control,
}


def _load_rule_files(wiki_dir: str, tags: List[str]) -> str:
    """Load and concatenate rule files with <wiki:path> tags based on category tags."""
    wiki_path = Path(wiki_dir)
    wiki_meta_path = wiki_path / "wiki_meta.json"
    
    if not wiki_meta_path.exists():
        return ""
    
    wiki_meta = json.loads(wiki_meta_path.read_text(encoding="utf-8"))
    
    # Filter files by category matching any of the provided tags
    files_to_load = [
        f for f in wiki_meta.get("files", []) 
        if f.get("category") in tags
    ]
    
    if not files_to_load:
        return ""
    
    parts = []
    for f in files_to_load:
        file_path = wiki_path / f["saved_as"]
        if file_path.exists():
            content = file_path.read_text(encoding="utf-8")
            parts.append(f"<kind=wiki id={f['path']}>\n{content}\n</kind=wiki id={f['path']}>")
    
    return "\n\n".join(parts)


def _format_result(files: List[FileExtraction]) -> str:
    """Format extraction result with wiki tags."""
    parts = []
    for f in files:
        parts.append(f"<kind=wiki id={f.source_file}>\n{f.content}\n</kind=wiki id={f.source_file}>")
    return "\n\n".join(parts)


def _format_response_rules(extraction: 'ResponseRuleExtraction') -> str:
    """Format ResponseRuleExtraction as markdown with headers and metadata comments."""
    parts = []
    
    # Outcome Rules
    parts.append("## Outcome Rules")
    if extraction.outcome_rules.strip():
        parts.append(extraction.outcome_rules.strip())
    else:
        parts.append("(No outcome rules were found in the wiki files)")
    parts.append("")
    
    # Link Rules
    parts.append("## Link Rules")
    if extraction.link_rules.strip():
        parts.append(extraction.link_rules.strip())
    else:
        parts.append("(No link rules were found in the wiki files)")
    parts.append("")
    
    # Message Formatting
    parts.append("## Message Formatting")
    if extraction.message_formatting.strip():
        parts.append(extraction.message_formatting.strip())
    else:
        parts.append("(No message formatting rules were found in the wiki files)")
    parts.append("")
    
    # General Constraints
    parts.append("## General Constraints")
    if extraction.general_constraints.strip():
        parts.append(extraction.general_constraints.strip())
    else:
        parts.append("(No general constraints were found in the wiki files)")
    
    return "\n".join(parts)


def _format_access_control_rules(extraction: 'AccessControlRuleExtraction') -> str:
    """Format AccessControlRuleExtraction as markdown with headers."""
    parts = []
    
    parts.append("## Access Level Rules")
    parts.append(extraction.access_level_rules.strip() if extraction.access_level_rules.strip() else "(No access level rules found)")
    parts.append("")
    
    parts.append("## Action Permission Matrix")
    parts.append(extraction.action_permission_matrix.strip() if extraction.action_permission_matrix.strip() else "(No action permission matrix found)")
    parts.append("")
    
    parts.append("## Role-Based Modifiers")
    parts.append(extraction.role_based_modifiers.strip() if extraction.role_based_modifiers.strip() else "(No role-based modifiers found)")
    parts.append("")
    
    parts.append("## Project-Based Modifiers")
    parts.append(extraction.project_based_modifiers.strip() if extraction.project_based_modifiers.strip() else "(No project-based modifiers found)")
    parts.append("")
    
    parts.append("## Relationship Modifiers")
    parts.append(extraction.relationship_modifiers.strip() if extraction.relationship_modifiers.strip() else "(No relationship modifiers found)")
    parts.append("")
    
    parts.append("## Special Exceptions")
    parts.append(extraction.special_exceptions.strip() if extraction.special_exceptions.strip() else "(No special exceptions found)")
    parts.append("")
    
    parts.append("## Contextual Factors")
    parts.append(extraction.contextual_factors.strip() if extraction.contextual_factors.strip() else "(No contextual factors found)")
    
    return "\n".join(parts)


def _extract_with_validation(wiki_content: str, extraction_prompt: str, max_attempts: int = 4) -> List[FileExtraction]:
    """Core extraction + validation loop."""
    original_user_message = f"Extract all relevant content from the following wiki files:\n\n{wiki_content}"
    current_user_message = original_user_message
    last_result = None
    
    for attempt in range(1, max_attempts + 1):
        print(f"  Attempt {attempt}/{max_attempts}...")
        
        # Extract
        w_result = call_llm(
            schema=ExtractedRulesResponse,
            system_prompt=extraction_prompt,
            conversation=[{"role": "user", "content": current_user_message}],
            reasoning_effort="high",
        )
        w_parsed = w_result["parsed"]
        last_result = w_parsed.files
        
        total_chars = sum(len(f.content) for f in w_parsed.files)
        print(f"    Extracted from {len(w_parsed.files)} files, {total_chars} chars")
        
        formatted_output = _format_result(w_parsed.files)
        
        # Validate
        validator_message = f"""TASK:
<system_prompt>
{extraction_prompt}
</system_prompt>

<user_prompt>
{original_user_message}
</user_prompt>

<result>
{formatted_output}
</result>

Very carefully assess whether this result correctly fulfills the task."""

        v_result = call_llm(
            schema=ValidatorResponse,
            system_prompt=validator_prompt,
            conversation=[{"role": "user", "content": validator_message}],
            reasoning_effort="high",
        )
        v_parsed = v_result["parsed"]
        print(f"    Validator: {'PASS' if v_parsed.is_valid else 'REJECT'}")
        
        if v_parsed.is_valid:
            return w_parsed.files
        
        # Prepare retry with feedback
        if attempt < max_attempts:
            print(f"    Rejection: {v_parsed.rejection_message}...")
            current_user_message = f"""{original_user_message}

RETRY: Previous attempt was rejected.

Previous output:
{formatted_output}

Rejection feedback: {v_parsed.rejection_message}

Address this feedback and try again."""
    
    print("    Max attempts reached, returning last result")
    return last_result


def extract_rules_for_category(wiki_dir: str, category: str, max_attempts: int = 4) -> str:
    """Extract rules for a user category (public/authenticated)."""
    if category not in CATEGORY_PROMPTS:
        raise ValueError(f"Unknown category: {category}. Use 'public' or 'authenticated'.")
    
    wiki_content = _load_rule_files(wiki_dir, tags=["agent_directive", "agent_reference"])
    if not wiki_content:
        return ""
    
    print(f"Extracting {category} rules...")
    files = _extract_with_validation(wiki_content, CATEGORY_PROMPTS[category], max_attempts)
    
    return _format_result(files) if files else ""


def extract_all_rules(wiki_dir: str, max_attempts: int = 4) -> dict:
    """Extract rules for all categories and save to rules/ folder."""
    wiki_path = Path(wiki_dir)
    rules_dir = wiki_path / "rules"
    rules_dir.mkdir(exist_ok=True)
    
    result = {}
    
    # Extract public and authenticated rules
    for category in ["public", "authenticated"]:
        print(f"\n{'='*50}")
        print(f"Category: {category}")
        print('='*50)
        
        content = extract_rules_for_category(wiki_dir, category, max_attempts)
        if content:
            file_path = rules_dir / f"{category}.md"
            file_path.write_text(content, encoding="utf-8")
            result[category] = str(file_path)
            print(f"  Saved to {file_path}")
        else:
            print(f"  No rules extracted for {category}")
    
    # Extract response rules (uses different extraction function)
    print(f"\n{'='*50}")
    print(f"Category: response")
    print('='*50)
    
    response_content = extract_response_formatting_rules(wiki_dir, max_attempts)
    if response_content:
        file_path = rules_dir / "response_struct.md"
        file_path.write_text(response_content, encoding="utf-8")
        result["response"] = str(file_path)
        print(f"  Saved to {file_path}")
    else:
        print(f"  No rules extracted for response")
    
    # Extract access control rules
    print(f"\n{'='*50}")
    print(f"Category: access_control")
    print('='*50)
    
    access_control_content = extract_access_control_rules(wiki_dir, max_attempts)
    if access_control_content:
        file_path = rules_dir / "access_control.md"
        file_path.write_text(access_control_content, encoding="utf-8")
        result["access_control"] = str(file_path)
        print(f"  Saved to {file_path}")
    else:
        print(f"  No rules extracted for access_control")
    
    return result


def load_rules(wiki_dir: str, category: str) -> str | None:
    """Load pre-extracted rules at runtime."""
    rules_path = Path(wiki_dir) / "rules" / f"{category}.md"
    return rules_path.read_text(encoding="utf-8") if rules_path.exists() else None


def extract_response_formatting_rules(wiki_dir: str, max_attempts: int = 4) -> str:
    """Extract categorized response rules from wiki files with specified tags."""
    wiki_content = _load_rule_files(wiki_dir, tags=["agent_directive", "agent_reference"])
    if not wiki_content:
        return ""
    
    print("Extracting categorized response rules from wiki files...")
    
    original_user_message = f"Extract all relevant content from the following wiki files:\n\n{wiki_content}"
    current_user_message = original_user_message
    last_result = None
    
    for attempt in range(1, max_attempts + 1):
        print(f"  Attempt {attempt}/{max_attempts}...")
        
        # Extract with new schema
        result = call_llm(
            schema=ResponseRuleExtraction,
            system_prompt=extraction_prompt_response,
            conversation=[{"role": "user", "content": current_user_message}],
            reasoning_effort="high",
        )
        parsed = result["parsed"]
        last_result = parsed
        
        total_chars = sum(len(getattr(parsed, field)) for field in ["outcome_rules", "link_rules", "message_formatting", "general_constraints"])
        print(f"    Extracted {total_chars} chars across 4 categories")
        
        # Format for validation
        formatted_output = _format_response_rules(parsed)
        
        # Validate
        validator_message = f"""TASK:
<system_prompt>
{extraction_prompt_response}
</system_prompt>

<user_prompt>
{original_user_message}
</user_prompt>

<result>
{formatted_output}
</result>

Very carefully assess whether this result correctly fulfills the task."""

        v_result = call_llm(
            schema=ValidatorResponse,
            system_prompt=validator_prompt,
            conversation=[{"role": "user", "content": validator_message}],
            reasoning_effort="high",
        )
        v_parsed = v_result["parsed"]
        print(f"    Validator: {'PASS' if v_parsed.is_valid else 'REJECT'}")
        
        if v_parsed.is_valid:
            return formatted_output
        
        # Prepare retry message
        print(f"    Rejection: {v_parsed.rejection_message}")
        current_user_message = f"""ORIGINAL TASK:
{original_user_message}

Previous output:
{formatted_output}

Rejection feedback: {v_parsed.rejection_message}

Address this feedback and try again."""
    
    print("    Max attempts reached, returning last result")
    return _format_response_rules(last_result) if last_result else ""


def extract_access_control_rules(wiki_dir: str, max_attempts: int = 4) -> str:
    """Extract categorized access control rules from wiki files with specified tags."""
    wiki_content = _load_rule_files(wiki_dir, tags=["agent_directive", "agent_reference"])
    if not wiki_content:
        return ""
    
    print("Extracting categorized access control rules from wiki files...")
    
    original_user_message = f"Extract all relevant content from the following wiki files:\n\n{wiki_content}"
    current_user_message = original_user_message
    last_result = None
    
    for attempt in range(1, max_attempts + 1):
        print(f"  Attempt {attempt}/{max_attempts}...")
        
        # Extract with access control schema
        result = call_llm(
            schema=AccessControlRuleExtraction,
            system_prompt=extraction_prompt_access_control,
            conversation=[{"role": "user", "content": current_user_message}],
            reasoning_effort="high",
        )
        parsed = result["parsed"]
        last_result = parsed
        
        total_chars = sum(len(getattr(parsed, field)) for field in [
            "access_level_rules", "action_permission_matrix", "role_based_modifiers",
            "project_based_modifiers", "relationship_modifiers", "special_exceptions", "contextual_factors"
        ])
        print(f"    Extracted {total_chars} chars across 7 categories")
        
        # Format for validation
        formatted_output = _format_access_control_rules(parsed)
        
        # Validate
        validator_message = f"""TASK:
<system_prompt>
{extraction_prompt_access_control}
</system_prompt>

<user_prompt>
{original_user_message}
</user_prompt>

<result>
{formatted_output}
</result>

Very carefully assess whether this result correctly fulfills the task."""

        v_result = call_llm(
            schema=ValidatorResponse,
            system_prompt=validator_prompt,
            conversation=[{"role": "user", "content": validator_message}],
            reasoning_effort="high",
        )
        v_parsed = v_result["parsed"]
        print(f"    Validator: {'PASS' if v_parsed.is_valid else 'REJECT'}")
        
        if v_parsed.is_valid:
            return formatted_output
        
        # Prepare retry message
        print(f"    Rejection: {v_parsed.rejection_message}")
        current_user_message = f"""ORIGINAL TASK:
{original_user_message}

Previous output:
{formatted_output}

Rejection feedback: {v_parsed.rejection_message}

Address this feedback and try again."""
    
    print("    Max attempts reached, returning last result")
    return _format_access_control_rules(last_result) if last_result else ""


def load_rules_for_session(whoami: dict) -> str:
    """
    Load pre-extracted rules based on session context.
    
    Uses wiki_sha1 to locate wiki directory and is_public to select category.
    Returns empty string if rules not found or whoami failed.
    
    Args:
        whoami: Result from whoami_raw() containing wiki_sha1 and is_public
    
    Returns:
        Rules content as string, or empty string if not available
    """
    # Handle whoami errors
    if whoami.get("error"):
        return ""
    
    wiki_sha1 = whoami.get("wiki_sha1", "")
    if not wiki_sha1:
        return ""
    
    wiki_dir = str(Path(__file__).parent / "wiki_data" / wiki_sha1[:8])
    category = "public" if whoami.get("is_public", True) else "authenticated"
    
    return load_rules(wiki_dir, category) or ""


def load_access_control_rules(whoami: dict) -> str:
    """Load pre-extracted access control rules for access evaluation."""
    # Handle whoami errors
    if whoami.get("error"):
        return ""
    
    wiki_sha1 = whoami.get("wiki_sha1", "")
    if not wiki_sha1:
        return ""
    
    wiki_dir = Path(__file__).parent / "wiki_data" / wiki_sha1[:8]
    rules_path = wiki_dir / "rules" / "access_control_.md"
    
    if rules_path.exists():
        return rules_path.read_text(encoding="utf-8")
    return ""


def extract_agent_glossary(wiki_dir: str, max_attempts: int = 4) -> Path:
    """Extract operational vocabulary. Saves to rules/glossary.json."""
    wiki_content = _load_rule_files(wiki_dir, tags=["agent_directive", "agent_reference", "conditional_entity", "background_context"])
    if not wiki_content:
        return Path(wiki_dir) / "rules" / "glossary.json"
    
    print("Extracting agent glossary...")
    
    original_user_message = f"Extract operational vocabulary from the following wiki files:\n\n{wiki_content}"
    current_user_message = original_user_message
    last_result = None
    
    for attempt in range(1, max_attempts + 1):
        print(f"  Attempt {attempt}/{max_attempts}...")
        
        # Extract
        result = call_llm(
            schema=AgentGlossary,
            system_prompt=extraction_prompt_glossary,
            conversation=[{"role": "user", "content": current_user_message}],
            reasoning_effort="high",
        )
        parsed = result["parsed"]
        last_result = parsed
        
        print(f"    Extracted glossary with {len(parsed.skills_and_wills.items)} skills/wills")
        
        # Format for validation
        formatted_output = json.dumps(parsed.model_dump(), indent=2, ensure_ascii=False)
        
        # Validate
        validator_message = f"""TASK:
<system_prompt>
{extraction_prompt_glossary}
</system_prompt>

<user_prompt>
{original_user_message}
</user_prompt>

<result>
{formatted_output}
</result>

Very carefully assess whether this result correctly fulfills the task."""

        v_result = call_llm(
            schema=ValidatorResponse,
            system_prompt=validator_prompt,
            conversation=[{"role": "user", "content": validator_message}],
            reasoning_effort="high",
        )
        v_parsed = v_result["parsed"]
        print(f"    Validator: {'PASS' if v_parsed.is_valid else 'REJECT'}")
        
        if v_parsed.is_valid:
            break
        
        # Prepare retry message
        if attempt < max_attempts:
            print(f"    Rejection: {v_parsed.rejection_message}")
            current_user_message = f"""ORIGINAL TASK:
{original_user_message}

Previous output:
{formatted_output}

Rejection feedback: {v_parsed.rejection_message}

Address this feedback and try again."""
    
    print("    Max attempts reached, using last result" if attempt == max_attempts else "    Validation passed")
    
    # Save to rules/glossary.json
    wiki_path = Path(wiki_dir)
    rules_dir = wiki_path / "rules"
    rules_dir.mkdir(exist_ok=True)
    
    glossary_path = rules_dir / "glossary.json"
    glossary_path.write_text(
        json.dumps(last_result.model_dump(), indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    
    return glossary_path
