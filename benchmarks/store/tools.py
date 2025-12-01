"""
Store benchmark SDK tool execution.

Contains store-specific tool implementations:
- execute_store_tools(): Main entry point for tool execution
- execute_single_call(): Single SDK call execution
- execute_batch(): Batch SDK call execution  
- execute_get_all_products(): Pagination wrapper for product listing
- execute_set_basket(): Complex basket management wrapper
"""

from erc3 import store, ApiException
from infrastructure import dispatch_with_timeout, execute_sdk_call


# ============================================================================
# STORE-SPECIFIC HELPERS
# ============================================================================

def append_basket_state_if_needed(job_function, benchmark_client, original_txt: str) -> str:
    """
    Automatically append basket state after state-changing operations.
    
    This is a wrapper behavior that fetches basket state after operations
    that modify it, providing the agent with immediate feedback.
    
    Returns:
        Modified txt with basket contents appended if applicable.
    """
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


# ============================================================================
# GET ALL PRODUCTS WRAPPER
# ============================================================================

def execute_get_all_products(function, benchmark_client) -> dict:
    """
    Fetch all products from the catalog with automatic pagination.
    
    Args:
        function: Req_GetAllProducts instance
        benchmark_client: SDK client for API calls
    
    Returns:
        dict with:
        - "text": formatted product list for conversation log
        - "tool_call": {request, response} dict for trace
    
    Raises:
        ApiException: If any pagination call fails (fail-fast, no partial results)
    """
    all_products = []
    offset = 0
    pages_fetched = 0
    
    while True:
        # Fetch next page
        response = benchmark_client.dispatch(store.Req_ListProducts(offset=offset, limit=0))
        pages_fetched += 1
        
        products_in_page = response.products or []
        all_products.extend(products_in_page)
        
        # Check if done
        if response.next_offset is None or response.next_offset <= 0:
            break
        
        offset = response.next_offset
    
    # Format response
    return _format_all_products_result(all_products, pages_fetched)


def _format_all_products_result(products: list, pages_fetched: int) -> dict:
    """Format all products into compact readable text and structured data."""
    if not products:
        text = "No products found in catalog."
        return {
            "text": text,
            "tool_call": {
                "request": {"tool": "get_all_products"},
                "response": {"products": [], "pages_fetched": pages_fetched}
            }
        }
    
    # Compact format: one line per product
    lines = ["Products:"]
    for p in products:
        lines.append(f"  {p.sku} | {p.name} | price={p.price} | stock={p.available}")
    
    text = "\n".join(lines)
    
    # Structured response for trace
    products_data = [
        {"sku": p.sku, "name": p.name, "price": p.price, "available": p.available}
        for p in products
    ]
    
    return {
        "text": text,
        "tool_call": {
            "request": {"tool": "get_all_products"},
            "response": {"products": products_data, "pages_fetched": pages_fetched}
        }
    }


# ============================================================================
# SET BASKET WRAPPER
# ============================================================================

def execute_set_basket(function, benchmark_client) -> dict:
    """
    Set basket to exact contents: clear existing, add products, test/apply best coupon.
    
    Steps:
    1. View current basket (to report what was cleared)
    2. Remove all existing products
    3. Remove existing coupon if any
    4. Add new products (fail-fast on error)
    5. Test all coupons if provided, apply best one
    6. View final basket and return formatted result
    
    Args:
        function: Req_SetBasket instance with products list and optional coupons list
        benchmark_client: SDK client for API calls
    
    Returns:
        dict with:
        - "text": human-readable response for conversation log
        - "tool_call": {request, response} dict for trace
    """
    products_to_add = function.products
    coupons_to_test = function.coupons if function.coupons else None
    
    # Track what we're doing for the response
    cleared_products = []
    cleared_coupon = None
    added_products = []
    applied_coupon = None
    coupon_test_results = []
    error_message = None
    
    # Step 1: View current basket to know what to clear
    try:
        current_basket = benchmark_client.dispatch(store.Req_ViewBasket())
        if current_basket.items:
            cleared_products = [
                {"sku": item.sku, "quantity": item.quantity}
                for item in current_basket.items
            ]
        if current_basket.coupon:
            cleared_coupon = current_basket.coupon
    except ApiException as e:
        # If we can't view basket, continue anyway - might be empty
        pass
    
    # Step 2: Remove all existing products
    for item in cleared_products:
        try:
            benchmark_client.dispatch(store.Req_RemoveItemFromBasket(
                sku=item["sku"],
                quantity=item["quantity"]
            ))
        except ApiException as e:
            # Fail-fast on removal error
            error_message = f"Failed to remove {item['sku']}: {e.api_error.error if hasattr(e, 'api_error') else str(e)}"
            return _format_set_basket_result(
                function, cleared_products, cleared_coupon, added_products, 
                applied_coupon, [], 0, error_message, benchmark_client
            )
    
    # Step 3: Remove existing coupon if any
    if cleared_coupon:
        try:
            benchmark_client.dispatch(store.Req_RemoveCoupon())
        except ApiException as e:
            # Fail-fast on coupon removal error
            error_message = f"Failed to remove coupon {cleared_coupon}: {e.api_error.error if hasattr(e, 'api_error') else str(e)}"
            return _format_set_basket_result(
                function, cleared_products, cleared_coupon, added_products,
                applied_coupon, [], 0, error_message, benchmark_client
            )
    
    # Step 4: Add new products (fail-fast)
    for item in products_to_add:
        try:
            benchmark_client.dispatch(store.Req_AddProductToBasket(
                sku=item.sku,
                quantity=item.quantity
            ))
            added_products.append({"sku": item.sku, "quantity": item.quantity})
        except ApiException as e:
            error_message = f"Failed to add {item.sku}: {e.api_error.error if hasattr(e, 'api_error') else str(e)}"
            return _format_set_basket_result(
                function, cleared_products, cleared_coupon, added_products,
                applied_coupon, [], 0, error_message, benchmark_client
            )
    
    # Step 5: Test coupons and apply best one
    best_coupon = None
    best_discount = 0
    
    if coupons_to_test and len(coupons_to_test) > 0:
        for coupon_code in coupons_to_test:
            try:
                # Apply the coupon
                benchmark_client.dispatch(store.Req_ApplyCoupon(coupon=coupon_code))
                # Get basket state to measure discount
                basket = benchmark_client.dispatch(store.Req_ViewBasket())
                
                discount = basket.discount or 0
                subtotal = basket.subtotal
                
                coupon_test_results.append({
                    "coupon": coupon_code,
                    "valid": True,
                    "discount": discount,
                    "subtotal": subtotal,
                    "total": basket.total,
                })
                
                # Track best discount
                if discount > best_discount:
                    best_discount = discount
                    best_coupon = coupon_code
                
                # Remove coupon for next test
                benchmark_client.dispatch(store.Req_RemoveCoupon())
                
            except ApiException as e:
                error_msg = e.api_error.error if hasattr(e, 'api_error') else str(e)
                coupon_test_results.append({
                    "coupon": coupon_code,
                    "valid": False,
                    "error": error_msg,
                })
        
        # Apply best coupon if it provides a discount
        if best_coupon and best_discount > 0:
            try:
                benchmark_client.dispatch(store.Req_ApplyCoupon(coupon=best_coupon))
                applied_coupon = best_coupon
            except ApiException as e:
                # Shouldn't happen since we just tested it successfully, but handle anyway
                error_message = f"Failed to re-apply best coupon {best_coupon}: {e.api_error.error if hasattr(e, 'api_error') else str(e)}"
                return _format_set_basket_result(
                    function, cleared_products, cleared_coupon, added_products,
                    applied_coupon, coupon_test_results, best_discount, error_message, benchmark_client
                )
    
    # Success - format result
    return _format_set_basket_result(
        function, cleared_products, cleared_coupon, added_products,
        applied_coupon, coupon_test_results, best_discount, None, benchmark_client
    )


def _format_set_basket_result(
    function, 
    cleared_products: list, 
    cleared_coupon: str | None,
    added_products: list,
    applied_coupon: str | None,
    coupon_test_results: list,
    best_discount: float,
    error_message: str | None,
    benchmark_client
) -> dict:
    """Format set_basket results into human-readable text and structured data."""
    lines = []
    
    # Report what was cleared
    if cleared_products or cleared_coupon:
        lines.append("Cleared from basket:")
        for p in cleared_products:
            lines.append(f"  - {p['quantity']}x {p['sku']}")
        if cleared_coupon:
            lines.append(f"  - Coupon: {cleared_coupon}")
        if not cleared_products:
            lines.append("  - (no products)")
    else:
        lines.append("Basket was already empty.")
    
    lines.append("")
    
    # Report what was added
    if added_products:
        lines.append("Added to basket:")
        for p in added_products:
            lines.append(f"  - {p['quantity']}x {p['sku']}")
    else:
        lines.append("No products added (basket cleared).")
    
    # Report coupon testing (if coupons were tested)
    if coupon_test_results:
        lines.append("\n" + "=" * 30)
        lines.append("Coupon Test Results:")
        
        for r in coupon_test_results:
            if r["valid"]:
                discount = r["discount"]
                if discount > 0:
                    pct = round(discount / r["subtotal"] * 100, 1) if r.get("subtotal", 0) > 0 else 0
                    lines.append(f"  {r['coupon']}: ${discount} discount ({pct}%), Total: ${r['total']}")
                else:
                    lines.append(f"  {r['coupon']}: Valid but no discount (Total: ${r['total']})")
            else:
                lines.append(f"  {r['coupon']}: Invalid - {r.get('error', 'Unknown error')}")
        
        # Summary of best coupon
        lines.append("")
        if applied_coupon:
            lines.append(f"→ Best coupon applied: {applied_coupon} (saves ${best_discount})")
        else:
            if any(r["valid"] for r in coupon_test_results):
                lines.append("→ No coupon applied (all valid coupons provide zero discount)")
            else:
                lines.append("→ No coupon applied (all coupons invalid)")
    
    # Report error if any
    if error_message:
        lines.append(f"\nERROR: {error_message}")
        lines.append("Operation stopped at this point. Basket may be in partial state.")
    
    # Get final basket state
    lines.append("\n" + "-" * 30)
    lines.append("Final Basket State:")
    try:
        final_basket = benchmark_client.dispatch(store.Req_ViewBasket())
        final_basket_dict = final_basket.model_dump(exclude_none=True)
        
        if final_basket.items:
            for item in final_basket.items:
                lines.append(f"  - {item.quantity}x {item.sku} @ {item.price} each")
            lines.append(f"  Subtotal: {final_basket.subtotal}")
            if final_basket.coupon:
                lines.append(f"  Coupon: {final_basket.coupon}")
            if final_basket.discount:
                lines.append(f"  Discount: -{final_basket.discount}")
            lines.append(f"  Total: {final_basket.total}")
        else:
            lines.append("  (empty)")
            final_basket_dict = {"items": [], "subtotal": 0, "total": 0}
    except Exception as e:
        lines.append(f"  Error fetching final state: {str(e)}")
        final_basket_dict = {"error": str(e)}
    
    text = "\n".join(lines)
    
    # Build request dict from function
    request_dict = {
        "tool": "set_basket",
        "products": [{"sku": p.sku, "quantity": p.quantity} for p in function.products],
        "coupons": function.coupons
    }
    
    # Build response dict
    response_dict = {
        "cleared": {
            "products": cleared_products,
            "coupon": cleared_coupon
        },
        "added": {
            "products": added_products,
        },
        "coupon_tests": coupon_test_results,
        "best_coupon": {
            "coupon": applied_coupon,
            "discount": best_discount
        } if applied_coupon else None,
        "final_basket": final_basket_dict
    }
    if error_message:
        response_dict["error"] = error_message
    
    return {
        "text": text,
        "tool_call": {"request": request_dict, "response": response_dict}
    }


# ============================================================================
# SINGLE AND BATCH EXECUTION
# ============================================================================

def execute_single_call(function, benchmark_client) -> dict:
    """
    Execute a single SDK tool call for store benchmark.
    
    Args:
        function: SDK request object (e.g., store.Req_ProductsList) or custom wrapper tool
        benchmark_client: SDK client for API calls
    
    Returns:
        dict with:
        - "text": formatted response string for conversation log
        - "tool_call": {request, response} dict for trace
    """
    # Handle custom wrapper tools first
    if hasattr(function, 'tool'):
        if function.tool == "get_all_products":
            return execute_get_all_products(function, benchmark_client)
        elif function.tool == "set_basket":
            return execute_set_basket(function, benchmark_client)
    
    # Standard SDK dispatch via shared infrastructure
    result = execute_sdk_call(function, benchmark_client)
    
    # Store-specific: auto-append basket state after state-changing operations
    result["text"] = append_basket_state_if_needed(function, benchmark_client, result["text"])
    
    return result


def execute_batch(functions_list, benchmark_client) -> dict:
    """
    Execute a batch of SDK functions serially with fail-fast error handling.
    
    Args:
        functions_list: List of SDK request objects
        benchmark_client: SDK client for API calls
    
    Returns:
        dict with:
        - "text": formatted string for conversation log
        - "tool_calls": list of {request, response} dicts for trace
    """
    text_parts = []
    tool_calls = []
    total_functions = len(functions_list)
    
    for idx, function in enumerate(functions_list, 1):
        request_json = function.model_dump_json()
        request_dict = function.model_dump()
        
        try:
            result = dispatch_with_timeout(benchmark_client, function)
            response_json = result.model_dump_json(exclude_none=True, exclude_unset=True)
            response_dict = result.model_dump(exclude_none=True, exclude_unset=True)
            
            # Auto-append basket state if applicable
            response_with_basket = append_basket_state_if_needed(function, benchmark_client, response_json)
            
            text_parts.append(f"Request:\n`{request_json}`\n\nResponse:\n`{response_with_basket}`")
            tool_calls.append({"request": request_dict, "response": response_dict})
            
        except TimeoutError as e:
            error_json = f'{{"error": "{str(e)}"}}'
            text_parts.append(f"Request:\n`{request_json}`\n\nResponse:\n`{error_json}`")
            tool_calls.append({"request": request_dict, "response": {"error": str(e)}})
            
            if idx < total_functions:
                text_parts.append(f"\nThe rest of requests are aborted due to the error.\nExecuted: {idx} out of {total_functions} requested operations.")
            break
            
        except ApiException as e:
            text_parts.append(f"Request:\n`{request_json}`\n\nResponse:\n`{e.detail}`")
            tool_calls.append({"request": request_dict, "response": {"error": e.detail}})
            
            if idx < total_functions:
                text_parts.append(f"\nThe rest of requests are aborted due to the error.\nExecuted: {idx} out of {total_functions} requested operations.")
            break
    
    return {
        "text": "\n\n---\n\n".join(text_parts),
        "tool_calls": tool_calls
    }


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def execute_store_tools(job, benchmark_client) -> dict:
    """
    Execute SDK tool(s) for store benchmark.
    
    This is the main entry point called by run_agent_loop via tool_executor.
    Handles both single and batch call modes.
    
    Args:
        job: Parsed LLM output with call.function or call.functions
        benchmark_client: SDK client for API calls
    
    Returns:
        dict with:
        - "text": Formatted response for conversation
        - "tool_calls": List of {request, response} dicts for trace
        - "function": The function(s) executed (for display)
    """
    if job.call.call_mode == "single":
        function = job.call.function
        result = execute_single_call(function, benchmark_client)
        return {
            "text": result["text"],
            "tool_calls": [result["tool_call"]],
            "function": function,
        }
    elif job.call.call_mode == "batch":
        functions = job.call.functions
        result = execute_batch(functions, benchmark_client)
        return {
            "text": result["text"],
            "tool_calls": result["tool_calls"],
            "function": functions,
        }
    else:
        raise ValueError(f"Unknown call_mode: {job.call.call_mode}")

