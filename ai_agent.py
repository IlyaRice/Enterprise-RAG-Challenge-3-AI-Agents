import time
import concurrent.futures
from langfuse import get_client
from typing import List, Union
import json
import config
from prompts import system_prompt, NextStepStore, NextStepDemo, CompleteTask, RefuseTask
from utilities import calculate_reasoning_and_output
from erc3 import store, ApiException, TaskInfo, ERC3, demo
from langfuse.openai import OpenAI
# from openai import OpenAI
from langfuse import observe, get_client
from openai.lib._parsing._completions import type_to_response_format_param
from pydantic import BaseModel, Field

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=config.OPENROUTER_API_KEY
)

def append_basket_state_if_needed(job_function, benchmark_client, benchmark: str, original_txt: str) -> str:
    """
    Automatically append basket state after state-changing operations.
    Returns modified txt with basket contents appended if applicable.
    """
    # Only apply to store benchmark and specific state-changing operations
    if benchmark != "store":
        return original_txt
    
    state_changing_ops = (
        store.Req_ApplyCoupon,
        store.Req_RemoveCoupon,
        store.Req_AddProductToBasket,
        store.Req_RemoveItemFromBasket
    )
    
    if not isinstance(job_function, state_changing_ops):
        return original_txt
    
    # Attempt to fetch current basket state
    try:
        basket_result = benchmark_client.dispatch(store.Req_ViewBasket(tool="/basket/view"))
        basket_json = basket_result.model_dump_json(exclude_none=True, exclude_unset=True)
        return f"{original_txt}\n\nBasket contents:\n{basket_json}"
    except ApiException as e:
        error_msg = e.api_error.error if hasattr(e, 'api_error') else str(e)
        return f"{original_txt}\n\nBasket contents:\n[Error fetching basket: {error_msg}. Please use Req_ViewBasket manually to verify.]"
    except Exception as e:
        return f"{original_txt}\n\nBasket contents:\n[Error fetching basket: {str(e)}. Please use Req_ViewBasket manually to verify.]"

def dispatch_with_timeout(benchmark_client, function, timeout_seconds=30):
    """Execute SDK dispatch with timeout protection."""
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(benchmark_client.dispatch, function)
        try:
            return future.result(timeout=timeout_seconds)
        except concurrent.futures.TimeoutError:
            raise TimeoutError(f"SDK operation timed out after {timeout_seconds} seconds")

def execute_batch(functions_list, benchmark_client, benchmark: str) -> str:
    """
    Execute a batch of functions serially with fail-fast error handling.
    Returns formatted string with all request/response pairs until completion or error.
    """
    results = []
    total_functions = len(functions_list)
    
    for idx, function in enumerate(functions_list, 1):
        # Format the request
        request_json = function.model_dump_json()
        
        # Execute the function
        try:
            result = dispatch_with_timeout(benchmark_client, function)
            response_json = result.model_dump_json(exclude_none=True, exclude_unset=True)
            
            # Auto-append basket state if applicable
            response_with_basket = append_basket_state_if_needed(function, benchmark_client, benchmark, response_json)
            
            # Add to results
            results.append(f"Request:\n`{request_json}`\n\nResponse:\n`{response_with_basket}`")
            
        except TimeoutError as e:
            error_json = f'{{"error": "{str(e)}"}}'
            results.append(f"Request:\n`{request_json}`\n\nResponse:\n`{error_json}`")
            
            # Add abort message
            if idx < total_functions:
                results.append(f"\nThe rest of requests are aborted due to the error.\nExecuted: {idx} out of {total_functions} requested operations.")
            break
            
        except ApiException as e:
            results.append(f"Request:\n`{request_json}`\n\nResponse:\n`{e.detail}`")
            
            # Add abort message
            if idx < total_functions:
                results.append(f"\nThe rest of requests are aborted due to the error.\nExecuted: {idx} out of {total_functions} requested operations.")
            break
    
    # Join all results with separators
    return "\n\n---\n\n".join(results)

def handle_task_completion(function, task: TaskInfo, erc_client: ERC3, verbose: bool) -> dict:
    """
    Handle CompleteTask or RefuseTask terminal actions and return final result.
    """
    # Determine success/failure and extract details
    if isinstance(function, CompleteTask):
        code = "completed"
        summary_text = function.summary
        details = function.completed_steps
        if verbose:
            print(f"Agent completed successfully. Summary: {summary_text}")
            print("\n".join(details))
    else:  # RefuseTask
        code = "failed"
        summary_text = function.summary
        details = function.attempted_solutions
        if verbose:
            print(f"Agent refused task. Reason: {summary_text}")
            print("\n".join(details))

    # Complete task and get evaluation
    completion = erc_client.complete_task(task)
    
    score = completion.eval.score if completion.eval else None
    eval_logs = completion.eval.logs if completion.eval else None
    
    lf = get_client()
    lf.score_current_span(name="score", value=score, data_type="NUMERIC", comment=eval_logs)

    return {
        "task_id": task.task_id,
        "task_text": task.task_text,
        "code": code,
        "summary": [summary_text] + details,
        "score": score,
        "eval_logs": eval_logs
    }

def execute_single_call(function, benchmark_client, benchmark: str, verbose: bool) -> str:
    """
    Execute a single tool call and return formatted text for logging.
    """
    try:
        result = dispatch_with_timeout(benchmark_client, function)
        txt = result.model_dump_json(exclude_none=True, exclude_unset=True)
        if verbose:
            print(f"OUT: {txt}")
    except TimeoutError as e:
        txt = f'{{"error": "{str(e)}"}}'
        if verbose:
            print(f"ERR: {str(e)}")
    except ApiException as e:
        txt = e.detail
        if verbose:
            print(f"ERR: {e.api_error.error}")

    # Automatically append basket state after state-changing operations
    txt = append_basket_state_if_needed(function, benchmark_client, benchmark, txt)
    
    return txt

observe()
def get_next_step(next_step_schema: BaseModel, log: List[dict]) -> Union[NextStepStore, NextStepDemo]:
    
    messages = []
    for msg in log:
        if msg["role"] == "system":
            messages.append({"role": "system", "content": msg["content"]})
        elif msg["role"] == "user":
            messages.append({"role": "user", "content": msg["content"]})
        elif msg["role"] == "assistant":
            messages.append({"role": "assistant", "content": msg["content"]})
            
    schema = type_to_response_format_param(next_step_schema)
    
    # Retry logic for rare LLM failures (empty responses)
    for attempt in range(3):
        try:
            llm_start = time.time()
            
            lf = get_client()
            with lf.start_as_current_generation(name="next-step-generation") as gen:
                response = client.chat.completions.create(
                        model="openai/gpt-oss-120b",
                        messages=messages,
                        response_format=schema,
                        extra_body={
                            "provider": {
                                "only": ["Cerebras"]
                            },
                        },
                    )

                reasoning=response.choices[0].message.reasoning
                gen.update(metadata={"reasoning":reasoning, "attempt": attempt + 1})
            
            llm_duration = time.time() - llm_start
            if config.VERBOSE:
                print(f"Step {len(log)} completed in {llm_duration:.2f}s" + (f" (retry {attempt})" if attempt > 0 else ""))
            
            content = response.choices[0].message.content
            parsed = next_step_schema.model_validate_json(content)
            
            return parsed
            
        except Exception as e:
            if attempt < 2:
                print(f"  ⚠ Retry {attempt + 1}/2 (error: {type(e).__name__})")
                time.sleep(0.5)
            else:
                raise

@observe()
def run_agent(erc_client: ERC3, task: TaskInfo, benchmark: str) -> dict:
    
    if benchmark == "store":
        benchmark_client = erc_client.get_store_client(task)
        next_step_schema = NextStepStore
    elif benchmark == "demo":
        benchmark_client = erc_client.get_demo_client(task)
        next_step_schema = NextStepDemo
    else:
        raise ValueError(f"Unknown benchmark: {benchmark}")

    schema = type_to_response_format_param(next_step_schema)
    system_prompt_with_schema = f"{system_prompt}\n\nFollow this schema when answering: {json.dumps(schema)}"

    # log will contain conversation context for the agent within task
    log = [
        {"role": "system", "content": system_prompt_with_schema},
        {"role": "user", "content": task.task_text},
    ]
    
    # let's limit number of reasoning steps by 100, just to be safe
    for i in range(100):
        step = f"step_{i + 1}"
        if config.VERBOSE:
            print(f"Next {step}... ", end="")

        job = get_next_step(next_step_schema, log)

        # Check if this is a single call or batch call
        if job.call.call_mode == "single":
            # Single mode execution
            function_to_execute = job.call.function
            
            # Handle terminal actions (CompleteTask, RefuseTask)
            if isinstance(function_to_execute, (CompleteTask, RefuseTask)):
                return handle_task_completion(function_to_execute, task, erc_client, config.VERBOSE)
            
            # Regular single tool execution
            next_planned_step = job.next_actions[0] if job.next_actions else "No plan provided"
            if config.VERBOSE:
                print(f"{next_planned_step}", f"\n  {function_to_execute}")

            # Execute the tool
            txt = execute_single_call(function_to_execute, benchmark_client, benchmark, config.VERBOSE)

            # Add to conversation log
            log.append({
                "role": "assistant",
                "content": f'Planned step:\n"{next_planned_step}"\n\nRequest:\n`{function_to_execute.model_dump_json()}`\n\nResponse:\n`{txt}`'
            })
            
        elif job.call.call_mode == "batch":
            # Batch mode execution
            functions_to_execute = job.call.functions
            
            # Print debug info
            next_planned_step = job.next_actions[0] if job.next_actions else "No plan provided"
            if config.VERBOSE:
                print(f"{next_planned_step}")
                print(f"  BATCH MODE: Executing {len(functions_to_execute)} functions")
                for idx, func in enumerate(functions_to_execute, 1):
                    print(f"    {idx}. {func}")

            # Execute batch
            txt = execute_batch(functions_to_execute, benchmark_client, benchmark)
            
            if config.VERBOSE:
                print(f"BATCH OUT: {len(functions_to_execute)} operations completed/attempted")

            # Add to conversation log
            log.append({
                "role": "assistant",
                "content": f'Planned step:\n"{next_planned_step}"\n\n{txt}'
            })
    
    # Timeout - complete task anyway
    completion = erc_client.complete_task(task)
    
    return {
    "task_id": task.task_id,
    "task_text": task.task_text,
    "code": "timeout",
    "summary": ["Task exceeded maximum steps limit"],
    "score": completion.eval.score if completion.eval else None,
    "eval_logs": completion.eval.logs if completion.eval else None
}