import pytest
from fastapi.testclient import TestClient
from src.server.telephony_server import app
from src.database.db import init_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    init_db()

def test_dashboard_stats():
    res = client.get("/api/dashboard/stats")
    assert res.status_code == 200
    data = res.json()
    assert "total_customers" in data
    assert "total_products" in data
    assert "revenue_today" in data
    assert "orders_today" in data

def test_settings_crud():
    # 1. Get settings
    res = client.get("/api/settings")
    assert res.status_code == 200
    data = res.json()
    assert "settings" in data

    # 2. Update store name
    res = client.put("/api/settings", json={"store_name": "DMart Mega Store", "delivery_fee": "35.0"})
    assert res.status_code == 200
    assert res.json()["success"] is True

    # 3. Verify health returns updated store name
    res_h = client.get("/health")
    assert res_h.status_code == 200
    assert res_h.json()["store"] == "DMart Mega Store"

    # Revert back
    client.put("/api/settings", json={"store_name": "D mart Express", "delivery_fee": "30.0"})

def test_products_crud():
    # 1. Add product
    prod_payload = {
        "name": "Organic Honey 500g",
        "category": "Groceries",
        "price": 220.0,
        "unit": "500 g",
        "stock_quantity": 25
    }
    res = client.post("/api/products", json=prod_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    prod_id = data["product"]["id"]

    # 2. Search product
    res_s = client.get(f"/api/products?query=Organic Honey")
    assert res_s.status_code == 200
    prods = res_s.json()["products"]
    assert any(p["id"] == prod_id for p in prods)

    # 3. Quick stock patch (+10)
    res_stock = client.patch(f"/api/products/{prod_id}/stock", json={"delta": 10})
    assert res_stock.status_code == 200
    assert res_stock.json()["new_stock"] == 35

    # 4. Update product price
    res_u = client.put(f"/api/products/{prod_id}", json={
        "name": "Organic Honey 500g",
        "category": "Groceries",
        "price": 240.0,
        "unit": "500 g",
        "stock_quantity": 35
    })
    assert res_u.status_code == 200
    assert res_u.json()["product"]["price"] == 240.0

    # 5. Delete product
    res_d = client.delete(f"/api/products/{prod_id}")
    assert res_d.status_code == 200
    assert res_d.json()["success"] is True

def test_customers_crud():
    # 1. Register customer
    cust_payload = {
        "phone": "+919988776655",
        "name": "Test User",
        "address": "123 Malleshwaram, Bengaluru"
    }
    res = client.post("/api/customers", json=cust_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    cust_id = data["customer_id"]

    # 2. Update customer
    res_u = client.put(f"/api/customers/{cust_id}", json={
        "phone": "+919988776655",
        "name": "Test User Updated",
        "address": "456 Indiranagar, Bengaluru"
    })
    assert res_u.status_code == 200
    assert res_u.json()["customer"]["name"] == "Test User Updated"

    # 3. Delete customer
    res_d = client.delete(f"/api/customers/{cust_id}")
    assert res_d.status_code == 200
    assert res_d.json()["success"] is True

def test_orders_flow():
    # 1. Create order
    order_payload = {
        "customer_phone": "+919008474173",
        "customer_name": "Vedashree",
        "delivery_type": "delivery",
        "delivery_address": "Krishna Nagar, Bengaluru",
        "items": [{"name": "Amul Taaza Toned Milk 1L", "quantity": 1}]
    }
    res = client.post("/api/orders", json=order_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    order_id = data["order_id"]

    # 2. Get order details
    res_det = client.get(f"/api/orders/{order_id}")
    assert res_det.status_code == 200
    assert res_det.json()["order_id"] == order_id

    # 3. Update status to PREPARING
    res_st = client.patch(f"/api/orders/{order_id}/status", json={"status": "PREPARING"})
    assert res_st.status_code == 200
    assert res_st.json()["status"] == "PREPARING"

    # 4. Cancel order and restock
    res_c = client.post(f"/api/orders/{order_id}/cancel")
    assert res_c.status_code == 200
    assert res_c.json()["success"] is True

def test_calls_endpoint():
    res = client.get("/api/calls")
    assert res.status_code == 200
    assert "calls" in res.json()
