# Tool Calling & Function Execution Reference

The AI agent uses deterministic function calling to interact with the database, check inventory, calculate delivery windows, and register new customers.

All tools are defined in `src/tools/booking_tools.py` and dispatched through `execute_tool_call(name, arguments, default_phone)`.

---

## 1. Tool Summary

| Function Name | Description | Invocation Scenario |
| :--- | :--- | :--- |
| `register_caller` | Creates a new customer profile in SQLite | Caller is unregistered and provides name and delivery address |
| `search_catalog` | Searches store inventory by query or category | Caller asks for items (e.g., "ಹಾಲು", "milk", "tea", "cooking oil") |
| `check_stock` | Checks stock availability for a specific item | Verification of sufficient stock before confirming an order |
| `place_order` | Atomically commits order, deducts stock, calculates ETA | Caller confirms purchase |
| `track_order` | Retrieves status and items for an Order ID | Caller asks about an existing order (e.g. `DMART-A045`) |
| `cancel_existing_order` | Cancels order and returns items to stock | Caller requests cancellation |

---

## 2. Tool Specifications

### `register_caller`
Registers a new customer or updates an existing address.

- **Parameters**:
  - `customer_name` *(string, required)*: Full name of the customer.
  - `delivery_address` *(string, required)*: Delivery address in service area.
  - `customer_phone` *(string, optional)*: Phone number. Defaults to caller's phone if omitted.
- **Example Call**:
```json
{
  "tool": "register_caller",
  "arguments": {
    "customer_name": "ಸುನಿಲ್ ಕುಮಾರ್",
    "delivery_address": "#45, ಮಲ್ಲೇಶ್ವರಂ, ಬೆಂಗಳೂರು"
  }
}
```
- **Returns**:
```json
{
  "success": true,
  "customer_id": 225,
  "name": "ಸುನಿಲ್ ಕುಮಾರ್",
  "phone_number": "+919333222111",
  "address": "#45, ಮಲ್ಲೇಶ್ವರಂ, ಬೆಂಗಳೂರು",
  "message": "Customer registered successfully."
}
```

---

### `search_catalog`
Queries the DMart store database using fuzzy keyword and semantic synonym matching.

- **Parameters**:
  - `query` *(string, optional)*: Product name, synonym, or category.
- **Example Call**:
```json
{
  "tool": "search_catalog",
  "arguments": {
    "query": "ಹಾಲು"
  }
}
```
- **Returns**:
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
Checks if the store has sufficient units of an item.

- **Parameters**:
  - `product_name` *(string, required)*: Exact or approximate product name.
  - `quantity` *(integer, optional)*: Desired quantity (default: 1).
- **Example Call**:
```json
{
  "tool": "check_stock",
  "arguments": {
    "product_name": "Amul Taaza Toned Milk 1L",
    "quantity": 2
  }
}
```
- **Returns (Success)**:
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

---

### `place_order`
Creates the order in SQLite, automatically links customer details, deducts stock quantities, and calculates the delivery arrival window.

- **Parameters**:
  - `items` *(array of objects, required)*:
    - `name` *(string)*: Product name.
    - `quantity` *(integer)*: Quantity.
  - `delivery_type` *(string, optional)*: `"delivery"` (default) or `"pickup"`.
  - `delivery_address` *(string, optional)*: Omit for registered callers; will be pulled automatically from profile.
  - `customer_name` *(string, optional)*: Omit for registered callers.
  - `customer_phone` *(string, optional)*: Omit for registered callers.
- **Example Call**:
```json
{
  "tool": "place_order",
  "arguments": {
    "items": [
      {"name": "Fortune Sunlite Sunflower Oil 1L", "quantity": 1},
      {"name": "Madhur Pure & Hygienic Sugar 1kg", "quantity": 1}
    ],
    "delivery_type": "delivery"
  }
}
```
- **Returns**:
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

---

### `track_order`
Retrieves live status for a previously confirmed order.

- **Parameters**:
  - `order_id` *(string, required)*: The unique Order ID (e.g. `DMART-E4A1`).
- **Example Call**:
```json
{
  "tool": "track_order",
  "arguments": {
    "order_id": "DMART-E4A1"
  }
}
```

---

### `cancel_existing_order`
Cancels an order and automatically increments the inventory stock of all items in that order.

- **Parameters**:
  - `order_id` *(string, required)*: Order identifier to cancel.
- **Example Call**:
```json
{
  "tool": "cancel_existing_order",
  "arguments": {
    "order_id": "DMART-E4A1"
  }
}
```
