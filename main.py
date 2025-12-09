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
# result = repeat_tasks(benchmark="store", task_indices=[4], num_times=1, export_path=export_path)

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

# result = repeat_tasks(benchmark="erc3-test",task_indices=[1, 23],num_times=1, export_path=export_path)
# result = repeat_tasks(benchmark="erc3-test",task_indices=[7, 8, 11, 13, 17, 18, 21, 22, 23],num_times=5, export_path=export_path)
# print(f"Score: {result.meta.total_score}/{result.meta.num_tasks}")
# result = create_and_run_session(benchmark="erc3-test", export_path=export_path)
result = create_and_run_session(benchmark="erc3-prod", export_path=export_path)
# result = repeat_tasks(benchmark="erc3-prod", task_indices=[46], num_times=2, export_path=export_path)

# if __name__ == "__main__":
#     result = repeat_tasks(benchmark="erc3-test", task_indices=[20], num_times=5, export_path=export_path)