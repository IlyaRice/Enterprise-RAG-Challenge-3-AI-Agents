"""
AI Agent main entry point module.

This is a thin router that dispatches to benchmark-specific implementations.
Each benchmark has its own runner in benchmarks/<name>/runner.py.

Contains:
- run_agent() - main entry point that routes to benchmark-specific runners
"""

from langfuse import observe
from erc3 import TaskInfo, ERC3
import config

@observe()
def run_agent(erc_client: ERC3, task: TaskInfo, benchmark: str) -> dict:
    """
    Main entry point for running an agent on a task.
    
    Routes to the appropriate benchmark-specific runner.
    
    Args:
        erc_client: ERC3 client for API access
        task: Task to run
        benchmark: Benchmark name ("store", "erc3", "erc3-dev", "erc3-test")
    
    Returns:
        Result dict including trace of all events.
    """
    if benchmark == "store":
        from benchmarks.store import run_store_benchmark
        return run_store_benchmark(erc_client, task)
    elif benchmark.startswith("erc3"):
        from benchmarks.erc3 import run_erc3_benchmark
        return run_erc3_benchmark(erc_client, task)
    else:
        raise ValueError(f"Unknown benchmark: {benchmark}. Supported: 'store', 'erc3*'")
