"""
ERC3 benchmark runner.

Coordinates context gathering, agent execution, and evaluation.
"""

import json
from pathlib import Path
from typing import List

from langfuse import get_client, observe

from erc3 import ERC3, TaskInfo
from erc3.erc3.dtos import Req_ProvideAgentResponse, Req_ListWiki

from infrastructure import AgentStepLimitError, TaskContext, LLM_MODEL_LOG_NAME
import config

from .runtime import (
    AGENT_REGISTRY,
    run_agent_loop,
    run_context_builder,
    collect_context_blocks,
    build_agent_context,
    whoami_raw,
    load_rules_for_session,
)


def _get_wiki_sha1(whoami: dict, benchmark_client) -> str:
    """
    Get wiki SHA1 with fallback to /wiki/list if whoami fails.
    
    Args:
        whoami: Result from whoami_raw()
        benchmark_client: SDK client for API calls
    
    Returns:
        8-character SHA1 prefix, or empty string on total failure
    """
    # Try to get from whoami first
    wiki_sha1 = whoami.get("wiki_sha1", "")
    
    # If whoami returned empty (system error simulation), fallback to /wiki/list
    if not wiki_sha1:
        try:
            wiki_list_response = benchmark_client.dispatch(Req_ListWiki())
            wiki_sha1 = wiki_list_response.sha1
            if config.VERBOSE:
                print(f"  ℹ Recovered wiki_sha1 from /wiki/list: {wiki_sha1[:8]}")
        except Exception as e:
            if config.VERBOSE:
                print(f"  ⚠ Failed to get wiki_sha1 from /wiki/list: {e}")
            return ""
    
    return wiki_sha1[:8] if wiki_sha1 else ""


def _load_company_info(wiki_sha1: str) -> dict:
    """
    Load company info from wiki_meta.json with fallback to defaults.
    
    Args:
        wiki_sha1: 8-character SHA1 prefix
    
    Returns:
        Dict with company_name, company_locations, company_execs
    """
    defaults = {"company_name": "Unknown", "company_locations": [], "company_execs": []}
    
    wiki_meta_path = Path(__file__).parent / "wiki_data" / wiki_sha1 / "wiki_meta.json"
    if not wiki_meta_path.exists():
        if config.VERBOSE:
            print(f"  ℹ No wiki_meta.json found, using defaults")
        return defaults
    
    try:
        wiki_meta = json.loads(wiki_meta_path.read_text(encoding="utf-8"))
        return {
            "company_name": wiki_meta.get("company_name", defaults["company_name"]),
            "company_locations": wiki_meta.get("company_locations", defaults["company_locations"]),
            "company_execs": wiki_meta.get("company_execs", defaults["company_execs"]),
        }
    except Exception as e:
        if config.VERBOSE:
            print(f"  ⚠ Failed to load wiki_meta.json: {e}, using defaults")
        return defaults


def _build_full_erc3_context(
    task_text: str,
    base_context: str,
    selected_blocks: List[str],
) -> str:
    """Combine task and context blocks for the agent prompt."""
    parts = [
        "<task_request>",
        task_text,
        "</task_request>",
        "<selected_block_ids>",
        "\n".join(selected_blocks) if selected_blocks else "[none]",
        "</selected_block_ids>",
        "<context_blocks>",
        base_context or "[no_additional_context]",
        "</context_blocks>",
    ]
    
    return "\n".join(parts)


def _complete_and_format_result(task: TaskInfo, erc_client: ERC3, trace: List[dict], agent_result: dict, benchmark: str) -> dict:
    """Submit task completion and format the final payload."""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            completion = erc_client.complete_task(task)
            score = completion.eval.score if completion.eval else 0
            eval_logs = completion.eval.logs if completion.eval else None
            break
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"WARNING: Task completion failed for task {task.task_id} (attempt {attempt + 1}/{max_retries}): {str(e)}")
                continue
            else:
                # If completion/evaluation fails after all retries, return result without score
                print(f"ERROR: Task completion failed for task {task.task_id} after {max_retries} attempts: {str(e)}")
                score = 0
                eval_logs = f"Completion failed after {max_retries} attempts: {str(e)}"
    
    lf = get_client()
    lf.score_current_span(name="score", value=score or 0, data_type="NUMERIC", comment=eval_logs)
    
    return {
        "task_id": task.task_id,
        "task_index": task.num,
        "task_text": task.task_text,
        "benchmark": benchmark,
        "trace": trace,
        "code": agent_result.get("status", "completed"),
        "summary": agent_result.get("message", ""),
        "outcome": agent_result.get("outcome"),
        "links": agent_result.get("links", []),
        "orchestrator_log": agent_result.get("orchestrator_log", []),
        "score": score,
        "eval_logs": eval_logs,
    }


def _handle_timeout(
    benchmark_client,
    task: TaskInfo,
    erc_client: ERC3,
    trace: List[dict],
    benchmark: str,
) -> dict:
    """Send fallback response on step limit and finalize result."""
    timeout_message = "Unable to complete request within the allowed number of steps. Please try again later."
    try:
        benchmark_client.dispatch(Req_ProvideAgentResponse(
            message=timeout_message,
            outcome="error_internal",
            links=[],
        ))
    except Exception:
        # If fallback response fails, continue with completion so evaluation still runs.
        pass
    
    result_payload = {
        "status": "timeout",
        "message": timeout_message,
        "outcome": "error_internal",
        "links": [],
        "orchestrator_log": [],
    }
    return _complete_and_format_result(task, erc_client, trace, result_payload, benchmark)


@observe()
def run_erc3_benchmark(erc_client: ERC3, task: TaskInfo) -> dict:
    """
    Entry point for ERC3 benchmark execution.
    """
    benchmark_client = erc_client.get_erc_dev_client(task)
    trace: List[dict] = []
    
    if config.VERBOSE:
        print(f"\nTask: {task.task_text}\n")
    
    # Clone agent config and customize system prompt
    agent_config = AGENT_REGISTRY["Agent"].copy()
    
    # Context gathering pipeline
    whoami = whoami_raw(benchmark_client)
    task_ctx = TaskContext(erc_client=erc_client, task_id=task.task_id, model=LLM_MODEL_LOG_NAME, whoami=whoami)
    collected = collect_context_blocks(benchmark_client, task, workers=10)
    
    # Run context builder
    lf = get_client()
    trace_id = lf.get_current_trace_id()
    parent_obs_id = lf.get_current_observation_id()
    
    try:
        selected_blocks = run_context_builder(
            task.task_text,
            collected,
            task_ctx,
            trace,
            langfuse_trace_id=trace_id,
            langfuse_parent_observation_id=parent_obs_id,
        )
    except Exception as e:
        print(f"✗ Context builder error: {e}, returning all blocks")
        selected_blocks = list(collected.blocks.keys())
    
    base_context = build_agent_context(collected, selected_blocks)
    rules = load_rules_for_session(whoami)
    
    # Load company info and format system prompt
    wiki_sha1 = _get_wiki_sha1(whoami, benchmark_client)
    if not wiki_sha1:
        raise ValueError("Unable to determine wiki_sha1 from /whoami or /wiki/list. Cannot proceed.")
    
    # Load company info from wiki_meta
    company_info = _load_company_info(wiki_sha1)
    
    system_prompt = agent_config["system_prompt"].format(
        company_name=company_info["company_name"],
        company_locations=", ".join(company_info["company_locations"]),
        company_execs=", ".join(company_info["company_execs"])
    )
    
    if rules and rules.strip():
        # Add tailored_for attribute if authenticated user
        user_id = whoami.get("current_user")
        if user_id and not whoami.get("is_public"):
            system_prompt = f'{system_prompt}\n\n<rules tailored_for="{user_id}">\n{rules}\n</rules>'
        else:
            system_prompt = f"{system_prompt}\n\n<rules>\n{rules}\n</rules>"
    agent_config["system_prompt"] = system_prompt
    
    full_context = _build_full_erc3_context(task.task_text, base_context, selected_blocks)
    
    try:
        agent_result = run_agent_loop(
            agent_config=agent_config,
            initial_context=full_context,
            benchmark_client=benchmark_client,
            trace=trace,
            parent_node_id="0",
            task_ctx=task_ctx,
        )
    except AgentStepLimitError:
        return _handle_timeout(benchmark_client, task, erc_client, trace, task.benchmark or "erc3")
    
    return _complete_and_format_result(task, erc_client, trace, agent_result, task.benchmark or "erc3")
