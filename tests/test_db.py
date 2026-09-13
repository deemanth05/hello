import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.database.db import init_db
from src.database.customer_repo import (
    get_customer,
    register_customer,
    normalize_phone,
    list_all_customers
)
from src.database.booking_repo import (
    search_products,
    check_item_stock,
    create_store_order,
    get_order_details,
    cancel_order,
    calculate_dynamic_eta
)

def test_full_database_and_repo_flow():
    print("--- Initializing Database ---")
    init_db()
    
    # 1. Test Phone Normalization
    assert normalize_phone("+91 98765-43210") == "9876543210"
    assert normalize_phone("09876543210") == "9876543210"
    assert normalize_phone("9876543210") == "9876543210"
    print("[OK] Phone normalization verified.")

    # 2. Test Deterministic Registered Customer Lookup
    cust = get_customer("+919876543210")
    assert cust is not None
    assert cust["name"] == "Rahul Sharma"
    assert "Sunshine Heights" in cust["address"]
    
    # Also lookup via raw 10 digits
    cust_raw = get_customer("9876543210")
    assert cust_raw is not None
    assert cust_raw["name"] == "Rahul Sharma"
    print(f"[OK] Found registered customer: {cust['name']} ({cust['phone_number']}) at {cust['address']}")

    # 3. Test Unregistered Customer Detection & In-Call Registration
    unregistered_phone = "+919999888877"
    # Clean up test user if present from earlier runs
    reg_res = register_customer(
        phone_number=unregistered_phone,
        name="Vikram Rao",
        address="Flat 101, Palm Grove Apartments, Indiranagar, Bangalore"
    )
    assert reg_res["success"] is True
    print(f"[OK] Registered new customer: {reg_res['name']} ({reg_res['phone_number']})")
    
    # Verify lookup succeeds now
    cust_new = get_customer(unregistered_phone)
    assert cust_new is not None
    assert cust_new["name"] == "Vikram Rao"
    print(f"[OK] Customer lookup verified after registration.")

    # 4. Test Semantic / General Item Search
    tea_results = search_products("I want to make tea")
    assert len(tea_results) > 0
    tea_names = [p["name"] for p in tea_results]
    print(f"[OK] General query 'I want to make tea' matched: {tea_names[:3]}")

    breakfast_results = search_products("breakfast")
    assert len(breakfast_results) > 0
    print(f"[OK] General query 'breakfast' matched: {[p['name'] for p in breakfast_results[:3]]}")

    # 5. Test Stock Verification
    stock = check_item_stock("Amul Taaza Milk", 2)
    assert stock["in_stock"] is True
    print(f"[OK] Stock check verified: {stock['product_name']} is in stock.")

    # 6. Test Placing Order with Dynamic ETA & Auto Address Resolution
    order_res = create_store_order(
        customer_name="",  # Should auto-resolve from customer profile
        customer_phone=unregistered_phone,
        items=[
            {"name": "Amul Taaza Toned Milk 1L", "quantity": 2},
            {"name": "Britannia 100% Whole Wheat Bread", "quantity": 1},
            {"name": "Red Label Tea 500g", "quantity": 1}
        ],
        delivery_type="delivery"
    )
    assert order_res["success"] is True
    assert order_res["customer_name"] == "Vikram Rao"
    assert "Palm Grove" in order_res["delivery_address"]
    assert "minutes" in order_res["estimated_delivery_time"]
    
    order_id = order_res["order_id"]
    print(f"[OK] Created Order {order_id}:")
    print(f"     Customer: {order_res['customer_name']}")
    print(f"     Address: {order_res['delivery_address']}")
    print(f"     Total Amount: Rs. {order_res['total_amount']}")
    print(f"     Estimated Delivery: {order_res['estimated_delivery_time']}")

    # 7. Test Order Retrieval
    details = get_order_details(order_id)
    assert details["found"] is True
    assert len(details["items"]) == 3
    print(f"[OK] Retrieved order details with {len(details['items'])} items.")

    # 8. Test Order Cancellation
    cancelled = cancel_order(order_id)
    assert cancelled["success"] is True
    print(f"[OK] Cancelled order successfully.")

    print("\n[PASSED] ALL PHASE 1 DATABASE & REPOSITORY TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_full_database_and_repo_flow()
