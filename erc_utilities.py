from ai_agent import run_agent
from typing import Any, List, Callable
from concurrent.futures import ThreadPoolExecutor
import matplotlib.pyplot as plt
from erc3 import ERC3, TaskInfo
from langfuse import observe, get_client


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
def run_task_once(benchmark: str, task_index: int, **_lf: Any) -> dict:
    """Create and run a single task instance."""
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
def repeat_task(benchmark: str, task_index: int, num_times: int) -> dict:
    """Run same task spec multiple times in parallel."""
    results = _run_parallel(
        lambda _, **kw: run_task_once(benchmark, task_index, **kw),
        range(num_times)
    )
    
    total_score = sum(r["score"] for r in results if r["score"] is not None)
    task_text = results[0]["task_text"] if results else "Unknown"
    print(f"{"#"*30}\nTask {task_index+1}: {task_text}\nTotal: {total_score}/{len(results)}\n{"#"*30}")
    
    lf = get_client()
    lf.score_current_span(
        name="avg-score",
        value=total_score/len(results),
        data_type="NUMERIC",
        comment=f"{total_score}/{len(results)} tasks"
    )
    
    return {"results": results, "total_score": total_score}


def _visualize_task_scores(task_scores: dict, max_score: int):
    """Visualize task scores with adaptive figure width."""
    # Visual parameters (easy to tune)
    BAR_WIDTH = 0.8          # Bar width in data units (matplotlib default)
    INCHES_PER_BAR = 0.8     # How many inches of figure per bar
    MARGIN_INCHES = 2        # Extra space for y-axis labels, margins
    
    # Prepare data
    import textwrap
    categories = [f"Task {idx+1}:\n{textwrap.fill(task_scores[idx]['task_text'][:80], width=16)}" for idx in task_scores.keys()]
    values = [task_scores[idx]["total_score"] for idx in task_scores.keys()]
    
    # Calculate dynamic figure width
    num_bars = len(categories)
    fig_width = num_bars * INCHES_PER_BAR + MARGIN_INCHES
    
    # Create figure with dynamic width
    plt.figure(figsize=(fig_width, 6), dpi=150)
    
    # Create bar chart
    plt.bar(categories, values, width=BAR_WIDTH)
    plt.axhline(y=max_score, linestyle='-')
    plt.ylim(0, max_score * 1.15)
    plt.title('Agent reliability by task')
    plt.xticks(fontsize=6)
    # Adjust layout to prevent cutoff
    plt.tight_layout()
    plt.show()


@observe()
def repeat_tasks(benchmark: str, task_indices: List[int], num_times: int) -> dict:
    """Run multiple task specs, each N times in parallel."""
    task_results = {
        idx: repeat_task(benchmark, idx, num_times)
        for idx in task_indices
    }
    
    # Visualization data
    task_scores = {
        idx: {
            "task_index": idx,
            "task_text": result["results"][0]["task_text"] if result["results"] else "",
            "total_score": result["total_score"]
        }
        for idx, result in task_results.items()
    }
    
    # Visualize
    _visualize_task_scores(task_scores, num_times)
    
    return {"task_results": task_results, "task_scores": task_scores}


@observe()
def run_session(benchmark: str, session_id: str) -> dict:
    """Run all tasks in a session in parallel."""
    erc = ERC3()
    status = erc.session_status(session_id)
    
    print(f"Session {session_id}: {len(status.tasks)} tasks")
    
    for task in status.tasks:
        erc.start_task(task)
    
    lf = get_client()
    trace_id = lf.get_current_trace_id()
    parent_obs_id = lf.get_current_observation_id()
    
    from concurrent.futures import as_completed
    
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
        results_temp = {}
        for future in as_completed(futures):
            task = futures[future]
            result = future.result()
            results_temp[task.task_id] = result
            
            # Print immediately as task completes
            status_icon = "✓" if result.get("score") == 1.0 else "✗"
            logs = f"\n  {result['eval_logs']}" if result.get("eval_logs") else ""
            print(f"{status_icon} Task #{task.num+1}: {task.task_text[:60]}\n  Score: {result.get('score', 'N/A')}{logs}")
    
    # Rebuild task_results in original task order
    task_results = {task.task_id: results_temp[task.task_id] for task in status.tasks}
    
    erc.submit_session(session_id)
    
    # Summary
    total_score = sum(r["score"] for r in task_results.values() if r["score"] is not None)
    num_scored = sum(1 for r in task_results.values() if r["score"] is not None)
    
    print(f"{"#"*30}\nSession: {total_score}/{num_scored}\n{"#"*30}")
    lf.score_current_span(
        name="session-score",
        value=total_score/num_scored if num_scored > 0 else 0,
        data_type="NUMERIC",
        comment=f"{total_score}/{num_scored}"
    )
    
    return {
        "session_id": session_id,
        "benchmark": benchmark,
        "total_score": total_score,
        "num_tasks": len(status.tasks),
        "task_results": task_results
    }


@observe()
def create_and_run_session(benchmark: str, workspace: str = "my", name: str = "AI Agent", architecture: str = "") -> dict:
    """Create a new session and run all tasks."""
    erc = ERC3()
    session = erc.start_session(benchmark=benchmark, workspace=workspace, name=name, architecture=architecture)
    print(f"Created session {session.session_id} with {session.task_count} tasks")
    return run_session(benchmark, session.session_id)

