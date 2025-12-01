"""
ERC3 benchmark SDK tool execution.

Contains ERC3-specific tool implementations:
- execute_erc3_tools(): Main entry point for tool execution
- execute_single_call(): Single SDK call execution

Uses shared execute_sdk_call from infrastructure for core SDK dispatch.
"""

from infrastructure import execute_sdk_call


# ============================================================================
# SINGLE CALL EXECUTION
# ============================================================================

def execute_single_call(function, benchmark_client) -> dict:
    """
    Execute a single SDK tool call for ERC3 benchmark.
    
    Args:
        function: SDK request object or custom wrapper tool
        benchmark_client: SDK client for API calls
    
    Returns:
        dict with:
        - "text": formatted response string for conversation log
        - "tool_call": {request, response} dict for trace
    """
    # TODO: Add wrapper tool routing here when needed
    # if hasattr(function, 'tool'):
    #     if function.tool == "some_wrapper":
    #         return execute_some_wrapper(function, benchmark_client)
    
    # Standard SDK dispatch via shared infrastructure
    return execute_sdk_call(function, benchmark_client)


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def execute_erc3_tools(job, benchmark_client) -> dict:
    """
    Execute SDK tool(s) for ERC3 benchmark.
    
    This is the main entry point called by run_agent_loop via tool_executor.
    Currently only supports single call mode.
    
    Args:
        job: Parsed LLM output with call.function
        benchmark_client: SDK client for ERC3 API calls
    
    Returns:
        dict with:
        - "text": Formatted response for conversation
        - "tool_calls": List of {request, response} dicts for trace
        - "function": The function executed (for display)
    """
    if job.call.call_mode == "single":
        function = job.call.function
        result = execute_single_call(function, benchmark_client)
        return {
            "text": result["text"],
            "tool_calls": [result["tool_call"]],
            "function": function,
        }
    else:
        raise ValueError(f"Unsupported call_mode for ERC3: {job.call.call_mode}")
