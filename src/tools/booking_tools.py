import json
from typing import Dict, Any, List
from loguru import logger
from src.database.booking_repo import (
    search_products,
    check_item_stock,
    create_store_order,
    get_order_details,
    cancel_order
)

# 1. JSON Tool Definitions for the LLM
STORE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_catalog",
            "description": "Search available grocery and supermarket products in the store by name or category (e.g. 'milk', 'oil', 'dal', 'snacks').",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search keyword for product or category (e.g., 'rice', 'dairy')."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_stock",
            "description": "Check if a specific item is currently in stock with the requested quantity.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_name": {
                        "type": "string",
                        "description": "Name of the product (e.g. 'Amul Taaza Milk', 'Tata Salt')."
                    },
                    "quantity": {
                        "type": "integer",
                        "description": "Number of units requested. Defaults to 1."
                    }
                },
                "required": ["product_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "place_order",
            "description": "Place a confirmed order for the caller. Only call this when the customer has confirmed their name, phone, items with quantities, and delivery/pickup choice with address.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {"type": "string", "description": "Customer's full name."},
                    "customer_phone": {"type": "string", "description": "Customer's phone number."},
                    "items": {
                        "type": "array",
                        "description": "List of items with exact name and quantity to purchase.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "description": "Item name."},
                                "quantity": {"type": "integer", "description": "Quantity."}
                            },
                            "required": ["name", "quantity"]
                        }
                    },
                    "delivery_type": {
                        "type": "string",
                        "enum": ["delivery", "pickup"],
                        "description": "Whether the order is for home delivery or store pickup."
                    },
                    "delivery_address": {
                        "type": "string",
                        "description": "Full street address for home delivery (can be empty if pickup)."
                    }
                },
                "required": ["customer_name", "customer_phone", "items", "delivery_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "track_order",
            "description": "Look up an existing order by its Order ID (e.g., 'DMART-A1B2').",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "The unique Order ID."}
                },
                "required": ["order_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_existing_order",
            "description": "Cancel an existing order using the Order ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "The unique Order ID to cancel."}
                },
                "required": ["order_id"]
            }
        }
    }
]

# 2. Tool Execution Dispatcher
def execute_tool_call(name: str, arguments: Dict[str, Any]) -> str:
    """Executes the Python repository function matching the tool name and returns JSON string."""
    logger.info(f"Executing Tool Call: {name} with args: {arguments}")
    
    try:
        if name == "search_catalog":
            query = arguments.get("query", "")
            res = search_products(query)
            return json.dumps({"products": res})
        
        elif name == "check_stock":
            product_name = arguments.get("product_name", "")
            qty = arguments.get("quantity", 1)
            res = check_item_stock(product_name, qty)
            return json.dumps(res)
            
        elif name == "place_order":
            res = create_store_order(
                customer_name=arguments.get("customer_name", ""),
                customer_phone=arguments.get("customer_phone", ""),
                items=arguments.get("items", []),
                delivery_type=arguments.get("delivery_type", "delivery"),
                delivery_address=arguments.get("delivery_address")
            )
            return json.dumps(res)
            
        elif name == "track_order":
            order_id = arguments.get("order_id", "")
            res = get_order_details(order_id)
            return json.dumps(res)
            
        elif name == "cancel_existing_order":
            order_id = arguments.get("order_id", "")
            res = cancel_order(order_id)
            return json.dumps(res)
            
        else:
            return json.dumps({"error": f"Unknown tool name: {name}"})
            
    except Exception as e:
        logger.error(f"Error in tool execution {name}: {e}")
        return json.dumps({"error": str(e)})
