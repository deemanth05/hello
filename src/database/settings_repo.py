from typing import Dict, Any, Optional
from loguru import logger
from src.database.db import get_db_cursor
from src.config import settings

def get_setting(key: str, default: Optional[str] = None) -> str:
    """Retrieve a single setting value from store_settings table."""
    with get_db_cursor() as cursor:
        cursor.execute("SELECT value FROM store_settings WHERE key = ?", (key.strip(),))
        row = cursor.fetchone()
        if row and row["value"] is not None:
            return str(row["value"])
    
    # Fallback to defaults from settings object if not in DB
    attr_map = {
        "store_name": getattr(settings, "STORE_NAME", "D mart Express"),
        "store_phone": getattr(settings, "STORE_PHONE", "+18554161860"),
        "delivery_fee": str(getattr(settings, "DELIVERY_FEE", 30.0)),
        "free_delivery_threshold": str(getattr(settings, "FREE_DELIVERY_THRESHOLD", 800.0)),
        "default_eta_minutes": "40",
        "active_language": "kn"
    }
    return attr_map.get(key.strip(), default if default is not None else "")

def get_all_settings() -> Dict[str, Any]:
    """Retrieve all configuration key-values as a dictionary."""
    with get_db_cursor() as cursor:
        cursor.execute("SELECT key, value, description, updated_at FROM store_settings")
        rows = cursor.fetchall()
        result = {}
        for r in rows:
            result[r["key"]] = {
                "value": r["value"],
                "description": r["description"],
                "updated_at": r["updated_at"]
            }
        
        # Ensure standard keys are present with typed quick access
        flat = {k: v["value"] for k, v in result.items()}
        return {
            "settings": flat,
            "details": result
        }

def update_setting(key: str, value: str, description: Optional[str] = None) -> bool:
    """Update or insert a single configuration key."""
    clean_k = key.strip()
    clean_v = str(value).strip()
    with get_db_cursor() as cursor:
        cursor.execute("""
            INSERT INTO store_settings (key, value, description, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
        """, (clean_k, clean_v, description or ""))
    logger.info(f"Store setting updated: {clean_k} = {clean_v}")
    return True

def update_settings(updates: Dict[str, Any]) -> bool:
    """Update multiple configuration settings at once."""
    with get_db_cursor() as cursor:
        for k, v in updates.items():
            if v is not None:
                clean_k = str(k).strip()
                clean_v = str(v).strip()
                cursor.execute("""
                    INSERT INTO store_settings (key, value, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        updated_at = CURRENT_TIMESTAMP
                """, (clean_k, clean_v))
    logger.info(f"Store settings batch updated: {list(updates.keys())}")
    return True
