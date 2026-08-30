from src.config import settings
import uuid
from typing import List,Dict,Any,Optional
from src.database.db import get_db_cursor
from loguru import logger

def search_products(query: str = "") -> List[Dict[str, Any]]:
    """Search products where all words in query match product name or category."""
    with get_db_cursor() as cursor:
        words = query.strip().split()
        if not words:
            cursor.execute("SELECT id, name, category, price, unit, stock_quantity FROM products WHERE stock_quantity > 0 LIMIT 15")
        else:
            # Build dynamic WHERE clause: (name LIKE %w1% OR category LIKE %w1%) AND (name LIKE %w2% OR category LIKE %w2%)
            conditions = " AND ".join(["(LOWER(name) LIKE ? OR LOWER(category) LIKE ?)" for _ in words])
            params = []
            for w in words:
                params.extend([f"%{w.lower()}%", f"%{w.lower()}%"])
            
            cursor.execute(f"SELECT id, name, category, price, unit, stock_quantity FROM products WHERE {conditions} AND stock_quantity > 0", params)
        
        return [dict(row) for row in cursor.fetchall()]
def check_item_stock(product_name: str, requested_quantity: int = 1) -> Dict[str, Any]:
    """Check stock by matching product keywords."""
    with get_db_cursor() as cursor:
        words = product_name.strip().split()
        if not words:
            return {"in_stock": False, "reason": "No product specified."}
        
        conditions = " AND ".join(["LOWER(name) LIKE ?" for _ in words])
        params = [f"%{w.lower()}%" for w in words]
        
        cursor.execute(f"SELECT id, name, price, unit, stock_quantity FROM products WHERE {conditions}", params)
        item = cursor.fetchone()
        
        if not item:
            return {"in_stock": False, "reason": f"Item matching '{product_name}' was not found in catalog."}
        
        if item["stock_quantity"] < requested_quantity:
            return {
                "in_stock": False,
                "item_name": item["name"],
                "available_stock": item["stock_quantity"],
                "reason": f"Only {item['stock_quantity']} units of '{item['name']}' available."
            }
        
        return {
            "in_stock": True,
            "product_id": item["id"],
            "product_name": item["name"],
            "unit": item["unit"],
            "price": item["price"],
            "available_stock": item["stock_quantity"]
        }

def create_store_order(
    customer_name: str,
    customer_phone: str,
    items: List[Dict[str, Any]],  # e.g. [{"name": "Amul Milk", "quantity": 2}, ...]
    delivery_type: str = "delivery",  # 'delivery' or 'pickup'
    delivery_address: Optional[str] = None
) -> Dict[str, Any]:
    """
    Creates an atomic order, calculates totals, and deducts inventory.
    """
    if not items:
        return {"success": False, "error": "Order must contain at least one item."}
    
    with get_db_cursor() as cursor:
        resolved_items = []
        subtotal = 0.0
        # Step 1: Validate stock for all items atomically
        for it in items:
            p_name = it.get("name", "").strip()
            qty = int(it.get("quantity", 1))
            
            cursor.execute("SELECT id, name, price, unit, stock_quantity FROM products WHERE LOWER(name) LIKE LOWER(?)", (f"%{p_name}%",))
            product = cursor.fetchone()
            
            if not product:
                return {"success": False, "error": f"Item '{p_name}' not found."}
            if product["stock_quantity"] < qty:
                return {"success": False, "error": f"Insufficient stock for '{product['name']}'. Requested: {qty}, Available: {product['stock_quantity']}."}
            
            item_cost = product["price"] * qty
            subtotal += item_cost
            resolved_items.append({
                "product_id": product["id"],
                "name": product["name"],
                "quantity": qty,
                "price": product["price"],
                "unit": product["unit"],
                "subtotal": item_cost
            })
        # Step 2: Apply Delivery Fee Logic
        delivery_fee = 0.0
        if delivery_type.lower() == "delivery":
            delivery_fee = 0.0 if subtotal >= settings.FREE_DELIVERY_THRESHOLD else settings.DELIVERY_FEE
        
        total_amount = subtotal + delivery_fee
        order_id = f"DMART-{uuid.uuid4().hex[:4].upper()}"
        # Step 3: Insert Order
        cursor.execute("""
            INSERT INTO orders (order_id, customer_name, customer_phone, delivery_type, delivery_address, total_amount, status)
            VALUES (?, ?, ?, ?, ?, ?, 'CONFIRMED')
        """, (order_id, customer_name.strip(), customer_phone.strip(), delivery_type.lower(), delivery_address, total_amount))
        # Step 4: Insert Order Items & Deduct Stock
        for item in resolved_items:
            cursor.execute("""
                INSERT INTO order_items (order_id, product_id, product_name, quantity, unit_price, subtotal)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (order_id, item["product_id"], item["name"], item["quantity"], item["price"], item["subtotal"]))
            
            cursor.execute("""
                UPDATE products SET stock_quantity = stock_quantity - ? WHERE id = ?
            """, (item["quantity"], item["product_id"]))
        return {
            "success": True,
            "order_id": order_id,
            "customer_name": customer_name,
            "delivery_type": delivery_type,
            "delivery_address": delivery_address,
            "items": resolved_items,
            "subtotal": subtotal,
            "delivery_fee": delivery_fee,
            "total_amount": total_amount,
            "status": "CONFIRMED"
        }
def get_order_details(order_id: str) -> Dict[str, Any]:
    """Retrieve full details of an existing order."""
    with get_db_cursor() as cursor:
        cursor.execute("SELECT * FROM orders WHERE order_id = ?", (order_id.strip().upper(),))
        order = cursor.fetchone()
        if not order:
            return {"found": False, "error": f"No order found with ID {order_id}."}
        
        cursor.execute("SELECT product_name, quantity, unit_price, subtotal FROM order_items WHERE order_id = ?", (order_id.strip().upper(),))
        items = [dict(r) for r in cursor.fetchall()]
        
        res = dict(order)
        res["found"] = True
        res["items"] = items
        return res
def cancel_order(order_id: str) -> Dict[str, Any]:
    """Cancel order and restore product inventory."""
    with get_db_cursor() as cursor:
        cursor.execute("SELECT status FROM orders WHERE order_id = ?", (order_id.strip().upper(),))
        order = cursor.fetchone()
        if not order:
            return {"success": False, "error": f"Order {order_id} not found."}
        if order["status"] == "CANCELLED":
            return {"success": False, "error": f"Order {order_id} is already cancelled."}
        
        # Restore stock
        cursor.execute("SELECT product_id, quantity FROM order_items WHERE order_id = ?", (order_id.strip().upper(),))
        items = cursor.fetchall()
        for it in items:
            cursor.execute("UPDATE products SET stock_quantity = stock_quantity + ? WHERE id = ?", (it["quantity"], it["product_id"]))
            
        cursor.execute("UPDATE orders SET status = 'CANCELLED' WHERE order_id = ?", (order_id.strip().upper(),))
        return {"success": True, "message": f"Order {order_id} has been cancelled and items returned to stock."}
