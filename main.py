import config
config.VERBOSE = 0
from erc_utilities import repeat_tasks, create_and_run_session, TaskResult, RunResult

export_path = config.TRACES_EXPORT_PATH

# Convenience exports
all_store_tasks = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]

# ============================================================================
# USAGE EXAMPLES
# ============================================================================
# Both functions return RunResult with:
#   - results: List[TaskResult] sorted by task_index
#   - meta: RunMeta with benchmark, task_indices, num_runs, session_id,
#           total_score, num_tasks, avg_score, workspace, name, architecture, started_at

# Run single task once:
# result = repeat_tasks(benchmark="store", task_indices=[2], num_times=3, export_path=export_path)

# Run single task 5 times (reliability test):
# result = repeat_tasks(benchmark="store", task_indices=[2, 12], num_times=5, export_path=export_path)

# Run multiple tasks
# result = repeat_tasks(benchmark="store", task_indices=[1, 2, 6, 7 ,8, 11, 12], num_times=1, export_path=export_path)

# Run all tasks once:
# result = repeat_tasks(benchmark="store", task_indices=all_store_tasks, num_times=5, export_path=export_path)

# Run competition session:
# result = create_and_run_session(benchmark="store", export_path=export_path)
# for i in range(5):
#     result = create_and_run_session(benchmark="store", export_path=export_path)

# ============================================================================
# WORKING WITH RESULTS
# ============================================================================
# result.meta.total_score      # Sum of all scores
# result.meta.avg_score        # Average score
# result.meta.num_tasks        # Total number of task runs
# result.meta.session_id       # Session ID (None for repeat_tasks)
# result.meta.workspace        # Workspace name
# result.meta.name             # Run name
# result.meta.architecture     # Architecture description
# result.meta.started_at       # ISO 8601 timestamp: "2025-11-28T15:30:45.123456"

# Iterate over results:
# for task_result in result.results:
#     print(f"Task {task_result.task_index}: {task_result.score}")
#     print(format_orchestrator_pov(task_result.model_dump()))
