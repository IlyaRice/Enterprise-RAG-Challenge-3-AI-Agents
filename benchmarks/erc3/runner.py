"""
ERC3 benchmark runner.

Coordinates context gathering, orchestrator execution, and evaluation.
"""

from typing import List

from langfuse import get_client, observe

import config
from erc3 import ERC3, TaskInfo
from erc3.erc3.dtos import Req_ProvideAgentResponse

from infrastructure import AgentStepLimitError, TaskContext, LLM_MODEL_LOG_NAME

from .agent_config import AGENT_REGISTRY
from .agent_execution import run_context_builder, run_erc3_agent_loop
from .rules import load_rules_for_session
from .tools import (
    collect_context_blocks,
    build_orchestrator_context,
    whoami_raw,
)


def _build_full_erc3_context(
    task_text: str,
    base_context: str,
    selected_blocks: List[str],
) -> str:
    """Combine task and context blocks for the orchestrator prompt."""
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
    completion = erc_client.complete_task(task)
    score = completion.eval.score if completion.eval else None
    eval_logs = completion.eval.logs if completion.eval else None
    
    lf = get_client()
    lf.score_current_span(name="score", value=score, data_type="NUMERIC", comment=eval_logs)
    
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
    task_ctx = TaskContext(erc_client=erc_client, task_id=task.task_id, model=LLM_MODEL_LOG_NAME)
    
    if config.VERBOSE:
        print(f"\nTask: {task.task_text}\n")
    
    # Clone orchestrator config and customize system prompt
    orchestrator_config = AGENT_REGISTRY["ERC3Orchestrator"].copy()
    
    # Context gathering pipeline
    whoami = whoami_raw(benchmark_client)
    collected = collect_context_blocks(benchmark_client, task)
    selected_blocks = run_context_builder(task.task_text, collected, task_ctx)
    base_context = build_orchestrator_context(collected, selected_blocks)
    rules = load_rules_for_session(whoami)
    
    # Build system prompt with rules appended
    system_prompt = orchestrator_config["system_prompt"]
    if rules and rules.strip():
        system_prompt = f"{system_prompt}\n\n<rules>\n{rules}\n</rules>"
    orchestrator_config["system_prompt"] = system_prompt
    
    full_context = _build_full_erc3_context(task.task_text, base_context, selected_blocks)
    
    try:
        agent_result = run_erc3_agent_loop(
            agent_config=orchestrator_config,
            initial_context=full_context,
            benchmark_client=benchmark_client,
            trace=trace,
            parent_node_id="0",
            task_ctx=task_ctx,
        )
    except AgentStepLimitError:
        return _handle_timeout(benchmark_client, task, erc_client, trace, task.benchmark or "erc3")
    
    return _complete_and_format_result(task, erc_client, trace, agent_result, task.benchmark or "erc3")