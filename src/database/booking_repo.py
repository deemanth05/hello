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
    # Dairy & Milk Products
    "ಹಾಲು": ["milk", "amul taaza", "amul gold"],
    "ಹಾಲಿನ": ["milk", "amul taaza", "amul gold"],
    "ಹಾಲಿನ ಪ್ಯಾಕೆಟ್": ["amul taaza", "amul gold", "milk"],
    "haalu": ["milk", "amul taaza", "amul gold"],
    "milk": ["milk", "amul taaza", "amul gold"],
    "ಮೊಸರು": ["milk", "paneer"],
    "ಬೆಣ್ಣೆ": ["butter", "amul butter"],
    "butter": ["butter", "amul butter"],
    "dairy": ["milk", "butter", "paneer"],
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
    "ಕಡಲೆ ಬೇಳೆ": ["toor dal"],
    "ಹೆಸರು ಬೇಳೆ": ["moong dal"],
    "bele": ["toor dal", "moong dal"],
    "dal": ["dal", "toor dal", "moong dal"],
    "pulses": ["dal", "toor dal", "moong dal"],
    "ಉಪ್ಪು": ["salt", "tata salt"],
    "uppu": ["salt", "tata salt"],
    "salt": ["salt", "tata salt"],
    "ಎಣ್ಣೆ": ["sunflower oil", "mustard oil"],
    "ಅಡುಗೆ ಎಣ್ಣೆ": ["sunflower oil"],
    "ಸೂರ್ಯಕಾಂತಿ ಎಣ್ಣೆ": ["sunflower oil"],
    "enne": ["sunflower oil", "mustard oil"],
    "oil": ["oil", "sunflower", "mustard"],
    "cooking oil": ["sunflower oil", "mustard oil"],

    # Breakfast & Bakery
    "ತಿಂಡಿ": ["bread", "butter", "milk"],
    "tindi": ["bread", "butter", "milk"],
    "breakfast": ["bread", "butter", "milk"],
    "ಬ್ರೆಡ್": ["bread", "whole wheat bread"],
    "bread": ["whole wheat bread", "milk bread"],
    "ಮೊಟ್ಟೆ": ["eggs", "farm fresh eggs"],
    "motte": ["eggs", "farm fresh eggs"],
    "eggs": ["eggs", "farm fresh eggs"],
    "egg": ["eggs", "farm fresh eggs"],

    # Beverages (Tea & Coffee)
    "tea": ["red label", "taj mahal", "tea"],
    "chai": ["red label", "taj mahal", "tea"],
    "ಚಹಾ": ["red label", "taj mahal", "tea"],
    "ಟೀ": ["red label", "taj mahal", "tea"],
    "ಟೀ ಪುಡಿ": ["red label", "taj mahal", "tea"],
    "tea powder": ["red label", "taj mahal", "tea"],
    "ಕಾಫಿ": ["nescafe", "bru", "coffee"],
    "ಕಾಫಿ ಪುಡಿ": ["nescafe", "bru", "coffee"],
    "coffee": ["nescafe", "bru", "coffee"],
    "coffee powder": ["nescafe", "bru", "coffee"],
    "filter coffee": ["bru", "nescafe", "coffee"],

    # Snacks
    "ಮ್ಯಾಗಿ": ["maggi", "noodles"],
    "maggi": ["maggi", "noodles"],
    "maggie": ["maggi"],
    "noodles": ["maggi"],
    "ಬಿಸ್ಕತ್ತು": ["parle-g", "biscuits"],
    "ಬಿಸ್ಕಟ್": ["parle-g", "biscuits"],
    "biscuit": ["parle-g", "biscuits"],
    "biscuits": ["parle-g", "biscuits"],
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

def calculate_dynamic_eta(minutes: Optional[int] = None) -> str:
    """Calculates a realistic delivery ETA window based on current time."""
    if minutes is None:
        try:
            from src.database.settings_repo import get_setting
            minutes = int(get_setting("default_eta_minutes", "40"))
        except Exception:
            minutes = 40
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

def search_products(query: str = "", category: str = "", low_stock_only: bool = False, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Search products using exact words, category match, and semantic grocery synonyms.
    Supports dashboard filtering by category and low stock.
    """
    with get_db_cursor() as cursor:
        clean_q = query.strip().lower()
        clean_cat = category.strip()
        
        # If no query but category or low stock specified
        if not clean_q:
            where_clauses = []
            params = []
            if clean_cat:
                where_clauses.append("LOWER(category) = LOWER(?)")
                params.append(clean_cat)
            if low_stock_only:
                where_clauses.append("stock_quantity <= 10")
            
            where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
            cursor.execute(f"""
                SELECT id, name, category, price, unit, stock_quantity 
                FROM products 
                {where_sql}
                ORDER BY id DESC
                LIMIT ?
            """, params + [limit])
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
        CATEGORY_KEYWORDS = {
            "dairy", "bakery", "snacks", "beverages", "produce", 
            "household", "personal care", "groceries", "eggs"
        }
        conditions = []
        params = []
        for term in all_terms:
            if term.lower() in CATEGORY_KEYWORDS:
                conditions.append("(LOWER(name) LIKE ? OR LOWER(category) LIKE ?)")
                params.extend([f"%{term}%", f"%{term}%"])
            else:
                conditions.append("LOWER(name) LIKE ?")
                params.append(f"%{term}%")

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
            
            product = None
            prod_id = it.get("product_id") or it.get("id")
            if prod_id:
                cursor.execute("SELECT id, name, price, unit, stock_quantity FROM products WHERE id = ?", (prod_id,))
                product = cursor.fetchone()

            # Step 1: Exact match by name
            if not product and p_name:
                cursor.execute("SELECT id, name, price, unit, stock_quantity FROM products WHERE LOWER(name) = LOWER(?) LIMIT 1", (p_name,))
                product = cursor.fetchone()

            # Step 2: Match product by tokens (excluding pure numbers/units) with ranked relevance
            raw_tokens = p_name.split()
            significant_tokens = [t for t in raw_tokens if len(t) > 1 and not t.isdigit() and t.lower() not in {"liter", "litre", "1l", "1kg", "kg", "packet", "pack"}]
            if not product and significant_tokens:
                token_query = " AND ".join(["LOWER(name) LIKE ?" for _ in significant_tokens])
                token_params = [f"%{t.lower()}%" for t in significant_tokens]
                cursor.execute(f"""
                    SELECT id, name, price, unit, stock_quantity FROM products 
                    WHERE {token_query} 
                    ORDER BY 
                        CASE 
                            WHEN LOWER(name) = LOWER(?) THEN 1
                            WHEN LOWER(name) LIKE ? THEN 2
                            ELSE 3
                        END, id ASC 
                    LIMIT 1
                """, token_params + [p_name.lower(), f"%{p_name.lower()}%"])
                product = cursor.fetchone()
            
            # Step 3: Semantic search fallback (resolves Kannada terms like 'ಹಾಲು', 'ಸಕ್ಕರೆ', 'ಅಕ್ಕಿ', etc.)
            if not product:
                matches = search_products(p_name)
                if matches:
                    cursor.execute("SELECT id, name, price, unit, stock_quantity FROM products WHERE id = ?", (matches[0]["id"],))
                    product = cursor.fetchone()

            # Step 4: Loose OR fallback with significant tokens only
            if not product and len(significant_tokens) > 1:
                token_or = " OR ".join(["LOWER(name) LIKE ?" for _ in significant_tokens])
                cursor.execute(f"SELECT id, name, price, unit, stock_quantity FROM products WHERE {token_or} ORDER BY stock_quantity DESC LIMIT 1", [f"%{t.lower()}%" for t in significant_tokens])
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
        try:
            from src.database.settings_repo import get_setting
            free_threshold = float(get_setting("free_delivery_threshold", "800.0"))
            base_fee = float(get_setting("delivery_fee", "30.0"))
            eta_mins = int(get_setting("default_eta_minutes", "40"))
        except Exception:
            free_threshold = settings.FREE_DELIVERY_THRESHOLD
            base_fee = settings.DELIVERY_FEE
            eta_mins = 40

        delivery_fee = 0.0
        if delivery_type.lower() == "delivery":
            delivery_fee = 0.0 if subtotal >= free_threshold else base_fee
        
        total_amount = subtotal + delivery_fee
        order_id = f"DMART-{uuid.uuid4().hex[:4].upper()}"
        estimated_delivery_time = calculate_dynamic_eta(eta_mins)
        
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

place_order = create_store_order

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

def list_recent_orders(limit: int = 50, status_filter: str = "") -> List[Dict[str, Any]]:
    """Retrieve recent orders with optional status filter and line items."""
    with get_db_cursor() as cursor:
        if status_filter:
            cursor.execute("SELECT * FROM orders WHERE status = ? ORDER BY id DESC LIMIT ?", (status_filter.strip().upper(), limit))
        else:
            cursor.execute("SELECT * FROM orders ORDER BY id DESC LIMIT ?", (limit,))
        orders = [dict(r) for r in cursor.fetchall()]
        for o in orders:
            cursor.execute("SELECT product_name, quantity, unit_price, subtotal FROM order_items WHERE order_id = ?", (o["order_id"],))
            o["items"] = [dict(r) for r in cursor.fetchall()]
        return orders

def add_product(name: str, category: str, price: float, unit: str, stock_quantity: int = 50) -> Dict[str, Any]:
    """Adds a new product to the catalog."""
    clean_name = name.strip()
    clean_cat = category.strip() or "Groceries"
    clean_unit = unit.strip() or "1 packet"
    
    if not clean_name:
        return {"success": False, "error": "Product name cannot be empty."}
    if float(price) < 0:
        return {"success": False, "error": "Price must be greater than or equal to 0."}
        
    with get_db_cursor() as cursor:
        cursor.execute("SELECT id FROM products WHERE LOWER(name) = LOWER(?)", (clean_name,))
        if cursor.fetchone():
            return {"success": False, "error": f"Product '{clean_name}' already exists in catalog."}
            
        cursor.execute("""
            INSERT INTO products (name, category, price, unit, stock_quantity)
            VALUES (?, ?, ?, ?, ?)
        """, (clean_name, clean_cat, float(price), clean_unit, int(stock_quantity)))
        new_id = cursor.lastrowid
        
    logger.info(f"Added new product ID {new_id}: '{clean_name}' (Rs. {price})")
    return {
        "success": True,
        "message": f"Product '{clean_name}' added successfully.",
        "product": {
            "id": new_id,
            "name": clean_name,
            "category": clean_cat,
            "price": float(price),
            "unit": clean_unit,
            "stock_quantity": int(stock_quantity)
        }
    }

def update_product(product_id: int, name: str, category: str, price: float, unit: str, stock_quantity: int) -> Dict[str, Any]:
    """Updates an existing product in the catalog."""
    clean_name = name.strip()
    clean_cat = category.strip() or "Groceries"
    clean_unit = unit.strip() or "1 packet"
    
    if not clean_name:
        return {"success": False, "error": "Product name cannot be empty."}
    if float(price) < 0:
        return {"success": False, "error": "Price must be non-negative."}
        
    with get_db_cursor() as cursor:
        cursor.execute("SELECT id FROM products WHERE id = ?", (product_id,))
        if not cursor.fetchone():
            return {"success": False, "error": f"Product ID {product_id} not found."}
            
        cursor.execute("""
            UPDATE products
            SET name = ?, category = ?, price = ?, unit = ?, stock_quantity = ?
            WHERE id = ?
        """, (clean_name, clean_cat, float(price), clean_unit, int(stock_quantity), product_id))
        
    logger.info(f"Updated product ID {product_id}: '{clean_name}'")
    return {
        "success": True,
        "message": f"Product '{clean_name}' updated successfully.",
        "product": {
            "id": product_id,
            "name": clean_name,
            "category": clean_cat,
            "price": float(price),
            "unit": clean_unit,
            "stock_quantity": int(stock_quantity)
        }
    }

def delete_product(product_id: int) -> Dict[str, Any]:
    """Deletes a product from the catalog."""
    with get_db_cursor() as cursor:
        cursor.execute("SELECT name FROM products WHERE id = ?", (product_id,))
        row = cursor.fetchone()
        if not row:
            return {"success": False, "error": f"Product ID {product_id} not found."}
        p_name = row["name"]
        cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
        
    logger.info(f"Deleted product ID {product_id}: '{p_name}'")
    return {"success": True, "message": f"Product '{p_name}' deleted successfully."}

def update_product_stock(product_id: int, delta: int) -> Dict[str, Any]:
    """Adjusts stock quantity by delta (positive or negative)."""
    with get_db_cursor() as cursor:
        cursor.execute("SELECT name, stock_quantity FROM products WHERE id = ?", (product_id,))
        row = cursor.fetchone()
        if not row:
            return {"success": False, "error": f"Product ID {product_id} not found."}
        new_stock = max(0, row["stock_quantity"] + int(delta))
        cursor.execute("UPDATE products SET stock_quantity = ? WHERE id = ?", (new_stock, product_id))
        
    return {"success": True, "new_stock": new_stock, "name": row["name"]}

def update_order_status(order_id: str, new_status: str) -> Dict[str, Any]:
    """Updates order status and manages inventory restoration if cancelled."""
    valid_statuses = ["CONFIRMED", "PREPARING", "OUT_FOR_DELIVERY", "DELIVERED", "CANCELLED"]
    status_upper = new_status.strip().upper()
    if status_upper not in valid_statuses:
        return {"success": False, "error": f"Invalid status '{new_status}'. Allowed: {', '.join(valid_statuses)}"}
        
    with get_db_cursor() as cursor:
        cursor.execute("SELECT status FROM orders WHERE order_id = ?", (order_id.strip().upper(),))
        order = cursor.fetchone()
        if not order:
            return {"success": False, "error": f"Order {order_id} not found."}
            
        old_status = order["status"]
        if old_status == status_upper:
            return {"success": True, "message": f"Order status is already {status_upper}."}
            
        # If moving to CANCELLED from non-cancelled, restore stock
        if status_upper == "CANCELLED" and old_status != "CANCELLED":
            cursor.execute("SELECT product_id, quantity FROM order_items WHERE order_id = ?", (order_id.strip().upper(),))
            items = cursor.fetchall()
            for it in items:
                cursor.execute("UPDATE products SET stock_quantity = stock_quantity + ? WHERE id = ?", (it["quantity"], it["product_id"]))
                
        # If reviving from CANCELLED to active, deduct stock
        elif old_status == "CANCELLED" and status_upper != "CANCELLED":
            cursor.execute("SELECT product_id, quantity FROM order_items WHERE order_id = ?", (order_id.strip().upper(),))
            items = cursor.fetchall()
            for it in items:
                cursor.execute("UPDATE products SET stock_quantity = MAX(0, stock_quantity - ?) WHERE id = ?", (it["quantity"], it["product_id"]))
                
        cursor.execute("UPDATE orders SET status = ? WHERE order_id = ?", (status_upper, order_id.strip().upper()))
        
    logger.info(f"Order {order_id} status changed: {old_status} -> {status_upper}")
    return {"success": True, "order_id": order_id, "previous_status": old_status, "status": status_upper}

def get_dashboard_stats() -> Dict[str, Any]:
    """Aggregates real-time store metrics for the overview dashboard."""
    with get_db_cursor() as cursor:
        # Total customers
        cursor.execute("SELECT COUNT(*) as count FROM customers")
        total_customers = cursor.fetchone()["count"]
        
        # Products & low stock
        cursor.execute("SELECT COUNT(*) as total, SUM(CASE WHEN stock_quantity <= 10 THEN 1 ELSE 0 END) as low_stock FROM products")
        p_row = cursor.fetchone()
        total_products = p_row["total"] or 0
        low_stock_count = p_row["low_stock"] or 0
        
        # Total orders & revenue today
        cursor.execute("""
            SELECT 
                COUNT(*) as total_orders,
                SUM(CASE WHEN date(created_at) = date('now') THEN 1 ELSE 0 END) as orders_today,
                SUM(CASE WHEN date(created_at) = date('now') AND status != 'CANCELLED' THEN total_amount ELSE 0.0 END) as revenue_today,
                SUM(CASE WHEN status != 'CANCELLED' THEN total_amount ELSE 0.0 END) as total_revenue
            FROM orders
        """)
        o_row = cursor.fetchone()
        
        return {
            "total_customers": total_customers,
            "total_products": total_products,
            "low_stock_count": low_stock_count,
            "orders_today": o_row["orders_today"] or 0,
            "revenue_today": round(o_row["revenue_today"] or 0.0, 2),
            "total_orders": o_row["total_orders"] or 0,
            "total_revenue": round(o_row["total_revenue"] or 0.0, 2)
        }


