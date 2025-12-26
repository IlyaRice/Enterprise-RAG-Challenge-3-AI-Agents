"""
Wiki rule extraction for ERC3 benchmarks.

Extracts rules from wiki files at ingestion time, saving them as markdown files.
Uses extraction + validation loop pattern.

Usage:
    from benchmarks.erc3.ingestion import extract_all_rules
    
    # At ingestion time:
    extract_all_rules(wiki_dir)  # Creates rules/public.md and rules/authenticated.md
"""

import json
from pathlib import Path
from typing import List

from infrastructure import call_llm
from .prompts import (
    FileExtraction, ExtractedRulesResponse, ValidatorResponse,
    RespondRuleExtraction,
    prompt_public_rules_extractor, prompt_authenticated_rules_extractor, 
    prompt_respond_rules_extractor,
    prompt_extraction_validator,
)


CATEGORY_PROMPTS = {
    "public": prompt_public_rules_extractor,
    "authenticated": prompt_authenticated_rules_extractor,
    "respond": prompt_respond_rules_extractor,
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


def _format_respond_rules(extraction: 'RespondRuleExtraction') -> str:
    """Format RespondRuleExtraction as markdown with headers and metadata comments."""
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
            system_prompt=prompt_extraction_validator,
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


def extract_respond_rules(wiki_dir: str, max_attempts: int = 4) -> str:
    """Extract categorized respond tool rules from wiki files with specified tags."""
    wiki_content = _load_rule_files(wiki_dir, tags=["agent_directive", "agent_reference"])
    if not wiki_content:
        return ""
    
    print("Extracting categorized respond rules from wiki files...")
    
    original_user_message = f"Extract all relevant content from the following wiki files:\n\n{wiki_content}"
    current_user_message = original_user_message
    last_result = None
    
    for attempt in range(1, max_attempts + 1):
        print(f"  Attempt {attempt}/{max_attempts}...")
        
        # Extract with new schema
        result = call_llm(
            schema=RespondRuleExtraction,
            system_prompt=prompt_respond_rules_extractor,
            conversation=[{"role": "user", "content": current_user_message}],
            reasoning_effort="high",
        )
        parsed = result["parsed"]
        last_result = parsed
        
        total_chars = sum(len(getattr(parsed, field)) for field in ["outcome_rules", "link_rules", "message_formatting", "general_constraints"])
        print(f"    Extracted {total_chars} chars across 4 categories")
        
        # Format for validation
        formatted_output = _format_respond_rules(parsed)
        
        # Validate
        validator_message = f"""TASK:
<system_prompt>
{prompt_respond_rules_extractor}
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
            system_prompt=prompt_extraction_validator,
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
    return _format_respond_rules(last_result) if last_result else ""


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
    
    # Extract respond rules (unified for all users)
    print(f"\n{'='*50}")
    print(f"Category: respond")
    print('='*50)
    
    respond_content = extract_respond_rules(wiki_dir, max_attempts)
    if respond_content:
        file_path = rules_dir / "respond_struct.md"
        file_path.write_text(respond_content, encoding="utf-8")
        result["respond"] = str(file_path)
        print(f"  Saved to {file_path}")
    else:
        print(f"  No rules extracted for respond")
    
    return result

