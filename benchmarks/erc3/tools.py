"""
ERC3 benchmark SDK tool execution and context gathering.

Contains:
- Pagination: _paginate (generic)
- Directory formatters: format_employees_list, format_customers_list, format_projects_list
- Context gathering: whoami_raw, format_whoami, employee_raw, format_employee
- Wiki search: search_wiki, format_wiki_search (BM25 + fuzzy hybrid)
- Context blocks: collect_context_blocks, build_orchestrator_context
- SDK execution: execute_single_call, execute_erc3_tools

Uses shared execute_sdk_call from infrastructure for core SDK dispatch.
"""

import json
import re
import yaml
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from rank_bm25 import BM25Okapi
from rapidfuzz import fuzz

from erc3.erc3.dtos import (
    Req_WhoAmI, Req_GetEmployee, Req_GetCustomer, Req_GetProject, ProjectTeamFilter,
    Req_ListEmployees, Req_SearchEmployees, Req_ListCustomers, Req_SearchCustomers,
    Req_ListProjects, Req_SearchProjects, Req_SearchTimeEntries, Req_LogTimeEntry,
)
from infrastructure import execute_sdk_call, dispatch_with_retry
# Import wrappers (LLM-facing, no limit/offset) - shadowing is OK, they're used in different contexts
import benchmarks.erc3.prompts as erc3_prompts


# ============================================================================
# DATA STRUCTURES FOR CONTEXT BLOCKS
# ============================================================================

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class ContextBlock:
    """
    Single block of collected context.
    
    Attributes:
        name: Block identifier (e.g., 'project:proj_xxx' or '[no_user_projects]')
        summary: One-line description for block list
        content: Full formatted content with kind:id tags
    """
    name: str
    summary: str
    content: str


@dataclass
class CollectedContext:
    """
    All collected context with structured access.
    
    Attributes:
        blocks: All selectable blocks keyed by name
        session_content: Always-included session block content
        employee_content: Always-included employee block content (None for public)
    """
    blocks: Dict[str, ContextBlock] = field(default_factory=dict)
    session_content: str = ""
    employee_content: str | None = None
    
    def get_content(self, selected: List[str]) -> str:
        """Get concatenated content of selected blocks."""
        parts = []
        for name in selected:
            if name in self.blocks:
                parts.append(self.blocks[name].content)
        return "\n\n".join(parts)
    
    def get_all_block_names(self) -> List[str]:
        """Get list of all available block names."""
        return list(self.blocks.keys())


# ============================================================================
# YAML FORMATTING HELPERS
# ============================================================================

def _format_entity(data: dict, tag: str) -> str:
    """Format entity as YAML wrapped in XML tag."""
    clean = {k: v for k, v in data.items() if v is not None}
    yaml_str = yaml.dump(clean, default_flow_style=False, sort_keys=False, allow_unicode=True)
    return f"<{tag}>\n{yaml_str}</{tag}>"


# ============================================================================
# WIKI SEARCH (BM25 + Fuzzy Hybrid)
# ============================================================================

def _tokenize(text: str) -> list[str]:
    """Tokenize text: lowercase, split on non-alphanumeric."""
    return re.findall(r'\w+', text.lower())


def _extract_snippets(content: str, query: str, context_lines: int = 1) -> list[dict]:
    """Extract all snippets where query matches (whole-word + fuzzy)."""
    lines = content.split('\n')
    query_tokens = _tokenize(query)
    query_lower = query.lower()
    
    matches, used = [], set()
    for i, line in enumerate(lines):
        if i in used:
            continue
        line_tokens = set(_tokenize(line))
        
        # Whole-word token match (score = 100 per token)
        token_hits = sum(1 for t in query_tokens if t in line_tokens)
        if token_hits > 0:
            score = token_hits * 100
        else:
            # Fuzzy fallback
            score = fuzz.partial_ratio(query_lower, line.lower())
            if score < 70:
                continue
        
        if score >= 70:
            start, end = max(0, i - context_lines), min(len(lines), i + context_lines + 1)
            for j in range(start, end):
                used.add(j)
            snippet_lines = lines[start:end]
            offset = i - start
            if 0 <= offset < len(snippet_lines):
                snippet_lines[offset] = ">>> " + snippet_lines[offset]
            matches.append({
                "line": i + 1,
                "score": score,
                "text": '\n'.join(snippet_lines)[:300],
            })
    return matches


def search_wiki(wiki_dir: str, query: str, bm25_threshold: float = 1.0, fuzzy_threshold: int = 70) -> dict:
    """
    Search wiki files using BM25 + fuzzy hybrid.
    
    Args:
        wiki_dir: Path to wiki directory
        query: Search query (name, keywords, etc.)
        bm25_threshold: Include if BM25 > this (default 1.0)
        fuzzy_threshold: Include if fuzzy > this (default 70)
    
    Returns:
        dict with 'results' list and 'warning' if >10 files match
    """
    # Load wiki files
    wiki_path = Path(wiki_dir)
    files = []
    for md_file in wiki_path.rglob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8")
            files.append({
                "path": str(md_file.relative_to(wiki_path)),
                "filename": md_file.name,
                "content": content,
            })
        except Exception:
            continue
    
    if not files:
        return {"results": [], "error": "no_wiki_files"}
    
    # Build BM25 index
    tokenized = [_tokenize(f["content"]) for f in files]
    bm25 = BM25Okapi(tokenized)
    bm25_scores = bm25.get_scores(_tokenize(query))
    
    # Search with thresholds
    results = []
    for idx, wiki_file in enumerate(files):
        snippets = _extract_snippets(wiki_file["content"], query)
        fuzzy_score = max((s["score"] for s in snippets), default=0)
        
        if bm25_scores[idx] > bm25_threshold or fuzzy_score > fuzzy_threshold:
            results.append({
                "filename": wiki_file["filename"],
                "path": wiki_file["path"],
                "bm25": round(bm25_scores[idx], 2),
                "fuzzy": fuzzy_score,
                "snippets": snippets,
            })
    
    # Sort by combined score
    results.sort(key=lambda x: (x["bm25"] * 6.67) + x["fuzzy"], reverse=True)
    
    # Dev warning
    if len(results) > 10:
        print(f"⚠️  wiki search '{query}': {len(results)} files matched (>10)")
    
    return {"results": results}


def format_wiki_search(response: dict, query: str) -> str:
    """Format wiki search results for LLM context."""
    if response.get("error"):
        return f'<wiki_search query="{query}" status="error">{response["error"]}</wiki_search>'
    
    results = response.get("results", [])
    if not results:
        return f'<wiki_search query="{query}" count="0" />'
    
    lines = [f'<wiki_search query="{query}" count="{len(results)}">']
    
    for r in results:
        lines.append(f'\n<wiki_file name="{r["filename"]}" bm25="{r["bm25"]}" fuzzy="{r["fuzzy"]}">')
        for s in r["snippets"]:
            lines.append(f'  [line {s["line"]}]')
            lines.append(f'  {s["text"]}')
        lines.append('</wiki_file>')
    
    lines.append('\n</wiki_search>')
    return '\n'.join(lines)


# ============================================================================
# PAGINATION HELPERS
# ============================================================================

# Constants for pagination
_DEFAULT_LIMIT = 5
_FALLBACK_LIMITS = [4, 3, 2, 1]  # Limits to try if default fails


def _fetch_page(client, request_factory, result_key: str, offset: int, limit: int) -> dict:
    """
    Fetch a single page of results.
    
    Returns:
        dict with:
        - "items": List of item dicts
        - "next_offset": Next offset or None if done
        - "error": Error message or None
    """
    try:
        response = dispatch_with_retry(client, request_factory(offset=offset, limit=limit))
        items_raw = getattr(response, result_key, None)
        
        if items_raw is None:
            items = []
        else:
            items = []
            for item in items_raw:
                if hasattr(item, 'model_dump'):
                    items.append(item.model_dump())
                else:
                    items.append(item)
        
        return {
            "items": items,
            "next_offset": response.next_offset,
            "error": None,
        }
    except Exception as e:
        return {
            "items": [],
            "next_offset": None,
            "error": str(e),
        }


def _paginate(client, request_factory, result_key: str) -> dict:
    """
    Generic pagination helper for ERC3 list endpoints.
    
    Simple sequential algorithm:
    1. Fetch first page with limit=5
    2. If fails, try smaller limits (4, 3, 2, 1)
    3. Continue fetching until next_offset is None
    
    Args:
        client: SDK client
        request_factory: Request class (e.g., Req_ListEmployees)
        result_key: Attribute name on response containing items (e.g., "employees")
    
    Returns:
        dict with:
        - "items": List of item dicts
        - "complete": True if all pages fetched successfully
        - "errors": List of error messages (empty if complete)
        - "pages_fetched": Number of successful page fetches
    """
    all_items = []
    pages_fetched = 0
    errors = []
    
    # Try to find a working limit
    limit = _DEFAULT_LIMIT
    first_page = _fetch_page(client, request_factory, result_key, 0, limit)
    
    if first_page["error"]:
        # Try fallback limits
        for fallback_limit in _FALLBACK_LIMITS:
            first_page = _fetch_page(client, request_factory, result_key, 0, fallback_limit)
            if not first_page["error"]:
                limit = fallback_limit
                break
        
        # If all limits failed
        if first_page["error"]:
            return {
                "items": [],
                "complete": False,
                "errors": ["Unable to access data. System may be temporarily unavailable."],
                "pages_fetched": 0,
            }
    
    # Collect first page results
    all_items.extend(first_page["items"])
    pages_fetched = 1
    next_offset = first_page["next_offset"]
    
    # Fetch remaining pages
    while next_offset is not None and next_offset > 0:
        page = _fetch_page(client, request_factory, result_key, next_offset, limit)
        
        if page["error"]:
            errors.append(f"Page at offset {next_offset}: {page['error']}")
            break
        
        all_items.extend(page["items"])
        pages_fetched += 1
        next_offset = page["next_offset"]
    
    # Warn if unexpectedly large result set
    if len(all_items) > 50:
        print(f"⚠ WARNING: Pagination collected {len(all_items)} items (>50). Consider if this is expected.")
    
    return {
        "items": all_items,
        "complete": len(errors) == 0,
        "errors": errors,
        "pages_fetched": pages_fetched,
    }


def format_employees_list(response: dict) -> str:
    """
    Format employees list response into LLM context block.
    
    Args:
        response: Result from employees_list_raw()
    
    Returns:
        Formatted string with employee directory
    """
    items = response.get("items", [])
    complete = response.get("complete", False)
    errors = response.get("errors", [])
    
    if not items and errors:
        return f'''<employees_directory status="error">
Failed to retrieve employee directory: {errors[0]}
</employees_directory>'''
    
    if not items:
        return '''<employees_directory status="empty">
No employees found in directory.
</employees_directory>'''
    
    # Build compact employee list - name with id reference
    lines = [f'<employees_directory count="{len(items)}">']
    
    for emp in items:
        emp_id = emp.get("id", "unknown")
        name = emp.get("name", "unknown")
        lines.append(f"[kind=employee id={emp_id}] {name}")
    
    if not complete:
        lines.append(f"\n  [INCOMPLETE: {errors[0] if errors else 'Unknown error'}]")
    
    lines.append("</employees_directory>")
    
    return "\n".join(lines)


# ============================================================================
# CONTEXT GATHERING: CUSTOMERS LIST
# ============================================================================

def format_customers_list(response: dict) -> str:
    """
    Format customers list response into LLM context block.
    
    Args:
        response: Result from customers_list_raw()
    
    Returns:
        Formatted string with customer directory
    """
    items = response.get("items", [])
    complete = response.get("complete", False)
    errors = response.get("errors", [])
    
    if not items and errors:
        return f'''<customers_directory status="error">
Failed to retrieve customer directory: {errors[0]}
</customers_directory>'''
    
    if not items:
        return '''<customers_directory status="empty">
No customers found in directory.
</customers_directory>'''
    
    # Build compact customer list - name with id reference
    lines = [f'<customers_directory count="{len(items)}">']
    
    for cust in items:
        cust_id = cust.get("id", "unknown")
        name = cust.get("name", "unknown")
        lines.append(f"[kind=customer id={cust_id}] {name}")
    
    if not complete:
        lines.append(f"\n  [INCOMPLETE: {errors[0] if errors else 'Unknown error'}]")
    
    lines.append("</customers_directory>")
    
    return "\n".join(lines)


# ============================================================================
# CONTEXT GATHERING: PROJECTS LIST
# ============================================================================

def format_projects_list(response: dict) -> str:
    """
    Format projects list response into LLM context block.
    
    Args:
        response: Result from projects_list_raw()
    
    Returns:
        Formatted string with projects directory
    """
    items = response.get("items", [])
    complete = response.get("complete", False)
    errors = response.get("errors", [])
    
    if not items and errors:
        return f'''<projects_directory status="error">
Failed to retrieve projects directory: {errors[0]}
</projects_directory>'''
    
    if not items:
        return '''<projects_directory status="empty">
No projects found in directory.
</projects_directory>'''
    
    # Build compact projects list - name, customer, id reference
    lines = [f'<projects_directory count="{len(items)}">']
    
    for proj in items:
        proj_id = proj.get("id", "unknown")
        name = proj.get("name", "unknown")
        lines.append(f"[kind=project id={proj_id}] {name}")
    
    if not complete:
        lines.append(f"\n  [INCOMPLETE: {errors[0] if errors else 'Unknown error'}]")
    
    lines.append("</projects_directory>")
    
    return "\n".join(lines)


# ============================================================================
# USER-SPECIFIC: USER'S PROJECTS
# ============================================================================

def user_projects_raw(client, whoami: dict) -> dict:
    """
    Get all projects where the current user is a team member (FULL details).
    
    Step 1: Search for project IDs where user is team member
    Step 2: For each project, call /projects/get to get full ProjectDetail
    """
    current_user = whoami.get("current_user")
    
    # Skip for public users
    if not current_user or whoami.get("is_public"):
        return {"items": [], "complete": True, "errors": [], "skipped": True}
    
    # Step 1: Search for project IDs
    team_filter = ProjectTeamFilter(employee_id=current_user)
    def request_factory(offset: int, limit: int):
        return Req_SearchProjects(team=team_filter, include_archived=True, offset=offset, limit=limit)
    
    search_result = _paginate(client, request_factory, "projects")
    if not search_result.get("complete"):
        return {"items": [], "complete": False, "errors": search_result.get("errors", []), "skipped": False}
    
    # Step 2: Get full details for each project
    projects = []
    errors = []
    for proj_brief in search_result.get("items", []):
        proj_id = proj_brief.get("id")
        if not proj_id:
            continue
        try:
            response = dispatch_with_retry(client, Req_GetProject(id=proj_id))
            if response.found and response.project:
                projects.append(response.project.model_dump())
        except Exception as e:
            errors.append(f"Failed to get project {proj_id}: {str(e)}")
    
    return {"items": projects, "complete": len(errors) == 0, "errors": errors, "skipped": False}


# ============================================================================
# USER-SPECIFIC: USER'S CUSTOMERS (merged: projects + account_manager)
# ============================================================================

def user_customers_raw(client, whoami: dict) -> dict:
    """
    Get ALL customers relevant to current user:
    - Customers from projects user is a team member on
    - Customers where user is account_manager
    
    Deduplicates by customer ID before fetching details.
    
    Args:
        client: SDK client
        whoami: Result from whoami_raw() containing current_user
    
    Returns:
        dict with:
        - "items": List of customer dicts (deduplicated)
        - "complete": True if all fetches succeeded
        - "errors": List of error messages
        - "skipped": True if public user
    """
    current_user = whoami.get("current_user")
    
    # Skip for public users
    if not current_user or whoami.get("is_public"):
        return {"items": [], "complete": True, "errors": [], "skipped": True}
    
    customer_ids = set()
    errors = []
    
    # Source 1: Customers from user's projects
    projects_result = user_projects_raw(client, whoami)
    if projects_result.get("complete"):
        for proj in projects_result.get("items", []):
            if cust_id := proj.get("customer"):
                customer_ids.add(cust_id)
    elif not projects_result.get("skipped"):
        errors.extend(projects_result.get("errors", ["Failed to get projects"]))
    
    # Source 2: Customers where user is account_manager
    def am_request_factory(offset: int, limit: int):
        return Req_SearchCustomers(account_managers=[current_user], offset=offset, limit=limit)
    
    am_result = _paginate(client, am_request_factory, "companies")
    if am_result.get("complete"):
        for cust in am_result.get("items", []):
            if cust_id := cust.get("id"):
                customer_ids.add(cust_id)
    else:
        errors.extend(am_result.get("errors", ["Failed to search managed customers"]))
    
    # No customers found from either source
    if not customer_ids:
        return {"items": [], "complete": len(errors) == 0, "errors": errors, "skipped": False}
    
    # Fetch each customer's details ONCE (deduplicated)
    customers = []
    for cust_id in customer_ids:
        try:
            response = dispatch_with_retry(client, Req_GetCustomer(id=cust_id))
            if response.found and response.company:
                customers.append(response.company.model_dump())
        except Exception as e:
            errors.append(f"Customer {cust_id}: {str(e)}")
    
    return {"items": customers, "complete": len(errors) == 0, "errors": errors, "skipped": False}


# ============================================================================
# USER-SPECIFIC: USER'S TIME ENTRIES
# ============================================================================

def user_time_entries_raw(client, whoami: dict) -> dict:
    """
    Get all time entries for the current user.
    
    Args:
        client: SDK client
        whoami: Result from whoami_raw() containing current_user
    
    Returns:
        dict with:
        - "items": List of time entry dicts
        - "complete": True if all pages fetched
        - "errors": List of error messages
        - "pages_fetched": Number of pages
        - "skipped": True if public user
    """
    current_user = whoami.get("current_user")
    
    # Skip for public users
    if not current_user or whoami.get("is_public"):
        return {
            "items": [],
            "complete": True,
            "errors": [],
            "pages_fetched": 0,
            "skipped": True,
        }
    
    # Request factory with employee filter
    def request_factory(offset: int, limit: int):
        return Req_SearchTimeEntries(
            employee=current_user,
            offset=offset,
            limit=limit
        )
    
    result = _paginate(client, request_factory, "entries")
    result["skipped"] = False
    return result


# ============================================================================
# CONTEXT GATHERING: WHOAMI
# ============================================================================

def whoami_raw(client, task_info=None):
    """
    Get whoami - always returns dict (data or error).
    
    Args:
        client: SDK client
        task_info: Optional TaskInfo (unused, for consistent signature)
    """
    try:
        return client.dispatch(Req_WhoAmI()).model_dump()
    except Exception as e:
        return {"error": "whoami_failed", "message": str(e)}


def format_whoami(response: dict) -> str:
    """
    Format whoami response into LLM context block.
    Always returns a string (wrapped in <whoami_session_context>).
    """
    
    # Whoami failed - critical system issue
    if response.get("error"):
        message = response.get("message", "Unknown error")
        return f'''<whoami_session_context status="error">
SYSTEM NOTICE: Unable to verify user identity (/whoami request failed: {message}).

This request will be treated as coming from a public (unauthenticated) user.

If the request requires authenticated access, politely decline and explain:
"I'm currently unable to verify your identity due to a system issue. If you believe you should have access, please contact your system administrator for assistance."
</whoami_session_context>'''
    
    is_public = response.get("is_public", True)
    today = response.get("today", "unknown")
    
    # Public user
    if is_public or not response.get("current_user"):
        return f'''<whoami_session_context user="public">
You are responding to a public (unauthenticated) request.
user: public
access_level: guest
today: {today}
</whoami_session_context>'''
    
    # Authenticated user
    user_id = response["current_user"]
    location = response.get("location") or "unknown"
    department = response.get("department") or "unknown"
    
    return f'''<whoami_session_context kind="employee" id="{user_id}">
user: {user_id}
access_level: authenticated
location: {location}
department: {department}
today: {today}
</whoami_session_context>'''


# ============================================================================
# CONTEXT GATHERING: EMPLOYEE PROFILE
# ============================================================================

def employee_raw(client, whoami_response: dict):
    """
    Get employee profile using already-fetched whoami data.
    Always returns dict - either data or structured error.
    
    Args:
        client: SDK client
        whoami_response: Result from whoami_raw()
    """
    # Whoami failed - can't get employee profile
    if whoami_response.get("error"):
        return {"error": "whoami_failed", "message": whoami_response.get("message")}
    
    # Public user - no profile
    if whoami_response.get("is_public") or not whoami_response.get("current_user"):
        return {"error": "public_user"}
    
    user_id = whoami_response["current_user"]
    
    # Get employee details
    try:
        response = client.dispatch(Req_GetEmployee(id=user_id))
        return response.model_dump()
    except Exception as e:
        return {"error": "api_error", "user_id": user_id, "message": str(e)}


def format_employee(response: dict) -> str | None:
    """
    Format employee response with <employee:{id}> tag.
    Returns None for public users.
    """
    if response.get("error") == "public_user":
        return None
    if response.get("error"):
        return f'<kind=employee id=error>\n{response.get("message", "Unknown error")}\n</kind=employee id=error>'
    
    employee = response.get("employee")
    if not employee:
        return None
    
    emp_id = employee.get("id", "unknown")
    
    # Format skills/wills compactly
    skills = employee.get("skills", [])
    wills = employee.get("wills", [])
    skills_str = ", ".join(f"{s['name']}:{s['level']}" for s in skills) if skills else "none"
    wills_str = ", ".join(f"{w['name']}:{w['level']}" for w in wills) if wills else "none"
    
    lines = [
        f"<kind=employee id={emp_id}>",
        f"name: {employee.get('name', 'unknown')}",
        f"email: {employee.get('email', 'unknown')}",
        f"location: {employee.get('location', 'unknown')}",
        f"department: {employee.get('department', 'unknown')}",
        f"salary: {employee.get('salary', 0)}",
        f"notes: {employee.get('notes', '')}",
        f"skills: {skills_str}",
        f"wills: {wills_str}",
        f"</kind=employee id={emp_id}>",
    ]
    return "\n".join(lines)


# ============================================================================
# CONTEXT BLOCK FORMATTERS
# ============================================================================
# These functions create ContextBlock instances for individual entities.
# Used by collect_context_blocks() to build structured context.

def format_project_block(project: dict) -> ContextBlock:
    """
    Create a ContextBlock for a single project.
    
    Args:
        project: Project dict from user_projects_raw()
    
    Returns:
        ContextBlock with name like 'project:proj_xxx'
    """
    proj_id = project.get("id", "unknown")
    name = project.get("name", "Unknown Project")
    status = project.get("status", "unknown")
    
    content = _format_entity(project, f"kind=project id={proj_id}")
    summary = f'"{name}" - {status}'
    
    return ContextBlock(name=f"kind=project id={proj_id}", summary=summary, content=content)


def format_customer_block(customer: dict) -> ContextBlock:
    """
    Create a ContextBlock for a single customer.
    
    Args:
        customer: Customer dict from user_customers_raw()
    
    Returns:
        ContextBlock with name like 'customer:cust_xxx'
    """
    cust_id = customer.get("id", "unknown")
    name = customer.get("name", "Unknown Customer")
    location = customer.get("location", "unknown")
    deal_phase = customer.get("deal_phase", "unknown")
    
    content = _format_entity(customer, f"kind=customer id={cust_id}")
    
    # Summary for block list
    summary = f'"{name}" - {location} - {deal_phase}'
    
    return ContextBlock(name=f"kind=customer id={cust_id}", summary=summary, content=content)


def format_time_entry_block(entry: dict) -> ContextBlock:
    """
    Create a ContextBlock for a single time entry.
    
    Args:
        entry: Time entry dict from user_time_entries_raw()
    
    Returns:
        ContextBlock with name like 'time_entry:te_xxx'
    """
    entry_id = entry.get("id", "unknown")
    date = entry.get("date", "unknown")
    hours = entry.get("hours", 0)
    project = entry.get("project", "none")
    
    content = _format_entity(entry, f"kind=time_entry id={entry_id}")
    summary = f"{date} - {hours}h - {project}"
    
    return ContextBlock(name=f"kind=time_entry id={entry_id}", summary=summary, content=content)




# ============================================================================
# COLLECT CONTEXT BLOCKS
# ============================================================================

def collect_context_blocks(client, task_info=None, workers: int = 4) -> CollectedContext:
    """
    Collect all context as structured blocks.
    
    Args:
        client: SDK client
        task_info: Optional task info
        workers: Number of parallel workers (0 = sequential)
    
    Returns:
        CollectedContext with session, employee, and entity blocks
    """
    # Step 1: Get whoami (required for all others)
    whoami = whoami_raw(client, task_info)
    session_content = format_whoami(whoami)
    
    # Initialize result
    result = CollectedContext(
        session_content=session_content,
        employee_content=None,
        blocks={},
    )
    
    # Early return for public users - no additional blocks
    if whoami.get("is_public") or not whoami.get("current_user"):
        return result
    
    # Helper functions for parallel execution
    def get_employee():
        return employee_raw(client, whoami)
    
    def get_projects():
        return user_projects_raw(client, whoami)
    
    def get_customers():
        return user_customers_raw(client, whoami)
    
    def get_time_entries():
        return user_time_entries_raw(client, whoami)
    
    # Step 2: Execute (parallel or sequential)
    if workers > 0:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_employee = executor.submit(get_employee)
            future_projects = executor.submit(get_projects)
            future_customers = executor.submit(get_customers)
            future_time = executor.submit(get_time_entries)
            
            employee_result = future_employee.result()
            projects_result = future_projects.result()
            customers_result = future_customers.result()
            time_result = future_time.result()
    else:
        employee_result = get_employee()
        projects_result = get_projects()
        customers_result = get_customers()
        time_result = get_time_entries()
    
    # Step 3: Format employee (always included for authenticated users)
    result.employee_content = format_employee(employee_result)
    
    # Step 4: Create entity blocks for projects
    if projects_result.get("errors") and not projects_result.get("items"):
        name = "[error_user_projects]"
        result.blocks[name] = ContextBlock(
            name=name,
            summary="Error fetching user projects",
            content=f"<{name}>\nFailed to fetch user projects: {projects_result['errors'][0]}\n</{name}>",
        )
    elif not projects_result.get("items"):
        name = "[no_user_projects]"
        result.blocks[name] = ContextBlock(
            name=name,
            summary="No user projects found",
            content=f"<{name}>\nNo user projects found.\n</{name}>",
        )
    else:
        for proj in projects_result["items"]:
            block = format_project_block(proj)
            result.blocks[block.name] = block
    
    # Step 5: Create entity blocks for customers
    if customers_result.get("errors") and not customers_result.get("items"):
        name = "[error_user_customers]"
        result.blocks[name] = ContextBlock(
            name=name,
            summary="Error fetching user customers",
            content=f"<{name}>\nFailed to fetch user customers: {customers_result['errors'][0]}\n</{name}>",
        )
    elif not customers_result.get("items"):
        name = "[no_user_customers]"
        result.blocks[name] = ContextBlock(
            name=name,
            summary="No user customers found",
            content=f"<{name}>\nNo user customers found.\n</{name}>",
        )
    else:
        for cust in customers_result["items"]:
            block = format_customer_block(cust)
            result.blocks[block.name] = block
    
    # Step 6: Create entity blocks for time entries
    if time_result.get("errors") and not time_result.get("items"):
        name = "[error_user_time_entries]"
        result.blocks[name] = ContextBlock(
            name=name,
            summary="Error fetching user time entries",
            content=f"<{name}>\nFailed to fetch user time entries: {time_result['errors'][0]}\n</{name}>",
        )
    elif not time_result.get("items"):
        name = "[no_user_time_entries]"
        result.blocks[name] = ContextBlock(
            name=name,
            summary="No user time entries found",
            content=f"<{name}>\nNo user time entries found.\n</{name}>",
        )
    else:
        for entry in time_result["items"]:
            block = format_time_entry_block(entry)
            result.blocks[block.name] = block
    
    return result


def build_orchestrator_context(
    collected: CollectedContext,
    selected_blocks: List[str],
) -> str:
    """
    Build formatted context string for orchestrator prompt.
    
    Args:
        collected: CollectedContext from collect_context_blocks()
        selected_blocks: List of block names selected by context_builder
    
    Returns:
        Formatted context string ready for orchestrator prompt
    """
    parts = []
    
    # Always include session
    parts.append(collected.session_content)
    
    # Always include employee (if available)
    if collected.employee_content:
        parts.append(collected.employee_content)
    
    # Add selected block contents only
    if selected_blocks:
        selected_content = collected.get_content(selected_blocks)
        if selected_content:
            parts.append(selected_content)
    
    return "\n\n".join(parts)


# ============================================================================
# SDK TOOL EXECUTION
# ============================================================================

def execute_single_call(function, benchmark_client) -> dict:
    """
    Execute a single SDK tool call for ERC3 benchmark.
    
    Args:
        function: SDK request object or custom wrapper tool
        benchmark_client: SDK client for API calls
    
    Returns:
        dict with:
        - "text": formatted response string for conversation log
        - "tool_call": {request, response} dict for trace
    """
    # Wrapper: Log time entry (field ordering fix)
    if isinstance(function, erc3_prompts.Req_LogTimeEntry):
        function = Req_LogTimeEntry(**function.model_dump())
    
    # Wrappers: List endpoints (autopaginated, formatted as directories)
    elif isinstance(function, erc3_prompts.Req_ListEmployees):
        result = _paginate(benchmark_client, Req_ListEmployees, "employees")
        formatted = format_employees_list(result)
        return {
            "text": formatted,
            "tool_call": {"request": {}, "response": {"count": len(result["items"])}}
        }
    
    elif isinstance(function, erc3_prompts.Req_ListCustomers):
        result = _paginate(benchmark_client, Req_ListCustomers, "companies")
        formatted = format_customers_list(result)
        return {
            "text": formatted,
            "tool_call": {"request": {}, "response": {"count": len(result["items"])}}
        }
    
    elif isinstance(function, erc3_prompts.Req_ListProjects):
        result = _paginate(benchmark_client, Req_ListProjects, "projects")
        formatted = format_projects_list(result)
        return {
            "text": formatted,
            "tool_call": {"request": {}, "response": {"count": len(result["items"])}}
        }
    
    # Wrappers: Search endpoints (autopaginated with filters)
    elif isinstance(function, erc3_prompts.Req_SearchEmployees):
        params = function.model_dump(exclude={'tool'})
        result = _paginate(
            benchmark_client,
            lambda offset, limit: Req_SearchEmployees(**params, offset=offset, limit=limit),
            "employees"
        )
        response_dict = {"employees": result["items"]}
        if not result["complete"] and result["errors"]:
            response_dict["error"] = f"Incomplete: {result['errors'][0]}"
        return {
            "text": json.dumps(response_dict, indent=2, ensure_ascii=False),
            "tool_call": {"request": params, "response": response_dict}
        }
    
    elif isinstance(function, erc3_prompts.Req_SearchCustomers):
        params = function.model_dump(exclude={'tool'})
        result = _paginate(
            benchmark_client,
            lambda offset, limit: Req_SearchCustomers(**params, offset=offset, limit=limit),
            "companies"
        )
        response_dict = {"companies": result["items"]}
        if not result["complete"] and result["errors"]:
            response_dict["error"] = f"Incomplete: {result['errors'][0]}"
        return {
            "text": json.dumps(response_dict, indent=2, ensure_ascii=False),
            "tool_call": {"request": params, "response": response_dict}
        }
    
    elif isinstance(function, erc3_prompts.Req_SearchProjects):
        params = function.model_dump(exclude={'tool'})
        result = _paginate(
            benchmark_client,
            lambda offset, limit: Req_SearchProjects(**params, offset=offset, limit=limit),
            "projects"
        )
        response_dict = {"projects": result["items"]}
        if not result["complete"] and result["errors"]:
            response_dict["error"] = f"Incomplete: {result['errors'][0]}"
        return {
            "text": json.dumps(response_dict, indent=2, ensure_ascii=False),
            "tool_call": {"request": params, "response": response_dict}
        }
    
    elif isinstance(function, erc3_prompts.Req_SearchTimeEntries):
        params = function.model_dump(exclude={'tool'})
        result = _paginate(
            benchmark_client,
            lambda offset, limit: Req_SearchTimeEntries(**params, offset=offset, limit=limit),
            "entries"
        )
        response_dict = {"entries": result["items"]}
        # Capture summary fields from first item's response (they're global totals from server)
        if result["items"] and result["complete"]:
            # Make one call to get summaries
            try:
                resp = dispatch_with_retry(benchmark_client, Req_SearchTimeEntries(**params, offset=0, limit=1))
                if hasattr(resp, 'total_hours'):
                    response_dict['total_hours'] = resp.total_hours
                    response_dict['total_billable'] = resp.total_billable
                    response_dict['total_non_billable'] = resp.total_non_billable
            except:
                pass
        if not result["complete"] and result["errors"]:
            response_dict["error"] = f"Incomplete: {result['errors'][0]}"
        return {
            "text": json.dumps(response_dict, indent=2, ensure_ascii=False),
            "tool_call": {"request": params, "response": response_dict}
        }
    
    # Standard SDK dispatch via shared infrastructure
    return execute_sdk_call(function, benchmark_client)


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def execute_erc3_tools(job, benchmark_client) -> dict:
    """
    Execute SDK tool(s) for ERC3 benchmark.
    
    This is the main entry point called by run_agent_loop via tool_executor.
    Currently only supports single call mode.
    
    Args:
        job: Parsed LLM output with call.function
        benchmark_client: SDK client for ERC3 API calls
    
    Returns:
        dict with:
        - "text": Formatted response for conversation
        - "tool_calls": List of {request, response} dicts for trace
        - "function": The function executed (for display)
    """
    if job.call.call_mode == "single":
        function = job.call.function
        result = execute_single_call(function, benchmark_client)
        return {
            "text": result["text"],
            "tool_calls": [result["tool_call"]],
            "function": function,
        }
    else:
        raise ValueError(f"Unsupported call_mode for ERC3: {job.call.call_mode}")
