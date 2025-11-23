from erc_utilities import run_task_once, repeat_task, repeat_tasks, create_and_run_session


# Convenience exports
all_store_tasks = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]

# Example usage:
# result = run_task_once(benchmark="store", task_index=1)
# results = repeat_task(benchmark="store", task_index=1, num_times=5)
# results = repeat_tasks(benchmark="store", task_indices=[9], num_times=10)
# results = repeat_tasks(benchmark="store", task_indices=all_store_tasks, num_times=5)
# result = create_and_run_session(benchmark="store", workspace="my")