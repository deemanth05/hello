import datetime
import uuid
import re
from typing import List, Dict, Any, Optional
from src.config import settings
from src.database.db import get_db_cursor
from src.database.customer_repo import get_customer
from loguru import logger

# Common grocery synonym / intent mappings for general voice requests (English, Kannada Script, and Kanglish)
SEMANTIC_SYNONYMS = {
    # Milk / Dairy
    "tea": ["tea", "sugar", "milk"],
    "chai": ["tea", "sugar", "milk"],
    "ಚಹಾ": ["tea", "sugar", "milk"],
    "ಟೀ": ["tea", "sugar", "milk"],
    "ಹಾಲು": ["milk", "amul taaza", "amul gold"],
    "haalu": ["milk", "amul taaza", "amul gold"],
    "milk": ["milk", "amul taaza", "amul gold"],
    "ಮೊಸರು": ["milk", "paneer"],
    "ಬೆಣ್ಣೆ": ["butter", "amul butter"],
    "butter": ["butter", "amul butter"],
    "dairy": ["milk", "butter", "paneer", "eggs"],
    "ಪನೀರ್": ["paneer", "amul malai paneer"],
    "paneer": ["paneer", "amul malai paneer"],

    # Staples & Groceries
    "ಸಕ್ಕರೆ": ["sugar", "madhur"],
    "sakkare": ["sugar", "madhur"],
    "sugar": ["sugar", "madhur"],
    "ಅಕ್ಕಿ": ["rice", "basmati", "kolam"],
    "akki": ["rice", "basmati", "kolam"],
    "rice": ["basmati", "rice", "kolam"],
    "ಹಿಟ್ಟು": ["atta", "aashirvaad"],
    "ಅಟ್ಟಾ": ["atta", "aashirvaad"],
    "hittu": ["atta", "aashirvaad"],
    "atta": ["atta", "aashirvaad", "wheat"],
    "ಗೋಧಿ": ["atta", "aashirvaad"],
    "flour": ["atta", "aashirvaad"],
    "ಬೇಳೆ": ["toor dal", "moong dal"],
    "ತೊಗರಿ ಬೇಳೆ": ["toor dal"],
    "bele": ["toor dal", "moong dal"],
    "dal": ["dal", "toor dal", "moong dal"],
    "pulses": ["dal", "toor dal", "moong dal"],
    "ಉಪ್ಪು": ["salt", "tata salt"],
    "uppu": ["salt", "tata salt"],
    "salt": ["salt", "tata salt"],
    "ಎಣ್ಣೆ": ["sunflower oil", "mustard oil"],
    "ಅಡುಗೆ ಎಣ್ಣೆ": ["sunflower oil"],
    "enne": ["sunflower oil", "mustard oil"],
    "oil": ["oil", "sunflower", "mustard"],
    "cooking oil": ["sunflower oil", "mustard oil"],

    # Breakfast & Bakery
    "ತಿಂಡಿ": ["bread", "eggs", "butter", "milk"],
    "tindi": ["bread", "eggs", "butter", "milk"],
    "breakfast": ["bread", "eggs", "butter", "milk"],
    "ಬ್ರೆಡ್": ["bread", "whole wheat bread"],
    "bread": ["whole wheat bread", "milk bread"],
    "ಮೊಟ್ಟೆ": ["eggs", "farm fresh eggs"],
    "motte": ["eggs", "farm fresh eggs"],
    "eggs": ["eggs", "farm fresh eggs"],

    # Beverages & Coffee
    "ಕಾಫಿ": ["coffee", "nescafe", "bru"],
    "coffee": ["coffee", "sugar", "milk", "nescafe", "bru"],
    "filter coffee": ["coffee", "bru"],

    # Snacks
    "ಮ್ಯಾಗಿ": ["maggi", "noodles"],
    "maggi": ["maggi", "noodles"],
    "maggie": ["maggi"],
    "noodles": ["maggi"],
    "ಬಿಸ್ಕತ್ತು": ["biscuits", "parle-g"],
    "biscuit": ["biscuits", "parle-g"],
    "snacks": ["maggi", "chips", "biscuits"],
    "ಚಿಪ್ಸ್": ["chips", "lays"],
    "chips": ["chips", "lays"],

    # Vegetables & Produce
    "ತರಕಾರಿ": ["onions", "potatoes", "tomatoes"],
    "tarakari": ["onions", "potatoes", "tomatoes"],
    "vegetables": ["onions", "potatoes", "tomatoes"],
    "veggies": ["onions", "potatoes", "tomatoes"],
    "ಈರುಳ್ಳಿ": ["onions", "red onions"],
    "eerulli": ["onions", "red onions"],
    "ಆಲೂಗಡ್ಡೆ": ["potatoes"],
    "aalugadde": ["potatoes"],
    "ಟೊಮೆಟೊ": ["tomatoes"],
    "tomato": ["tomatoes"],

    # Cleaning & Personal Care
    "ಸಾಬೂನು": ["soap", "dettol"],
    "ಸೋಪು": ["soap", "dettol"],
    "saaboonu": ["soap", "dettol"],
    "soap": ["dettol", "soap"],
    "ಸರ್ಫ್": ["surf excel", "detergent"],
    "ವಾಷಿಂಗ್ ಪೌಡರ್": ["surf excel", "detergent"],
    "detergent": ["surf excel", "detergent"],
    "cleaning": ["detergent", "dishwash", "surf excel", "vim"],
    "ವಿಮ್": ["vim", "dishwash"],
    "vim": ["vim", "dishwash"]
}

def calculate_dynamic_eta(minutes: int = 40) -> str:
    """Calculates a realistic delivery ETA window based on current time."""
    now = datetime.datetime.now()
    arrival_time = now + datetime.timedelta(minutes=minutes)
    time_str = arrival_time.strftime("%I:%M %p").lstrip("0")
    return f"{minutes-5} to {minutes+5} minutes (approx {time_str})"

STOP_WORDS = {
    "i", "want", "to", "make", "a", "an", "the", "some", "need", "for", 
    "please", "get", "give", "and", "of", "in", "with", "buy", "order", 
    "item", "items", "stuff", "product", "products", "do", "you", "have", "can", "me",
    # Kannada stopwords
    "ನನಗೆ", "ಬೇಕು", "ದಯವಿಟ್ಟು", "ಮತ್ತು", "ಒಂದು", "ಎರಡು", "ಸ್ವಲ್ಪ", "ತಂದುಕೊಡಿ", "ಕೊಡಿ",
    "nanage", "beku", "dayavittu", "matthu", "ondu", "eradu", "kodi"
}

def search_products(query: str = "") -> List[Dict[str, Any]]:
    """
    Search products using exact words, category match, and semantic grocery synonyms.
    """
    with get_db_cursor() as cursor:
        clean_q = query.strip().lower()
        if not clean_q:
            cursor.execute("""
                SELECT id, name, category, price, unit, stock_quantity 
                FROM products 
                WHERE stock_quantity > 0 
                LIMIT 15
            """)
            return [dict(row) for row in cursor.fetchall()]

        # 1. Check for specific synonym triggers in query
        matched_synonyms = []
        for key, synonyms in SEMANTIC_SYNONYMS.items():
            if key in clean_q:
                matched_synonyms.extend(synonyms)

        # 2. Extract meaningful search terms (remove stopwords & 1-char noise)
        raw_words = re.findall(r"[\w]+", clean_q)
        search_terms = [w for w in raw_words if w not in STOP_WORDS and len(w) > 1]
        
        # Combine search terms and synonyms
        all_terms = list(dict.fromkeys(matched_synonyms + search_terms))
        
        if not all_terms:
            all_terms = [w for w in raw_words if w not in STOP_WORDS]
            
        if not all_terms:
            cursor.execute("SELECT id, name, category, price, unit, stock_quantity FROM products WHERE stock_quantity > 0 LIMIT 10")
            return [dict(row) for row in cursor.fetchall()]

        # 3. Match products containing any relevant term
        conditions = []
        params = []
        for term in all_terms:
            conditions.append("(LOWER(name) LIKE ? OR LOWER(category) LIKE ?)")
            params.extend([f"%{term}%", f"%{term}%"])

        query_sql = f"""
            SELECT id, name, category, price, unit, stock_quantity 
            FROM products 
            WHERE ({' OR '.join(conditions)}) AND stock_quantity > 0
            ORDER BY 
                CASE 
                    WHEN LOWER(name) LIKE ? THEN 1
                    WHEN LOWER(name) LIKE ? THEN 2
                    ELSE 3
                END, name ASC
            LIMIT 10
        """
        params.extend([f"{clean_q}%", f"%{clean_q}%"])
        
        cursor.execute(query_sql, params)
        rows = cursor.fetchall()
        
        if not rows:
            cursor.execute("SELECT id, name, category, price, unit, stock_quantity FROM products WHERE stock_quantity > 0 LIMIT 5")
            rows = cursor.fetchall()
            
        return [dict(row) for row in rows]

def check_item_stock(product_name: str, requested_quantity: int = 1) -> Dict[str, Any]:
    """Check stock by matching product keywords accurately."""
    with get_db_cursor() as cursor:
        words = product_name.strip().split()
        if not words:
            return {"in_stock": False, "reason": "No product specified."}
        
        conditions = " AND ".join(["LOWER(name) LIKE ?" for _ in words])
        params = [f"%{w.lower()}%" for w in words]
        
        cursor.execute(f"SELECT id, name, price, unit, stock_quantity FROM products WHERE {conditions}", params)
        item = cursor.fetchone()
        
        # Fallback to loose OR matching if exact phrase did not match
        if not item and len(words) > 1:
            or_conditions = " OR ".join(["LOWER(name) LIKE ?" for _ in words])
            cursor.execute(f"SELECT id, name, price, unit, stock_quantity FROM products WHERE {or_conditions} ORDER BY stock_quantity DESC LIMIT 1", params)
            item = cursor.fetchone()
        
        if not item:
            # Fallback to semantic search (handles Kannada terms like 'ಹಾಲು', 'ಅಕ್ಕಿ', etc.)
            matches = search_products(product_name)
            if matches:
                cursor.execute("SELECT id, name, price, unit, stock_quantity FROM products WHERE id = ?", (matches[0]["id"],))
                item = cursor.fetchone()

        if not item:
            return {"in_stock": False, "reason": f"Item matching '{product_name}' was not found in catalog."}
        
        try:
            req_qty = int(requested_quantity)
        except (ValueError, TypeError):
            req_qty = 1

        if item["stock_quantity"] < req_qty:
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
    Creates an atomic order, deducts stock, auto-populates registered address if omitted, 
    and generates dynamic ETA window.
    """
    if not items:
        return {"success": False, "error": "Order must contain at least one item."}
    
    # Auto-resolve customer details from DB if missing
    clean_phone = customer_phone.strip()
    cust = get_customer(clean_phone)
    if cust:
        if not customer_name:
            customer_name = cust["name"]
        if not delivery_address and delivery_type.lower() == "delivery":
            delivery_address = cust["address"]

    if not customer_name:
        customer_name = "Valued Customer"

    with get_db_cursor() as cursor:
        resolved_items = []
        subtotal = 0.0
        
        # Step 1: Validate stock for all items atomically
        for it in items:
            p_name = it.get("name", "").strip()
            try:
                qty = int(it.get("quantity", 1))
            except (ValueError, TypeError):
                qty = 1
            if qty <= 0:
                qty = 1
            
            # Match product by tokens
            tokens = p_name.split()
            token_query = " AND ".join(["LOWER(name) LIKE ?" for _ in tokens])
            token_params = [f"%{t.lower()}%" for t in tokens]
            
            cursor.execute(f"SELECT id, name, price, unit, stock_quantity FROM products WHERE {token_query}", token_params)
            product = cursor.fetchone()
            
            # Loose fallback
            if not product and len(tokens) > 1:
                token_or = " OR ".join(["LOWER(name) LIKE ?" for _ in tokens])
                cursor.execute(f"SELECT id, name, price, unit, stock_quantity FROM products WHERE {token_or} LIMIT 1", token_params)
                product = cursor.fetchone()
            
            # Semantic search fallback (handles Kannada terms like 'ಹಾಲು', 'ಸಕ್ಕರೆ', etc.)
            if not product:
                matches = search_products(p_name)
                if matches:
                    cursor.execute("SELECT id, name, price, unit, stock_quantity FROM products WHERE id = ?", (matches[0]["id"],))
                    product = cursor.fetchone()
            
            if not product:
                return {"success": False, "error": f"Item '{p_name}' not found in catalog."}
            if product["stock_quantity"] < qty:
                return {
                    "success": False, 
                    "error": f"Insufficient stock for '{product['name']}'. Requested: {qty}, Available: {product['stock_quantity']}."
                }
            
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
        estimated_delivery_time = calculate_dynamic_eta(35)
        
        # Step 3: Insert Order
        cursor.execute("""
            INSERT INTO orders (order_id, customer_name, customer_phone, delivery_type, delivery_address, total_amount, estimated_delivery_time, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'CONFIRMED')
        """, (order_id, customer_name.strip(), clean_phone, delivery_type.lower(), delivery_address, total_amount, estimated_delivery_time))
        
        # Step 4: Insert Order Items & Deduct Stock
        for item in resolved_items:
            cursor.execute("""
                INSERT INTO order_items (order_id, product_id, product_name, quantity, unit_price, subtotal)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (order_id, item["product_id"], item["name"], item["quantity"], item["price"], item["subtotal"]))
            
            cursor.execute("""
                UPDATE products SET stock_quantity = stock_quantity - ? WHERE id = ?
            """, (item["quantity"], item["product_id"]))
            
        logger.info(f"Successfully placed order {order_id} for {customer_name} ({clean_phone}). Total: Rs. {total_amount}, ETA: {estimated_delivery_time}")
        
        return {
            "success": True,
            "order_id": order_id,
            "customer_name": customer_name,
            "customer_phone": clean_phone,
            "delivery_type": delivery_type,
            "delivery_address": delivery_address or "Store Pickup",
            "items": resolved_items,
            "subtotal": subtotal,
            "delivery_fee": delivery_fee,
            "total_amount": total_amount,
            "estimated_delivery_time": estimated_delivery_time,
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

def list_recent_orders(limit: int = 20) -> List[Dict[str, Any]]:
    """Retrieve recent orders with their line items."""
    with get_db_cursor() as cursor:
        cursor.execute("SELECT * FROM orders ORDER BY id DESC LIMIT ?", (limit,))
        orders = [dict(r) for r in cursor.fetchall()]
        for o in orders:
            cursor.execute("SELECT product_name, quantity, unit_price, subtotal FROM order_items WHERE order_id = ?", (o["order_id"],))
            o["items"] = [dict(r) for r in cursor.fetchall()]
        return orders

