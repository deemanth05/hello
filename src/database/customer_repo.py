import re
from typing import Optional, Dict, Any, List
from src.database.db import get_db_cursor
from loguru import logger

def normalize_phone(phone: str) -> str:
    """
    Normalizes phone numbers to standard 10-digit format or E.164.
    Extracts the last 10 digits if it contains a 10-digit Indian mobile number.
    """
    if not phone:
        return ""
    digits = re.sub(r"\D", "", phone)
    # If 12 digits starting with 91, take last 10 digits
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits

def get_customer(phone_number: str) -> Optional[Dict[str, Any]]:
    """
    Deterministic customer lookup by phone number.
    Searches both raw format, +91 prefixed, and normalized 10-digit format.
    """
    if not phone_number:
        return None
        
    raw = phone_number.strip()
    norm = normalize_phone(raw)
    
    candidates = list(dict.fromkeys([
        raw,
        norm,
        f"+91{norm}" if norm else raw,
        f"0{norm}" if norm else raw
    ]))
    
    with get_db_cursor() as cursor:
        placeholders = ",".join(["?"] * len(candidates))
        cursor.execute(
            f"SELECT id, phone_number, name, address, created_at FROM customers WHERE phone_number IN ({placeholders}) LIMIT 1",
            candidates
        )
        row = cursor.fetchone()
        if row:
            return dict(row)
            
    return None

def register_customer(phone_number: str, name: str, address: str) -> Dict[str, Any]:
    """
    Atomically registers or updates a customer with deterministic phone normalization.
    """
    clean_name = name.strip()
    clean_address = address.strip()
    clean_phone = phone_number.strip()
    norm = normalize_phone(clean_phone)
    canonical_phone = f"+91{norm}" if len(norm) == 10 else clean_phone

    if not clean_name:
        return {"success": False, "error": "Customer name is required for registration."}
    if not clean_address:
        return {"success": False, "error": "Customer delivery address is required for registration."}
    if not clean_phone:
        return {"success": False, "error": "Phone number is required for registration."}

    # Check if already registered
    existing = get_customer(clean_phone)
    with get_db_cursor() as cursor:
        if existing:
            # Update existing customer
            cursor.execute("""
                UPDATE customers
                SET name = ?, address = ?
                WHERE id = ?
            """, (clean_name, clean_address, existing["id"]))
            logger.info(f"Updated existing customer ID {existing['id']}: {clean_name} ({canonical_phone})")
            return {
                "success": True,
                "customer_id": existing["id"],
                "name": clean_name,
                "phone_number": canonical_phone,
                "address": clean_address,
                "message": "Customer profile updated successfully."
            }
        else:
            # Insert new customer (insert canonical and raw forms for fast lookup)
            cursor.execute("""
                INSERT INTO customers (phone_number, name, address)
                VALUES (?, ?, ?)
            """, (canonical_phone, clean_name, clean_address))
            new_id = cursor.lastrowid
            
            # Also insert raw 10-digit variant if different
            if norm and norm != canonical_phone:
                cursor.execute("""
                    INSERT OR IGNORE INTO customers (phone_number, name, address)
                    VALUES (?, ?, ?)
                """, (norm, clean_name, clean_address))
                
            logger.info(f"Registered new customer ID {new_id}: {clean_name} ({canonical_phone})")
            return {
                "success": True,
                "customer_id": new_id,
                "name": clean_name,
                "phone_number": canonical_phone,
                "address": clean_address,
                "message": "Customer registered successfully."
            }

def update_customer_address(phone_number: str, address: str) -> Dict[str, Any]:
    """Updates delivery address for a registered customer."""
    customer = get_customer(phone_number)
    if not customer:
        return {"success": False, "error": "Customer not found."}
    
    with get_db_cursor() as cursor:
        cursor.execute("UPDATE customers SET address = ? WHERE phone_number = ? OR id = ?", (address.strip(), phone_number, customer["id"]))
    return {"success": True, "message": "Address updated successfully.", "address": address.strip()}

def list_all_customers() -> List[Dict[str, Any]]:
    """Returns a list of all registered customers."""
    with get_db_cursor() as cursor:
        cursor.execute("SELECT id, phone_number, name, address, created_at FROM customers ORDER BY id DESC")
        return [dict(r) for r in cursor.fetchall()]
