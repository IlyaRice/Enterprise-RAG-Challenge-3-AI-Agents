"""
Store benchmark runner.

Entry point for store benchmark execution. Handles:
- Orchestrator setup and configuration
- Task completion and evaluation
- Error handling for step limit exceeded
"""

from typing import List
from langfuse import get_client, observe

import config
from erc3 import TaskInfo, ERC3

# Import from universal infrastructure
from infrastructure import (
    AgentStepLimitError,
    TaskContext,
    LLM_MODEL_LOG_NAME,
)

# Import from universal agent execution
from agent_execution import run_agent_loop

# Import from store-specific modules
from .agent_config import AGENT_REGISTRY
from .prompts import SubmitTask
from .tools import execute_store_tools


# ============================================================================
# INTERNAL HELPERS
# ============================================================================

def _handle_task_completion(
    function: SubmitTask,
    task: TaskInfo,
    erc_client: ERC3,
    trace: List[dict],
    orchestrator_log: List[dict] = None
) -> dict:
    """
    Handle SubmitTask terminal action and return final result.
    
    Args:
        function: SubmitTask instance with outcome and report
        task: Task being completed
        erc_client: ERC3 client for task completion API
        trace: Trace of all events
        orchestrator_log: Full orchestrator conversation log (optional)
    
    Returns:
        Result dict with task_id, task_text, benchmark, trace, code, summary, score, eval_logs
    """
    # Determine code from outcome
    code = "completed" if function.outcome == "success" else "refused"
    report_text = function.report

    # Complete task and get evaluation
    completion = erc_client.complete_task(task)
    
    score = completion.eval.score if completion.eval else None
    eval_logs = completion.eval.logs if completion.eval else None
    
    lf = get_client()
    lf.score_current_span(name="score", value=score, data_type="NUMERIC", comment=eval_logs)

    if config.VERBOSE:
        print(f"Score: {score}")
        if eval_logs:
            print(f"Eval: {eval_logs}")

    result = {
        "task_id": task.task_id,
        "task_index": task.num,
        "task_text": task.task_text,
        "benchmark": "store",
        "trace": trace,
        "code": code,
        "summary": report_text,
        "score": score,
        "eval_logs": eval_logs
    }
    
    # Include orchestrator_log
    if orchestrator_log is not None:
        result["orchestrator_log"] = orchestrator_log
    
    return result


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

@observe()
def run_store_benchmark(erc_client: ERC3, task: TaskInfo) -> dict:
    """
    Entry point for store benchmark execution.
    
    Runs the orchestrator agent that coordinates sub-agents for store benchmark.
    
    Args:
        erc_client: ERC3 client for task completion API
        task: Task to run
    
    Returns:
        Result dict including trace of all events.
    """
    # Get benchmark client
    benchmark_client = erc_client.get_store_client(task)
    
    # Initialize trace for collecting events
    trace = []
    
    # Create TaskContext for LLM usage logging
    task_ctx = TaskContext(erc_client=erc_client, task_id=task.task_id, model=LLM_MODEL_LOG_NAME)
    
    if config.VERBOSE:
        print(f"\nTask: {task.task_text}\n")
    
    # Get orchestrator config
    orchestrator_config = AGENT_REGISTRY["Orchestrator"]
    system_prompt = f"{orchestrator_config['system_prompt']}first step"
    
    # Initialize orchestrator_log for subagent context
    orchestrator_log = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": task.task_text},
    ]
    
    try:
        # Run orchestrator via unified loop
        result = run_agent_loop(
            agent_config=orchestrator_config,
            initial_context=task.task_text,
            benchmark_client=benchmark_client,
            trace=trace,
            parent_node_id="0",  # Orchestrator steps start from "1" (virtual root "0")
            orchestrator_log=orchestrator_log,
            task_ctx=task_ctx,
            tool_executor=execute_store_tools,
        )
        
        # Create terminal action for completion handling
        outcome = "success" if result["status"] == "completed" else "failure"
        terminal_action = SubmitTask(tool="submit_task", outcome=outcome, report=result["report"])
        
        if config.VERBOSE:
            print()
        return _handle_task_completion(
            terminal_action, task, erc_client, trace, orchestrator_log
        )
        
    except AgentStepLimitError:
        # Orchestrator exceeded step limit - complete task with timeout
        completion = erc_client.complete_task(task)
        
        score = completion.eval.score if completion.eval else None
        eval_logs = completion.eval.logs if completion.eval else None
        
        if config.VERBOSE:
            print(f"\nScore: {score}")
            if eval_logs:
                print(f"Eval: {eval_logs}")
        
        return {
            "task_id": task.task_id,
            "task_index": task.num,
            "task_text": task.task_text,
            "benchmark": "store",
            "trace": trace,
            "orchestrator_log": orchestrator_log,
            "code": "timeout",
            "summary": "Orchestrator exceeded maximum steps limit",
            "score": score,
            "eval_logs": eval_logs
        }

