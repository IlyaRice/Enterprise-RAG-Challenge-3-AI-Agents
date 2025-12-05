"""
ERC utilities module.

Contains:
- TaskResult, RunMeta, RunResult - Pydantic models for consistent return types
- repeat_tasks() - Run multiple task specs, each N times
- create_and_run_session() - Create and run a competition session

Private helpers:
- _run_task_once() - Run a single task instance
- _repeat_task() - Run same task spec multiple times
- _run_parallel() - Parallel execution with Langfuse trace propagation
- _visualize_task_scores() - Bar chart visualization
"""

import json
import os
from datetime import datetime
from pydantic import BaseModel
from typing import Any, List, Callable, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import matplotlib.pyplot as plt
from erc3 import ERC3, TaskInfo
from langfuse import observe, get_client

from ai_agent import run_agent
import config

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class TaskResult(BaseModel):
    """Single task execution result - the atomic unit."""
    task_id: str
    task_index: int
    task_text: str
    benchmark: str
    code: str  # "completed", "refused", "timeout"
    summary: str
    score: Optional[float]
    eval_logs: Optional[str]
    trace: List[dict]
    orchestrator_log: Optional[List[dict]] = None


class RunMeta(BaseModel):
    """Metadata for a batch run."""
    benchmark: str
    task_indices: List[int]
    num_runs: int
    session_id: Optional[str]  # None for repeat_tasks
    total_score: float
    num_tasks: int
    avg_score: float
    workspace: str
    name: str
    architecture: str
    started_at: str  # ISO 8601 format


class RunResult(BaseModel):
    """Result from repeat_tasks or create_and_run_session."""
    meta: RunMeta
    results: List[TaskResult]


# ============================================================================
# PRIVATE HELPERS
# ============================================================================

def _run_parallel(func: Callable, items: List, max_workers: int = None, **kwargs) -> List:
    """Execute function on items in parallel with Langfuse trace propagation."""
    lf = get_client()
    trace_id = lf.get_current_trace_id()
    parent_obs_id = lf.get_current_observation_id()
    
    max_workers = max_workers or len(items)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(
                func, item,
                langfuse_trace_id=trace_id,
                langfuse_parent_observation_id=parent_obs_id,
                **kwargs
            )
            for item in items
        ]
        return [f.result() for f in futures]


@observe()
def _run_task_once(benchmark: str, task_index: int, **_lf: Any) -> dict:
    """Create and run a single task instance. Returns raw dict."""
    erc = ERC3()
    benchmark_info = erc.view_benchmark(benchmark)
    spec_id = benchmark_info.specs[task_index].id
    
    # Create new task instance
    task_response = erc.start_new_task(benchmark=benchmark, spec_id=spec_id)
    task_detail = erc.task_detail(task_response.task_id)
    
    task = TaskInfo(
        spec_id=spec_id,
        task_id=task_response.task_id,
        num=task_index,
        task_text=task_detail.text,
        status="new",
        benchmark=benchmark,
        score=-1.0
    )
    
    return run_agent(erc, task, benchmark)


@observe()
def _repeat_task(benchmark: str, task_index: int, num_times: int) -> List[dict]:
    """Run same task spec multiple times in parallel. Returns list of raw dicts."""
    results = _run_parallel(
        lambda _, **kw: _run_task_once(benchmark, task_index, **kw),
        range(num_times)
    )
    
    # Print summary
    total_score = sum(r["score"] for r in results if r["score"] is not None)
    task_text = results[0]["task_text"] if results else "Unknown"
    print(f"{'#'*30}\nTask {task_index+1}: {task_text}\nTotal: {total_score}/{len(results)}\n{'#'*30}")
    
    lf = get_client()
    lf.score_current_span(
        name="avg-score",
        value=total_score/len(results) if results else 0,
        data_type="NUMERIC",
        comment=f"{total_score}/{len(results)} tasks"
    )
    
    return results


def _save_results(result: "RunResult", export_path: str, prefix: str):
    """Save RunResult to JSON files (full + summary)."""
    timestamp = result.meta.started_at.replace(":", "-").replace(".", "-")
    filename = f"{prefix}_{timestamp}.json"
    
    # Save full trace
    os.makedirs(export_path, exist_ok=True)
    filepath_full = os.path.join(export_path, filename)
    with open(filepath_full, "w", encoding="utf-8") as f:
        json.dump(result.model_dump(), f, ensure_ascii=False, indent=2)
    
    # Save summary (without trace fields)
    summary_dir = os.path.join(export_path, "summary")
    os.makedirs(summary_dir, exist_ok=True)
    filepath_summary = os.path.join(summary_dir, filename)
    
    result_dict = result.model_dump()
    result_dict["results"] = [{k: v for k, v in r.items() if k != "trace"} for r in result_dict["results"]]
    
    with open(filepath_summary, "w", encoding="utf-8") as f:
        json.dump(result_dict, f, ensure_ascii=False, indent=2)
    
    print(f"Results saved to: {filepath_full}")
    print(f"Summary saved to: {filepath_summary}")


def _visualize_task_scores(results: List[TaskResult], num_runs: int):
    """Visualize task scores with adaptive figure width."""
    import textwrap
    from collections import defaultdict
    
    # Group results by task_index
    by_task = defaultdict(list)
    for r in results:
        by_task[r.task_index].append(r)
    
    # Sort by task index
    sorted_indices = sorted(by_task.keys())
    
    # Prepare data
    categories = []
    values = []
    for idx in sorted_indices:
        task_results = by_task[idx]
        task_text = task_results[0].task_text if task_results else ""
        total = sum(r.score for r in task_results if r.score is not None)
        
        categories.append(f"Task {idx+1}:\n{textwrap.fill(task_text[:80], width=16)}")
        values.append(total)
    
    # Visual parameters
    BAR_WIDTH = 0.8
    INCHES_PER_BAR = 0.8
    MARGIN_INCHES = 2
    
    num_bars = len(categories)
    fig_width = num_bars * INCHES_PER_BAR + MARGIN_INCHES
    
    # Create figure with dynamic width
    plt.figure(figsize=(fig_width, 6), dpi=150)
    
    # Create bar chart
    plt.bar(categories, values, width=BAR_WIDTH)
    plt.axhline(y=num_runs, linestyle='-')
    plt.ylim(0, num_runs * 1.15)
    plt.title('Agent reliability by task')
    plt.xticks(fontsize=6)
    # Adjust layout to prevent cutoff
    plt.tight_layout()
    plt.show()


# ============================================================================
# PUBLIC API
# ============================================================================

@observe()
def repeat_tasks(
    benchmark: str,
    task_indices: List[int],
    num_times: int,
    workspace: str = "test",
    name: str = "Standalone tasks",
    architecture: str = "Multiagent",
    export_path: Optional[str] = None
) -> RunResult:
    """
    Run multiple task specs, each N times in parallel.
    
    Args:
        benchmark: Benchmark name (e.g., "store")
        task_indices: List of task indices to run (e.g., [0, 1, 2])
        num_times: Number of times to run each task
        workspace: Workspace name (default: "test")
        name: Run name (default: "Standalone tasks")
        architecture: Architecture description (default: "Multiagent")
        export_path: Optional path to save results as JSON
    
    Returns:
        RunResult with all results sorted by task_index, and consistent meta
    """
    started_at = datetime.now().isoformat()
    
    # Run all tasks
    all_results = []
    for idx in task_indices:
        task_results = _repeat_task(benchmark, idx, num_times)
        all_results.extend(task_results)
    
    # Convert to TaskResult objects
    task_results = [TaskResult(**r) for r in all_results]
    
    # Sort by task_index
    task_results.sort(key=lambda r: r.task_index)
    
    # Calculate meta
    total_score = sum(r.score for r in task_results if r.score is not None)
    num_tasks = len(task_results)
    num_scored = sum(1 for r in task_results if r.score is not None)
    avg_score = total_score / num_scored if num_scored > 0 else 0.0
    
    meta = RunMeta(
        benchmark=benchmark,
        task_indices=sorted(task_indices),
        num_runs=num_times,
        session_id=None,
        total_score=total_score,
        num_tasks=num_tasks,
        avg_score=avg_score,
        workspace=workspace,
        name=name,
        architecture=architecture,
        started_at=started_at,
    )
    
    result = RunResult(results=task_results, meta=meta)
    
    # Visualize if multiple tasks
    if len(task_indices) > 1:
        _visualize_task_scores(task_results, num_times)
    
    # Export results if path provided
    if export_path:
        _save_results(result, export_path, "repeat_tasks")
    
    return result


@observe()
def _run_session(
    benchmark: str,
    session_id: str,
    workspace: str,
    name: str,
    architecture: str,
    export_path: Optional[str] = None
) -> RunResult:
    """Run all tasks in a session in parallel."""
    started_at = datetime.now().isoformat()
    
    erc = ERC3()
    status = erc.session_status(session_id)
    
    print(f"Session {session_id}: {len(status.tasks)} tasks")
    
    for task in status.tasks:
        erc.start_task(task)
    
    lf = get_client()
    trace_id = lf.get_current_trace_id()
    parent_obs_id = lf.get_current_observation_id()
    
    with ThreadPoolExecutor(max_workers=len(status.tasks)) as executor:
        futures = {
            executor.submit(
                run_agent, erc, task, benchmark,
                langfuse_trace_id=trace_id,
                langfuse_parent_observation_id=parent_obs_id,
            ): task
            for task in status.tasks
        }
        
        # Collect results (unordered)
        all_results = []
        for future in as_completed(futures):
            task = futures[future]
            result = future.result()
            all_results.append(result)
            
            # Print immediately as task completes
            status_icon = "✓" if result.get("score") == 1.0 else "✗"
            logs = f"\n  {result['eval_logs']}" if result.get("eval_logs") else ""
            print(f"{status_icon} Task #{task.num+1}: {task.task_text[:60]}\n  Score: {result.get('score', 'N/A')}{logs}")
    
    erc.submit_session(session_id)
    
    # Convert to TaskResult objects and sort by task_index
    task_results = [TaskResult(**r) for r in all_results]
    task_results.sort(key=lambda r: r.task_index)
    
    # Calculate meta
    total_score = sum(r.score for r in task_results if r.score is not None)
    num_tasks = len(task_results)
    num_scored = sum(1 for r in task_results if r.score is not None)
    avg_score = total_score / num_scored if num_scored > 0 else 0.0
    task_indices = sorted(set(r.task_index for r in task_results))
    
    print(f"{'#'*30}\nSession: {total_score}/{num_scored}\n{'#'*30}")
    lf.score_current_span(
        name="session-score",
        value=avg_score,
        data_type="NUMERIC",
        comment=f"{total_score}/{num_scored}"
    )
    
    meta = RunMeta(
        benchmark=benchmark,
        task_indices=task_indices,
        num_runs=1,
        session_id=session_id,
        total_score=total_score,
        num_tasks=num_tasks,
        avg_score=avg_score,
        workspace=workspace,
        name=name,
        architecture=architecture,
        started_at=started_at,
    )
    
    result = RunResult(results=task_results, meta=meta)
    
    # Export results if path provided
    if export_path:
        _save_results(result, export_path, "run_session")
    
    return result


@observe()
def create_and_run_session(
    benchmark: str,
    workspace: str = "test",
    name: str = "I.R.",
    architecture: str = "Multiagent oss-120b",
    export_path: Optional[str] = None
) -> RunResult:
    """
    Create a new session and run all tasks.
    
    Args:
        benchmark: Benchmark name (e.g., "store")
        workspace: Workspace name (default: "test")
        name: Session name (default: "I.R.")
        architecture: Architecture description (default: "Multiagent oss-120b")
        export_path: Optional path to save results as JSON
    
    Returns:
        RunResult with all results sorted by task_index, and consistent meta
    """
    erc = ERC3()
    session = erc.start_session(
        benchmark=benchmark,
        workspace=workspace,
        name=name,
        architecture=architecture
    )
    print(f"Created session {session.session_id} with {session.task_count} tasks")
    return _run_session(benchmark, session.session_id, workspace, name, architecture, export_path)
