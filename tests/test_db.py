from src.database.db import init_db
from src.database.booking_repo import (
    search_products,
    check_item_stock,
    create_store_order,
    get_order_details,
    cancel_order
)

def test_store_flow():
    # 1. Initialize DB & Seed Catalog
    init_db()
    
    # 2. Search catalog
    products = search_products("milk")
    assert len(products) > 0
    milk_name = products[0]["name"]
    
    # 3. Check stock
    stock = check_item_stock("Milk", 2)
    assert stock["in_stock"] is True
    
    # 4. Place an order
    order_res = create_store_order(
        customer_name="Rahul Sharma",
        customer_phone="+919876543210",
        items=[
            {"name": "Amul Taaza Toned Milk", "quantity": 2},
            {"name": "Tata Salt", "quantity": 1}
        ],
        delivery_type="delivery",
        delivery_address="Flat 402, Sunshine Heights, Mumbai"
    )
    assert order_res["success"] is True
    order_id = order_res["order_id"]
    print(f"\nCreated Order: {order_id} with total ₹{order_res['total_amount']}")
    
    # 5. Fetch details
    details = get_order_details(order_id)
    assert details["found"] is True
    assert len(details["items"]) == 2
    
    # 6. Cancel order and verify
    cancelled = cancel_order(order_id)
    assert cancelled["success"] is True
    
    print("\n✅ All DMart Store & Order Engine tests passed successfully!")

if __name__ == "__main__":
    test_store_flow()
