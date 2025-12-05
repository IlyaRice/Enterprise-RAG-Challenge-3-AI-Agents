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
    extraction_prompt_public, extraction_prompt_authenticated, validator_prompt,
)


CATEGORY_PROMPTS = {
    "public": extraction_prompt_public,
    "authenticated": extraction_prompt_authenticated,
}


def _load_rule_files(wiki_dir: str) -> str:
    """Load and concatenate all rule files with <wiki:path> tags."""
    wiki_path = Path(wiki_dir)
    manifest_path = wiki_path / "manifest.json"
    
    if not manifest_path.exists():
        return ""
    
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rule_files = [f for f in manifest.get("files", []) if f.get("has_rules", False)]
    
    if not rule_files:
        return ""
    
    parts = []
    for f in rule_files:
        file_path = wiki_path / f["saved_as"]
        if file_path.exists():
            content = file_path.read_text(encoding="utf-8")
            parts.append(f"<wiki:{f['path']}>\n{content}\n</wiki:{f['path']}>")
    
    return "\n\n".join(parts)


def _format_result(files: List[FileExtraction]) -> str:
    """Format extraction result with <wiki:path> tags."""
    parts = []
    for f in files:
        parts.append(f"<wiki:{f.source_file}>\n{f.content}\n</wiki:{f.source_file}>")
    return "\n\n".join(parts)


def _extract_with_validation(wiki_content: str, extraction_prompt: str, max_attempts: int = 2) -> List[FileExtraction]:
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


def extract_rules_for_category(wiki_dir: str, category: str, max_attempts: int = 2) -> str:
    """Extract rules for a user category (public/authenticated)."""
    if category not in CATEGORY_PROMPTS:
        raise ValueError(f"Unknown category: {category}. Use 'public' or 'authenticated'.")
    
    wiki_content = _load_rule_files(wiki_dir)
    if not wiki_content:
        return ""
    
    print(f"Extracting {category} rules...")
    files = _extract_with_validation(wiki_content, CATEGORY_PROMPTS[category], max_attempts)
    
    return _format_result(files) if files else ""


def extract_all_rules(wiki_dir: str, max_attempts: int = 2) -> dict:
    """Extract rules for all categories and save to rules/ folder."""
    wiki_path = Path(wiki_dir)
    rules_dir = wiki_path / "rules"
    rules_dir.mkdir(exist_ok=True)
    
    result = {}
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
    
    return result


def load_rules(wiki_dir: str, category: str) -> str | None:
    """Load pre-extracted rules at runtime."""
    rules_path = Path(wiki_dir) / "rules" / f"{category}.md"
    return rules_path.read_text(encoding="utf-8") if rules_path.exists() else None


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
