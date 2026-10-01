import pytest
from fastapi.testclient import TestClient
from src.server.telephony_server import app
from src.database.db import init_db
from src.database.booking_repo import get_db_cursor

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    init_db()

# ================= 1. ANALYTICS & DASHBOARD STATS =================

def test_audit_1_dashboard_stats_and_kpis():
    """Verify aggregated stats API returns all required metrics."""
    res = client.get("/api/dashboard/stats")
    assert res.status_code == 200
    data = res.json()
    
    assert "total_customers" in data and isinstance(data["total_customers"], int)
    assert "total_products" in data and isinstance(data["total_products"], int)
    assert "low_stock_count" in data and isinstance(data["low_stock_count"], int)
    assert "orders_today" in data and isinstance(data["orders_today"], int)
    assert "revenue_today" in data and isinstance(data["revenue_today"], (int, float))
    assert "total_orders" in data and isinstance(data["total_orders"], int)
    assert "total_revenue" in data and isinstance(data["total_revenue"], (int, float))

# ================= 2. STORE SETTINGS & SHOP NAME =================

def test_audit_2_store_settings_and_dynamic_shop_name():
    """Verify reading and modifying store settings (shop name, phone, delivery fee, threshold, ETA)."""
    # 1. Fetch current settings
    res = client.get("/api/settings")
    assert res.status_code == 200
    data = res.json()
    assert "settings" in data
    original_name = data["settings"].get("store_name", "D mart Express")

    # 2. Update shop name and delivery settings
    new_name = "Super DMart Bengaluru"
    update_payload = {
        "store_name": new_name,
        "store_phone": "+18554161860",
        "delivery_fee": "45.0",
        "free_delivery_threshold": "1000.0",
        "default_eta_minutes": "30",
        "welcome_greeting": "ನಮಸ್ಕಾರ, {store_name} ಗೆ ಸ್ವಾಗತ!"
    }
    res_up = client.put("/api/settings", json=update_payload)
    assert res_up.status_code == 200
    assert res_up.json()["success"] is True

    # 3. Verify health endpoint immediately reflects the updated store name
    res_h = client.get("/health")
    assert res_h.status_code == 200
    assert res_h.json()["store"] == new_name

    # 4. Verify settings persistence
    res_verify = client.get("/api/settings")
    assert res_verify.json()["settings"]["store_name"] == new_name
    assert res_verify.json()["settings"]["delivery_fee"] == "45.0"
    assert res_verify.json()["settings"]["default_eta_minutes"] == "30"

    # Revert back to original
    client.put("/api/settings", json={"store_name": original_name, "delivery_fee": "30.0"})

# ================= 3. PRODUCTS & CATALOG CRUD =================

def test_audit_3_products_catalog_crud_and_stock():
    """Verify full product lifecycle: create, search, filter, stock increment, edit, and delete."""
    # 1. Create product
    new_prod = {
        "name": "Audit Test Basmati Rice 1kg",
        "category": "Groceries",
        "price": 145.0,
        "unit": "1 kg",
        "stock_quantity": 8  # low stock initially
    }
    res_add = client.post("/api/products", json=new_prod)
    assert res_add.status_code == 200
    add_data = res_add.json()
    assert add_data["success"] is True
    prod_id = add_data["product"]["id"]

    # 2. Reject duplicate product name
    res_dup = client.post("/api/products", json=new_prod)
    assert res_dup.status_code == 200
    assert res_dup.json()["success"] is False
    assert "already exists" in res_dup.json()["error"]

    # 3. Search product by query
    res_s = client.get("/api/products?query=Audit Test Basmati")
    assert res_s.status_code == 200
    matches = res_s.json()["products"]
    assert any(p["id"] == prod_id for p in matches)

    # 4. Category filter
    res_cat = client.get("/api/products?category=Groceries")
    assert res_cat.status_code == 200
    assert any(p["id"] == prod_id for p in res_cat.json()["products"])

    # 5. Low stock filter (since stock is 8 <= 10)
    res_low = client.get("/api/products?low_stock=true")
    assert res_low.status_code == 200
    assert any(p["id"] == prod_id for p in res_low.json()["products"])

    # 6. Quick restock (+10)
    res_patch = client.patch(f"/api/products/{prod_id}/stock", json={"delta": 10})
    assert res_patch.status_code == 200
    assert res_patch.json()["new_stock"] == 18

    # 7. Edit product
    res_edit = client.put(f"/api/products/{prod_id}", json={
        "name": "Audit Test Basmati Rice 1kg",
        "category": "Groceries",
        "price": 155.0,
        "unit": "1 kg",
        "stock_quantity": 25
    })
    assert res_edit.status_code == 200
    assert res_edit.json()["product"]["price"] == 155.0
    assert res_edit.json()["product"]["stock_quantity"] == 25

    # 8. Delete product
    res_del = client.delete(f"/api/products/{prod_id}")
    assert res_del.status_code == 200
    assert res_del.json()["success"] is True

    # 9. Verify deletion
    res_check = client.get("/api/products?query=Audit Test Basmati")
    assert not any(p["id"] == prod_id for p in res_check.json()["products"])

# ================= 4. CUSTOMER REGISTRY CRUD =================

def test_audit_4_customer_registry_crud_and_orders():
    """Verify customer registration, phone normalization, editing, order lookup, and deletion."""
    # 1. Register customer
    cust_payload = {
        "phone": "9845012345",
        "name": "Audit Customer",
        "address": "#77, 4th Cross, Malleshwaram, Bengaluru"
    }
    res_reg = client.post("/api/customers", json=cust_payload)
    assert res_reg.status_code == 200
    reg_data = res_reg.json()
    assert reg_data["success"] is True
    cust_id = reg_data["customer_id"]

    # 2. Search customer by name and phone
    res_search_name = client.get("/api/customers?query=Audit Customer")
    assert res_search_name.status_code == 200
    assert any(c["id"] == cust_id for c in res_search_name.json()["customers"])

    res_search_phone = client.get("/api/customers?query=9845012345")
    assert res_search_phone.status_code == 200
    assert any(c["id"] == cust_id for c in res_search_phone.json()["customers"])

    # 3. Edit customer profile
    res_edit = client.put(f"/api/customers/{cust_id}", json={
        "phone": "+919845012345",
        "name": "Audit Customer Updated",
        "address": "#88, 5th Cross, Malleshwaram, Bengaluru"
    })
    assert res_edit.status_code == 200
    assert res_edit.json()["success"] is True
    assert res_edit.json()["customer"]["name"] == "Audit Customer Updated"

    # 4. View customer orders (empty initially)
    res_orders = client.get(f"/api/customers/{cust_id}/orders")
    assert res_orders.status_code == 200
    assert isinstance(res_orders.json()["orders"], list)

    # 5. Delete customer profile
    res_del = client.delete(f"/api/customers/{cust_id}")
    assert res_del.status_code == 200
    assert res_del.json()["success"] is True

# ================= 5. ORDERS MANAGEMENT & STOCK RESTORATION =================

def test_audit_5_orders_lifecycle_and_stock_restoration():
    """Verify placing manual order, status transitions, and automatic stock restoration upon cancellation."""
    # Record initial stock of Fortune Sunlite Sunflower Oil 1L
    res_p = client.get("/api/products?query=Sunflower Oil")
    oil_prod = res_p.json()["products"][0]
    initial_stock = oil_prod["stock_quantity"]
    oil_id = oil_prod["id"]

    # 1. Place Order (Order 2 units)
    order_payload = {
        "customer_phone": "+919008474173",
        "customer_name": "Vedashree",
        "delivery_type": "delivery",
        "delivery_address": "Krishna Nagar, Bengaluru",
        "items": [{"name": oil_prod["name"], "quantity": 2}]
    }
    res_order = client.post("/api/orders", json=order_payload)
    assert res_order.status_code == 200
    order_data = res_order.json()
    assert order_data["success"] is True
    order_id = order_data["order_id"]
    assert order_data["status"] == "CONFIRMED"

    # Verify stock deducted by 2
    res_p2 = client.get("/api/products?query=Sunflower Oil")
    after_order_stock = next(p["stock_quantity"] for p in res_p2.json()["products"] if p["id"] == oil_id)
    assert after_order_stock == initial_stock - 2

    # 2. Get order details
    res_det = client.get(f"/api/orders/{order_id}")
    assert res_det.status_code == 200
    det = res_det.json()
    assert det["order_id"] == order_id
    assert det["customer_name"] == "Vedashree"
    assert len(det["items"]) == 1
    assert det["items"][0]["quantity"] == 2

    # 3. Status progression: CONFIRMED -> PREPARING
    res_prep = client.patch(f"/api/orders/{order_id}/status", json={"status": "PREPARING"})
    assert res_prep.status_code == 200
    assert res_prep.json()["status"] == "PREPARING"

    # 4. Status progression: PREPARING -> OUT_FOR_DELIVERY
    res_out = client.patch(f"/api/orders/{order_id}/status", json={"status": "OUT_FOR_DELIVERY"})
    assert res_out.status_code == 200
    assert res_out.json()["status"] == "OUT_FOR_DELIVERY"

    # 5. Status progression: OUT_FOR_DELIVERY -> DELIVERED
    res_deliv = client.patch(f"/api/orders/{order_id}/status", json={"status": "DELIVERED"})
    assert res_deliv.status_code == 200
    assert res_deliv.json()["status"] == "DELIVERED"

    # 6. Cancel order -> MUST restore the 2 units of stock back to inventory!
    res_cancel = client.post(f"/api/orders/{order_id}/cancel")
    assert res_cancel.status_code == 200
    assert res_cancel.json()["success"] is True

    # Verify inventory was restored!
    res_p3 = client.get("/api/products?query=Sunflower Oil")
    restored_stock = next(p["stock_quantity"] for p in res_p3.json()["products"] if p["id"] == oil_id)
    assert restored_stock == initial_stock

# ================= 6. TELEPHONY CALL LOGS =================

def test_audit_6_telephony_call_logs():
    """Verify call logs endpoint returns call records with correct schema."""
    res_calls = client.get("/api/calls")
    assert res_calls.status_code == 200
    data = res_calls.json()
    assert "calls" in data
    assert isinstance(data["calls"], list)
