"""
ERC3 benchmark runner - TO BE IMPLEMENTED.

Entry point for ERC3 benchmark execution. Will handle:
- Agent setup and configuration
- Task completion via provide_agent_response
- Link tracking for grounding
- Error handling
"""

from erc3 import ERC3, TaskInfo


def run_erc3_benchmark(erc_client: ERC3, task: TaskInfo) -> dict:
    """
    Entry point for ERC3 benchmark execution.
    
    Args:
        erc_client: ERC3 client for task completion API
        task: Task to run
    
    Returns:
        Result dict including trace of all events.
    """
    raise NotImplementedError("ERC3 benchmark not yet implemented")

