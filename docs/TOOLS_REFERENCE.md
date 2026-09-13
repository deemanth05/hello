# Tool Calling & Function Execution Reference

The DMart Express AI Voice Agent uses deterministic function calling to interact with the SQLite database, search the grocery catalog, check inventory levels, commit orders, calculate delivery windows, and register new customers.

All tool executions are dispatched via `execute_tool_call(name: str, arguments: Dict[str, Any], default_phone: Optional[str] = None) -> str` located in [`src/tools/booking_tools.py`](file:///c:/Users/deema/Desktop/hello/src/tools/booking_tools.py).

---

## 1. Dual-Schema Declarations

Depending on the deployment pipeline, tools are declared in one of two formats:

1. **Cloud Gemini Live Mode (`GEMINI_TOOLS` in [`src/server/gemini_live_bridge.py`](file:///c:/Users/deema/Desktop/hello/src/server/gemini_live_bridge.py))**:
   - Registered using the `google.genai` SDK `types.Tool(function_declarations=[...])`.
   - Focuses on 4 real-time voice ordering functions: `search_catalog`, `check_stock`, `place_order`, `register_caller`.
   - Results are fed back natively to Gemini Live via `session.send_tool_response(...)` with `types.FunctionResponse(name=..., id=..., response={"result": res})`.

2. **Local Pipeline Mode (`STORE_TOOLS` in [`src/tools/booking_tools.py`](file:///c:/Users/deema/Desktop/hello/src/tools/booking_tools.py))**:
   - Registered using standard JSON Schema / OpenAI function calling format.
   - Declares all 6 tools including order management: `register_caller`, `search_catalog`, `check_stock`, `place_order`, `track_order`, `cancel_existing_order`.
   - Dispatched directly in the local conversation turn loop.

---

## 2. Tool Summary

| Function Name | Cloud Mode (Gemini) | Local Mode (Ollama) | Description | Invocation Scenario |
| :--- | :---: | :---: | :--- | :--- |
| `register_caller` | Yes | Yes | Registers new customer name and delivery address in SQLite | Caller is unregistered and provides name and address |
| `search_catalog` | Yes | Yes | Queries products via keyword and semantic synonym matching | Caller asks for items (e.g., "ಹಾಲು", "milk", "tea", "sugar") |
| `check_stock` | Yes | Yes | Checks current stock availability and price for a product | Agent or caller verifies available quantity before confirming |
| `place_order` | Yes | Yes | Commits atomic order, deducts inventory, calculates ETA | Caller confirms order purchase |
| `track_order` | Via Dispatcher | Yes | Retrieves live status and line items for an Order ID | Caller inquires about a past order (e.g. `DMART-A045`) |
| `cancel_existing_order` | Via Dispatcher | Yes | Cancels order and restores line items back to inventory | Caller requests order cancellation |

---

## 3. Tool Specifications

### `register_caller`
Registers a new customer profile or updates an existing address in the `customers` table.

- **Parameters**:
  - `customer_name` *(string, required)*: Full name of the customer (e.g. "ರಾಹುಲ್ ಶರ್ಮ" or "Rahul Sharma").
  - `delivery_address` *(string, required)*: Full street address and locality (e.g. "#45, 2nd Cross, Malleshwaram, Bengaluru").
  - `customer_phone` *(string, optional)*: Phone number in E.164 format. Defaults to current caller's phone (`default_phone` passed by telephony session) if omitted.
- **Handler**: `register_customer(...)` in [`src/database/customer_repo.py`](file:///c:/Users/deema/Desktop/hello/src/database/customer_repo.py).
- **Return (Success)**:
  ```json
  {
    "success": true,
    "customer_id": 6,
    "name": "ಸುನಿಲ್ ಕುಮಾರ್",
    "phone_number": "+919333222111",
    "address": "#45, ಮಲ್ಲೇಶ್ವರಂ, ಬೆಂಗಳೂರು",
    "message": "Customer registered successfully."
  }
  ```
- **Return (Failure)**:
  ```json
  {
    "success": false,
    "error": "Phone number, name, and address are required."
  }
  ```

---

### `search_catalog`
Searches available grocery products using tokenized keyword matching, category filters, and semantic Kannada/English grocery synonyms defined in `SEMANTIC_SYNONYMS`.

- **Parameters**:
  - `query` *(string, optional in local schema, required in Gemini schema)*: Product name, category, or general term (e.g. "milk", "ಹಾಲು", "sugar", "ಸಕ್ಕರೆ", "bread", "cooking oil", "ಬೇಳೆ").
- **Handler**: `search_products(...)` in [`src/database/booking_repo.py`](file:///c:/Users/deema/Desktop/hello/src/database/booking_repo.py).
- **Synonym Expansion**: Automatically expands common intents:
  - `"ಹಾಲು"` / `"milk"` $\rightarrow$ `["milk", "amul taaza", "amul gold"]`
  - `"tea"` / `"ಚಹಾ"` $\rightarrow$ `["tea", "sugar", "milk"]`
  - `"ಸಕ್ಕರೆ"` / `"sugar"` $\rightarrow$ `["sugar", "madhur"]`
  - `"ಎಣ್ಣೆ"` / `"oil"` $\rightarrow$ `["sunflower oil", "mustard oil"]`
  - `"ತಿಂಡಿ"` / `"breakfast"` $\rightarrow$ `["bread", "eggs", "butter", "milk"]`
- **Return**:
  ```json
  {
    "products": [
      {
        "id": 11,
        "name": "Amul Taaza Toned Milk 1L",
        "category": "Dairy",
        "price": 54.0,
        "unit": "1 Liter",
        "stock_quantity": 50
      },
      {
        "id": 12,
        "name": "Amul Gold Full Cream Milk 1L",
        "category": "Dairy",
        "price": 68.0,
        "unit": "1 Liter",
        "stock_quantity": 40
      }
    ],
    "count": 2
  }
  ```

---

### `check_stock`
Checks whether a specified product exists and has sufficient units in inventory.

- **Parameters**:
  - `product_name` *(string, required)*: Exact or approximate product name (e.g. "Amul Taaza Milk", "Aashirvaad Atta").
  - `quantity` *(integer, optional)*: Requested quantity. Defaults to `1`.
- **Handler**: `check_item_stock(...)` in [`src/database/booking_repo.py`](file:///c:/Users/deema/Desktop/hello/src/database/booking_repo.py).
- **Return (In Stock)**:
  ```json
  {
    "in_stock": true,
    "product_id": 11,
    "product_name": "Amul Taaza Toned Milk 1L",
    "unit": "1 Liter",
    "price": 54.0,
    "available_stock": 50
  }
  ```
- **Return (Insufficient Stock)**:
  ```json
  {
    "in_stock": false,
    "item_name": "Amul Taaza Toned Milk 1L",
    "available_stock": 2,
    "reason": "Only 2 units of 'Amul Taaza Toned Milk 1L' available."
  }
  ```
- **Return (Not Found)**:
  ```json
  {
    "in_stock": false,
    "reason": "Item matching 'Almond Butter' was not found in catalog."
  }
  ```

---

### `place_order`
Atomically validates stock for all items, creates the order in the `orders` table, inserts line items into `order_items`, deducts stock from `products`, and calculates dynamic ETA.

- **Parameters**:
  - `items` *(array of objects, required)*:
    - `name` *(string, required)*: Exact or recognizable product name.
    - `quantity` *(integer, required)*: Number of units to order.
  - `delivery_type` *(string, optional)*: `"delivery"` (default) or `"pickup"`.
  - `delivery_address` *(string, optional)*: Delivery address. If omitted and customer is registered in database, their registered address is automatically populated.
  - `customer_name` *(string, optional)*: Customer name. Automatically populated from registered profile if omitted.
  - `customer_phone` *(string, optional)*: Customer phone number. Automatically populated from incoming caller ID if omitted.
- **Handler**: `create_store_order(...)` in [`src/database/booking_repo.py`](file:///c:/Users/deema/Desktop/hello/src/database/booking_repo.py).
- **Business Logic**:
  - Delivery Fee: Free if `subtotal >= 800.0` (`settings.FREE_DELIVERY_THRESHOLD`), otherwise `30.0` (`settings.DELIVERY_FEE`). For `"pickup"`, fee is always `0.0`.
  - ETA Window: Calculated dynamically as `30 to 40 minutes (approx <HH:MM AM/PM>)`.
  - Stock Deductions: Decrements `stock_quantity` by ordered quantity for each item inside a single atomic SQLite transaction.
- **Return (Success)**:
  ```json
  {
    "success": true,
    "order_id": "DMART-E4A1",
    "customer_name": "Rahul Sharma",
    "customer_phone": "+919876543210",
    "delivery_type": "delivery",
    "delivery_address": "Flat 402, Sunshine Heights, Mumbai",
    "items": [
      {
        "product_id": 1,
        "name": "Fortune Sunlite Sunflower Oil 1L",
        "quantity": 1,
        "price": 140.0,
        "unit": "1 Liter",
        "subtotal": 140.0
      },
      {
        "product_id": 10,
        "name": "Madhur Pure & Hygienic Sugar 1kg",
        "quantity": 1,
        "price": 45.0,
        "unit": "1 kg",
        "subtotal": 45.0
      }
    ],
    "subtotal": 185.0,
    "delivery_fee": 30.0,
    "total_amount": 215.0,
    "estimated_delivery_time": "30 to 40 minutes (approx 10:15 PM)",
    "status": "CONFIRMED"
  }
  ```
- **Return (Failure - Insufficient Stock)**:
  ```json
  {
    "success": false,
    "error": "Insufficient stock for 'Amul Taaza Toned Milk 1L'. Requested: 100, Available: 50."
  }
  ```

---

### `track_order`
Retrieves current status and purchased items for an existing Order ID.

- **Parameters**:
  - `order_id` *(string, required)*: Order identifier (e.g. `DMART-E4A1`).
- **Handler**: `get_order_details(...)` in [`src/database/booking_repo.py`](file:///c:/Users/deema/Desktop/hello/src/database/booking_repo.py).
- **Return (Success)**:
  ```json
  {
    "id": 1,
    "order_id": "DMART-E4A1",
    "customer_name": "Rahul Sharma",
    "customer_phone": "+919876543210",
    "delivery_type": "delivery",
    "delivery_address": "Flat 402, Sunshine Heights, Mumbai",
    "total_amount": 215.0,
    "estimated_delivery_time": "30 to 40 minutes (approx 10:15 PM)",
    "status": "CONFIRMED",
    "created_at": "2026-09-13 16:30:00",
    "found": true,
    "items": [
      {
        "product_name": "Fortune Sunlite Sunflower Oil 1L",
        "quantity": 1,
        "unit_price": 140.0,
        "subtotal": 140.0
      },
      {
        "product_name": "Madhur Pure & Hygienic Sugar 1kg",
        "quantity": 1,
        "unit_price": 45.0,
        "subtotal": 45.0
      }
    ]
  }
  ```
- **Return (Not Found)**:
  ```json
  {
    "found": false,
    "error": "No order found with ID DMART-XXXX."
  }
  ```

---

### `cancel_existing_order`
Cancels an order and automatically increments the stock quantity in the `products` table for every line item in the order.

- **Parameters**:
  - `order_id` *(string, required)*: Order identifier to cancel.
- **Handler**: `cancel_order(...)` in [`src/database/booking_repo.py`](file:///c:/Users/deema/Desktop/hello/src/database/booking_repo.py).
- **Return (Success)**:
  ```json
  {
    "success": true,
    "message": "Order DMART-E4A1 has been cancelled and items returned to stock."
  }
  ```
- **Return (Already Cancelled or Not Found)**:
  ```json
  {
    "success": false,
    "error": "Order DMART-E4A1 is already cancelled."
  }
  ```

---

## 4. Error Handling & Input Sanitization

`execute_tool_call` implements robust defensive parsing:
1. **Stringified JSON Support**: If LLM passes `arguments` as a raw JSON string rather than a Python dictionary, it is parsed via `json.loads`.
2. **Items List Normalization**: Handles cases where the model returns items as strings (e.g. `["Amul Milk"]`) instead of structured dicts (`[{"name": "Amul Milk", "quantity": 1}]`).
3. **Default Phone Injection**: If the model omits `customer_phone`, `execute_tool_call` transparently falls back to the caller's phone number extracted from the Twilio WebSocket session.
4. **Exception Handling**: Any unexpected database or runtime error is caught, logged with stack trace via `loguru.logger`, and returned as `{"error": str(e)}`.
