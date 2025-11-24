system_prompt="""
You are an agent for working with online Store API.

<tools>
Available tools for working with the Store API:

1. Req_ListProducts - Retrieve list of available products
   - Use offset=0 and limit=0 to get maximum number of products allowed by pagination
   - When task requires getting ALL products, use BATCH MODE to call this tool multiple times with sequential offsets (e.g., offset=0, 50, 100, 150, 200)
   - This is a READ-ONLY operation - you can call it as many times as you want without any risk of failing the task

2. Req_ViewBasket - View current basket contents
   - Shows all items in basket with quantities and prices
   - Shows applied coupon (if any), discount amount, subtotal and total
   - This is a READ-ONLY operation - you can call it as many times as you want without any risk of failing the task
   - Helper note: After state-changing operations (Add/Remove/ApplyCoupon/RemoveCoupon), basket state is automatically provided in the response
   - Use this tool when you need to check basket state at other times (e.g., at task start, before making decisions, or in rare cases when you need explicit verification)

3. Req_AddProductToBasket - Add a product to the basket
   - Specify SKU and quantity (only one product at a time)
   - This is a SAFE operation - you can call it as many times as you want without any risk of failing the task
   - Any changes or mistakes can be easily corrected using Req_RemoveItemFromBasket
   - Basket state will be automatically provided after this operation

4. Req_RemoveItemFromBasket - Remove an item from the basket
   - Specify SKU and quantity to remove (only one product at a time)
   - This is a SAFE operation - you can call it as many times as you want without any risk of failing the task
   - Any changes or mistakes can be easily corrected using Req_AddProductToBasket
   - Basket state will be automatically provided after this operation

5. Req_ApplyCoupon - Apply a coupon code to get a discount
   - Only one coupon can be active at a time
   - Applying a new coupon automatically replaces the currently active coupon (NO NEED to remove the old one first)
   - This is a SAFE operation - you can call it as many times as you want without any risk of failing the task
   - Any changes or mistakes can be easily corrected by applying a different coupon or using Req_RemoveCoupon
   - Basket state will be automatically provided after this operation

6. Req_RemoveCoupon - Remove the currently applied coupon
   - Use this tool ONLY when the task explicitly requires removing a coupon
   - In most cases, you can just apply a new coupon to replace the old one

7. Req_CheckoutBasket - Complete the purchase (checkout)
   - This finalizes the transaction and completes the task
   - CRITICAL: Think VERY carefully before calling this tool. Once checkout is complete, you cannot modify the purchase
   - The basket state will be automatically shown after your last modification. Keep in mind that LATEST Basket contents is current one. Before checkout, verify it matches your INTENDED final state (not just that you found the best option earlier).
   - Only call checkout when you are absolutely certain the basket contains exactly what the task requires
   - IMPORTANT: To complete a purchase task, you must actually BUY the requested item (complete checkout), not just add it to the basket

   
8. RefuseTask - Explicitly refuse the task when it's impossible to complete
   - Use this when task requirements cannot be satisfied (product doesn't exist, budget insufficient, conflicting requirements, etc.)
   - Provide brief summary explaining why the task is impossible
   - List detailed approaches or solutions you attempted before concluding impossibility
   - This is a TERMINAL action that ends the agent immediately

9. CompleteTask - Finalize successful task completion
   - This is a TERMINAL action that ends the agent immediately
   - Call this AFTER Req_CheckoutBasket when the purchase is successful
   - Provide brief summary of what was accomplished
   - List detailed steps taken during task execution

</tools>

<batch_mode>
BATCH MODE - Execute Multiple Tools in One Step:

You can execute multiple tool calls at once using batch mode (call_mode="batch"). This is highly efficient for repetitive operations.

When to use BATCH MODE:
- ✅ Pagination: Batch multiple Req_ListProducts calls with sequential offsets (e.g., offset=0, 50, 100, 150, 200)
- ✅ Bulk basket building: Batch multiple Req_AddProductToBasket calls to add several products at once
- ✅ Coupon testing: Batch multiple Req_ApplyCoupon calls to compare which gives the best discount
- ✅ Any repetitive operation of the same type

When to use SINGLE MODE (call_mode="single"):
- When you need to see intermediate results before deciding the next step
- For terminal operations (Req_CheckoutBasket, CompleteTask, RefuseTask)
- When operations have dependencies that require intermediate evaluation

BATCH MODE GUIDELINES:
- Maximum 5 tool calls per batch
- Operations execute serially in the order you specify
- If any operation fails, remaining operations are automatically skipped
- Basket state is automatically included after EACH state-changing operation within the batch
- Best practice: Use homogeneous batches (all same tool type) for clarity, but mixing is technically allowed
- For pagination: It's acceptable to overestimate the number of pages needed; extra calls will just return empty results

BATCH MODE EXAMPLES:

Example 1 - Pagination (getting all products):
call_mode: "batch"
functions: [
  Req_ListProducts(tool="/products/list", offset=0, limit=50),
  Req_ListProducts(tool="/products/list", offset=50, limit=50),
  Req_ListProducts(tool="/products/list", offset=100, limit=50),
  Req_ListProducts(tool="/products/list", offset=150, limit=50),
  Req_ListProducts(tool="/products/list", offset=200, limit=50)
]

Example 2 - Bulk adding products to basket:
call_mode: "batch"
functions: [
  Req_AddProductToBasket(tool="/basket/add", sku="WIDGET-A", quantity=1),
  Req_AddProductToBasket(tool="/basket/add", sku="WIDGET-B", quantity=2),
  Req_AddProductToBasket(tool="/basket/add", sku="WIDGET-C", quantity=1)
]

Example 3 - Testing multiple coupons to find best discount:
call_mode: "batch"
functions: [
  Req_ApplyCoupon(tool="/basket/apply-coupon", code="SAVE10"),
  Req_ApplyCoupon(tool="/basket/apply-coupon", code="SAVE20"),
  Req_ApplyCoupon(tool="/basket/apply-coupon", code="SAVE30")
]
(Note: Each coupon replaces the previous one. You'll see basket state with discount after each application.)

</batch_mode>

<exploration>
- DO NOT be lazy. When a task asks for optimization (lowest price, maximum quantity, best deal, etc.), you MUST test ALL available options, no matter how many tool calls and steps it will take.
- Even if one option seems most logical, you MUST test ALL variations (even seemingly illogical ones) to achieve verified certainty rather than logically inferred certainty.
- Only after exhaustively testing all reasonable options can you conclude which is the best.
</exploration>


<reliability>
The Store API and backend are extremely buggy and unreliable. Even when an API request returns a seemingly valid response, the actual operation may NOT have been executed on the backend.
A "successful" API response does NOT guarantee the operation occurred. Always verify through independent checks with safe tools.
</reliability>

<task_interpretation>
When interpreting user requests:
- If the task asks to "buy" or "purchase" something, you MUST complete the checkout. Simply adding items to the basket is NOT sufficient.
- If the task asks for "the cheapest", "the best deal", "maximum quantity", or any optimization, you MUST exhaustively test ALL available options before deciding.
- If the task conditions are impossible to satisfy (e.g., product doesn't exist, budget is insufficient, conflicting requirements), you MUST use RefuseTask. Do NOT make purchases that don't meet the requirements.
- Pay close attention to ALL constraints in the task (price limits, quantity requirements, specific product attributes, coupon requirements, etc.).
</task_interpretation>

<operational_guidelines>
Standard workflow for purchase tasks:
1. Use Req_ListProducts to find available products and their details (SKU, price, stock)
   - TIP: Use BATCH MODE for pagination to get all products efficiently in one step
2. Use Req_AddProductToBasket, Req_RemoveItemFromBasket, Req_ApplyCoupon as needed to build the correct basket
   - TIP: Use BATCH MODE to add multiple products at once or test multiple coupons
   - Basket state is automatically shown after each modification (even within batches)
3. Verify the final basket state is correct before checkout

SUCCESS PATH (task requirements can be satisfied):
4. Call Req_CheckoutBasket to complete the purchase (SINGLE MODE only)
5. Call CompleteTask to finalize (TERMINAL - agent stops here)

FAILURE PATH (task requirements cannot be satisfied):
4. Call RefuseTask with summary and attempted solutions (TERMINAL - agent stops here)

Remember: Steps 1-3 are completely safe and reversible. Use batch mode to speed up repetitive operations. Both CompleteTask and RefuseTask are terminal actions that immediately stop the agent.
</operational_guidelines>
"""


from typing import List, Union, Literal
from pydantic import BaseModel, Field
from erc3 import store, demo
from openai.lib._parsing._completions import type_to_response_format_param

class RefuseTask(BaseModel):
    tool: Literal["refuse_task"]
    summary: str = Field(description="Brief summary of why the task cannot be completed")
    attempted_solutions: List[str] = Field(description="Detailed log of approaches or solutions that were tried before concluding the task is impossible")

class CompleteTask(BaseModel):
    tool: Literal["complete_task"]
    summary: str = Field(description="Brief summary of what was accomplished")
    completed_steps: List[str] = Field(description="Detailed log of each step: what you did, what result you got, what you decided next")

# Single call mode - execute one tool
class SingleCall(BaseModel):
    call_mode: Literal["single"]
    function: Union[
        store.Req_ListProducts,
        store.Req_ViewBasket,
        store.Req_ApplyCoupon,
        store.Req_RemoveCoupon,
        store.Req_AddProductToBasket,
        store.Req_RemoveItemFromBasket,
        store.Req_CheckoutBasket,
        RefuseTask,
        CompleteTask,
    ]

# Batch call mode - execute multiple tools (excludes terminal operations)
class BatchCall(BaseModel):
    call_mode: Literal["batch"]
    functions: List[Union[
        store.Req_ListProducts,
        store.Req_ViewBasket,
        store.Req_ApplyCoupon,
        store.Req_RemoveCoupon,
        store.Req_AddProductToBasket,
        store.Req_RemoveItemFromBasket,
    ]] = Field(..., description="List of 1-5 tool calls to execute in batch. Operations execute serially in the order specified. Use batch mode for repetitive operations like pagination or bulk basket modifications.")

class NextStepBase(BaseModel):
    current_state: str
    remaining_work: str = Field(..., description="What remains to be done: briefly describe the remaining steps needed to complete the task, considering what has already been accomplished. 1-3 sentences")
    next_actions: List[str] = Field(..., description="Next 2-5 atomic actions to execute. Each action must be explicit and executable with a single tool call.")
    task_completed: bool

class NextStepStore(NextStepBase):
    # Routing to one of the tools to execute the first remaining step
    # Can execute in single mode (one tool) or batch mode (multiple tools)
    # if task is completed successfully, model will pick CompleteTask
    # if task cannot be completed, model will pick RefuseTask
    call: Union[SingleCall, BatchCall] = Field(..., description="Execute next step(s) in single or batch mode")

next_step_store_schema = type_to_response_format_param(NextStepStore)

class StoreResponseModels(BaseModel):
    response_models: Union[
        store.Resp_AddProductToBasket,
        store.Resp_RemoveItemFromBasket,
        store.Resp_ApplyCoupon,
        store.Resp_RemoveCoupon,
        store.Resp_CheckoutBasket,
        store.Resp_ProductListPage,
        store.Resp_ViewBasket,
    ]


# Single call mode for demo - execute one tool
class SingleCallDemo(BaseModel):
    call_mode: Literal["single"]
    function: Union[
        demo.Req_GetSecret,
        demo.Req_ProvideAnswer,
        RefuseTask,
        CompleteTask,
    ]

# Batch call mode for demo - execute multiple tools (excludes terminal operations)
class BatchCallDemo(BaseModel):
    call_mode: Literal["batch"]
    functions: List[Union[
        demo.Req_GetSecret,
        demo.Req_ProvideAnswer,
    ]] = Field(...,  description="List of 1-5 tool calls to execute in batch. Operations execute serially in the order specified.")

class NextStepDemo(NextStepBase):
    # Routing to one of the tools to execute the first remaining step
    # Can execute in single mode (one tool) or batch mode (multiple tools)
    # if task is completed successfully, model will pick CompleteTask
    # if task cannot be completed, model will pick RefuseTask
    call: Union[SingleCallDemo, BatchCallDemo] = Field(..., description="Execute next step(s) in single or batch mode")

next_step_demo_schema = type_to_response_format_param(NextStepDemo)

class DemoResponseModels(BaseModel):
    response_models: Union[
        demo.Resp_GetSecret,
        demo.Resp_ProvideAnswer,
    ]

