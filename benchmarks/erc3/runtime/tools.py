"""
ERC3 SDK tool execution.

Contains:
- Pagination helpers: _fetch_page, _paginate
- SDK execution: execute_single_call, execute_erc3_tools

Uses shared execute_sdk_call from infrastructure for core SDK dispatch.
"""

import json

from erc3.erc3.dtos import (
    Req_ListEmployees, Req_ListCustomers, Req_ListProjects,
    Req_SearchEmployees, Req_SearchCustomers, Req_SearchProjects,
    Req_SearchTimeEntries, Req_LogTimeEntry,
)
from infrastructure import execute_sdk_call, dispatch_with_retry

from . import prompts as erc3_prompts
from .context import (
    format_employees_list, format_customers_list, format_projects_list,
    load_respond_rules_for_session,
    _paginate,
)


# ============================================================================
# SDK TOOL EXECUTION
# ============================================================================

def execute_single_call(function, benchmark_client, task_ctx=None) -> dict:
    """
    Execute a single SDK tool call for ERC3 benchmark.
    
    Args:
        function: SDK request object or custom wrapper tool
        benchmark_client: SDK client for API calls
        task_ctx: TaskContext for internal tools needing whoami
    
    Returns:
        dict with "text" and "tool_call"
    """
    # Internal tool: Load respond instructions
    if isinstance(function, erc3_prompts.Req_LoadRespondInstructions):
        whoami = task_ctx.whoami if task_ctx else None
        rules = load_respond_rules_for_session(whoami) if whoami else ""
        text = f"<respond_instructions>\n{rules or '(No respond instructions found)'}\n</respond_instructions>"
        return {"text": text, "tool_call": {"request": {}, "response": {"loaded": bool(rules)}}}
    
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

def execute_erc3_tools(job, benchmark_client, task_ctx=None) -> dict:
    """Execute SDK tool for ERC3 benchmark. Returns dict with text, tool_calls, function."""
    function = job.function
    result = execute_single_call(function, benchmark_client, task_ctx)
    return {"text": result["text"], "tool_calls": [result["tool_call"]], "function": function}

