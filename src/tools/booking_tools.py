import json
from typing import Dict, Any, List, Optional
from loguru import logger
from src.database.booking_repo import (
    search_products,
    check_item_stock,
    create_store_order,
    get_order_details,
    cancel_order
)
from src.database.customer_repo import (
    get_customer,
    register_customer
)

# 1. JSON Tool Definitions for the Local LLM
STORE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "register_caller",
            "description": "Register a new or unregistered caller into the DMart database. Call this when an unregistered caller provides their name and delivery address.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {
                        "type": "string", 
                        "description": "Customer's full name (e.g. 'Rahul Sharma')."
                    },
                    "delivery_address": {
                        "type": "string", 
                        "description": "Customer's full delivery street address and area."
                    },
                    "customer_phone": {
                        "type": "string", 
                        "description": "Customer's phone number. Defaults to current caller number if omitted."
                    }
                },
                "required": ["customer_name", "delivery_address"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_catalog",
            "description": "Search available grocery products, staples, beverages, snacks, produce, and categories in the store catalog.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search keyword or general category (e.g. 'milk', 'sunflower oil', 'tea', 'atta', 'breakfast', 'rice')."
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
            "description": "Check if specific grocery items and quantities are in stock in the catalog.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_name": {
                        "type": "string",
                        "description": "Name of the product (e.g. 'Amul Taaza Milk', 'Aashirvaad Atta')."
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
            "description": "Place the final confirmed grocery order. The system automatically attaches the customer's registered address and phone from the database and returns the dynamic delivery arrival time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {
                        "type": "string", 
                        "description": "Customer's name. Can be empty if registered."
                    },
                    "customer_phone": {
                        "type": "string", 
                        "description": "Customer's phone number. Can be empty if registered caller."
                    },
                    "items": {
                        "type": "array",
                        "description": "List of items with exact product name and quantity to purchase.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "description": "Exact product name (e.g. 'Amul Taaza Toned Milk 1L')."},
                                "quantity": {"type": "integer", "description": "Quantity to order."}
                            },
                            "required": ["name", "quantity"]
                        }
                    },
                    "delivery_type": {
                        "type": "string",
                        "enum": ["delivery", "pickup"],
                        "description": "Whether the order is for home delivery or store pickup. Defaults to 'delivery'."
                    },
                    "delivery_address": {
                        "type": "string",
                        "description": "Delivery address. Omit if customer is registered and using their registered address."
                    }
                },
                "required": ["items"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "track_order",
            "description": "Look up details and status of an existing order using the Order ID (e.g. 'DMART-A1B2').",
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
            "description": "Cancel an existing order using the Order ID and restore items to stock.",
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
def execute_tool_call(name: str, arguments: Dict[str, Any], default_phone: Optional[str] = None) -> str:
    """Executes the repository function matching the tool name and returns JSON string."""
    logger.info(f"Executing Tool Call: {name} with args: {arguments} (caller: {default_phone})")
    
    if not isinstance(arguments, dict):
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except Exception:
                arguments = {}
        else:
            arguments = {}

    try:
        if name == "register_caller":
            phone = arguments.get("customer_phone") or default_phone or ""
            name_val = arguments.get("customer_name", "")
            address_val = arguments.get("delivery_address", "")
            res = register_customer(phone_number=str(phone), name=str(name_val), address=str(address_val))
            return json.dumps(res)
            
        elif name == "search_catalog":
            query = arguments.get("query", "")
            res = search_products(str(query))
            return json.dumps({"products": res, "count": len(res)})
        
        elif name == "check_stock":
            product_name = arguments.get("product_name", "")
            qty = arguments.get("quantity", 1)
            res = check_item_stock(str(product_name), qty)
            return json.dumps(res)
            
        elif name == "place_order":
            phone = arguments.get("customer_phone") or default_phone or ""
            name_val = arguments.get("customer_name", "")
            raw_items = arguments.get("items", [])
            
            # Guard against stringified items JSON
            if isinstance(raw_items, str):
                try:
                    raw_items = json.loads(raw_items)
                except Exception:
                    raw_items = [{"name": raw_items, "quantity": 1}]
            
            # Normalize list of items (handle string elements vs dicts)
            cleaned_items = []
            if isinstance(raw_items, list):
                for it in raw_items:
                    if isinstance(it, str):
                        cleaned_items.append({"name": it, "quantity": 1})
                    elif isinstance(it, dict):
                        cleaned_items.append({
                            "name": str(it.get("name", "")),
                            "quantity": it.get("quantity", 1)
                        })
            else:
                cleaned_items = []

            del_type = arguments.get("delivery_type", "delivery")
            address = arguments.get("delivery_address")
            
            res = create_store_order(
                customer_name=str(name_val) if name_val else "",
                customer_phone=str(phone) if phone else "",
                items=cleaned_items,
                delivery_type=str(del_type),
                delivery_address=str(address) if address else None
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
