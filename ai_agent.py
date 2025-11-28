"""
AI Agent main entry point module.

This is the thin entry layer for running agents. The actual logic is distributed across:
- infrastructure.py: LLM client, trace helpers, SDK execution, utilities
- agent_types.py: Agent registry and configuration
- agent_execution.py: Unified agent loop and execution logic

Contains:
- run_agent() - main entry point
- run_orchestrator() - thin wrapper calling run_agent_loop
- handle_task_completion() - finalization

Import hierarchy: This module imports from all three lower-level modules.
"""

from typing import List
from langfuse import get_client, observe

import config
from erc3 import TaskInfo, ERC3

# Import from infrastructure
from infrastructure import (
    AgentStepLimitError,
    TaskContext,
    LLM_MODEL,
)

# Import from agent_types
from agent_types import (
    AGENT_REGISTRY,
)

# Import from agent_execution
from agent_execution import (
    run_agent_loop,
    run_task_analyzer,
)

# Import terminal actions for handle_task_completion
from subagent_prompts import CompleteTask, RefuseTask


# ============================================================================
# TASK COMPLETION HANDLER
# ============================================================================

def handle_task_completion(
    function,
    task: TaskInfo,
    erc_client: ERC3,
    trace: List[dict],
    benchmark: str,
    orchestrator_log: List[dict] = None
) -> dict:
    """
    Handle CompleteTask or RefuseTask terminal actions and return final result.
    
    Args:
        function: CompleteTask or RefuseTask instance
        task: Task being completed
        erc_client: ERC3 client for task completion API
        trace: Trace of all events
        benchmark: Benchmark name (e.g., "store")
        orchestrator_log: Full orchestrator conversation log (optional)
    
    Returns:
        Result dict with task_id, task_text, benchmark, trace, code, summary, score, eval_logs
    """
    # Determine success/failure and extract report
    if isinstance(function, CompleteTask):
        code = "completed"
    elif isinstance(function, RefuseTask):
        code = "refused"
    else:
        code = "failed"
    
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
        "benchmark": benchmark,
        "trace": trace,
        "code": code,
        "summary": report_text,
        "score": score,
        "eval_logs": eval_logs
    }
    
    # Include orchestrator_log if provided (store benchmark)
    if orchestrator_log is not None:
        result["orchestrator_log"] = orchestrator_log
    
    return result


# ============================================================================
# ORCHESTRATOR ENTRY POINT
# ============================================================================

@observe()
def run_orchestrator(erc_client: ERC3, task: TaskInfo, benchmark_client) -> dict:
    """
    Run the orchestrator agent that coordinates sub-agents for store benchmark.
    
    This is a thin wrapper around run_agent_loop with Orchestrator configuration.
    
    Args:
        erc_client: ERC3 client for task completion API
        task: Task to run
        benchmark_client: SDK client for API calls
    
    Returns:
        Result dict including trace of all events.
    """
    # Initialize trace for collecting events
    trace = []
    
    # Create TaskContext for LLM usage logging
    task_ctx = TaskContext(erc_client=erc_client, task_id=task.task_id, model=LLM_MODEL)
    
    if config.VERBOSE:
        print(f"\nTask: {task.task_text}\n")
    
    # Preprocess task to expand requirements (node_id="0", depth=-1)
    expanded_task = run_task_analyzer(task.task_text, trace, task_ctx=task_ctx)
    
    # Get orchestrator config
    orchestrator_config = AGENT_REGISTRY["Orchestrator"]
    system_prompt = f"{orchestrator_config['system_prompt']}first step"
    
    # Initialize orchestrator_log for subagent context
    orchestrator_log = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": expanded_task},
    ]
    
    try:
        # Run orchestrator via unified loop
        result = run_agent_loop(
            agent_config=orchestrator_config,
            initial_context=expanded_task,
            benchmark_client=benchmark_client,
            trace=trace,
            parent_node_id="0",  # Orchestrator is child of TaskAnalyzer
            orchestrator_log=orchestrator_log,
            task_ctx=task_ctx,
        )
        
        # Create terminal action for handle_task_completion
        if result["status"] == "completed":
            terminal_action = CompleteTask(tool="complete_task", report=result["report"])
        else:
            terminal_action = RefuseTask(tool="refuse_task", report=result["report"])
        
        if config.VERBOSE:
            print()
        return handle_task_completion(
            terminal_action, task, erc_client, trace, "store", orchestrator_log
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


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

@observe()
def run_agent(erc_client: ERC3, task: TaskInfo, benchmark: str) -> dict:
    """
    Main entry point for running an agent on a task.
    
    Currently only supports store benchmark with orchestrator + sub-agent architecture.
    
    Args:
        erc_client: ERC3 client for API access
        task: Task to run
        benchmark: Benchmark name (currently only "store" is supported)
    
    Returns:
        Result dict including trace of all events.
    """
    if benchmark == "store":
        benchmark_client = erc_client.get_store_client(task)
        return run_orchestrator(erc_client, task, benchmark_client)
    else:
        raise ValueError(f"Unknown benchmark: {benchmark}. Only 'store' is supported.")
