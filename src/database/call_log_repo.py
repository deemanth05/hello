from typing import List, Dict, Any, Optional
from loguru import logger
from src.database.db import get_db_cursor

def log_call_start(call_sid: str, caller_phone: str, customer_name: Optional[str] = None) -> None:
    """Record the initiation of an incoming phone call."""
    if not call_sid:
        return
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                INSERT INTO call_logs (call_sid, caller_phone, customer_name, call_status)
                VALUES (?, ?, ?, 'IN_PROGRESS')
                ON CONFLICT(call_sid) DO UPDATE SET
                    caller_phone = excluded.caller_phone,
                    customer_name = excluded.customer_name,
                    call_status = 'IN_PROGRESS'
            """, (call_sid.strip(), caller_phone.strip(), customer_name or "Caller"))
        logger.info(f"Logged call start for SID {call_sid} from {caller_phone}")
    except Exception as e:
        logger.error(f"Error logging call start: {e}")

def log_call_end(
    call_sid: str, 
    status: str = "COMPLETED", 
    duration_seconds: int = 0, 
    order_id: Optional[str] = None, 
    summary: Optional[str] = None
) -> None:
    """Record call conclusion with duration and linked order."""
    if not call_sid:
        return
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                UPDATE call_logs
                SET call_status = ?,
                    duration_seconds = ?,
                    order_id = COALESCE(?, order_id),
                    summary = COALESCE(?, summary)
                WHERE call_sid = ?
            """, (status, max(0, duration_seconds), order_id, summary, call_sid.strip()))
        logger.info(f"Logged call end for SID {call_sid}: status={status}, duration={duration_seconds}s, order={order_id}")
    except Exception as e:
        logger.error(f"Error logging call end: {e}")

def list_recent_calls(limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieve recent call records."""
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT id, call_sid, caller_phone, customer_name, call_status, duration_seconds, order_id, summary, created_at
                FROM call_logs
                ORDER BY id DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error listing recent calls: {e}")
        return []
