from loguru import logger      
import sqlite3
from typing import Generator
from contextlib import contextmanager
from src.config import settings

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.DATABASE_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.row_factory = sqlite3.Row
    return conn

@contextmanager
def get_db_cursor() -> Generator[sqlite3.Cursor,None,None]:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        yield cursor
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Database Error: {str(e)}")
        raise
    finally:
        conn.close()

def init_db():
    """Initializes tables and seeds DMart grocery catalog."""
    with get_db_cursor() as cursor:

        # 1. Products / Inventory
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                category TEXT NOT NULL,
                price REAL NOT NULL,
                unit TEXT NOT NULL,          -- e.g. '1 kg', '500 ml', '1 packet'
                stock_quantity INTEGER NOT NULL DEFAULT 50
            );
        """)

        # 2. Orders table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT UNIQUE NOT NULL,
                customer_name TEXT NOT NULL,
                customer_phone TEXT NOT NULL,
                delivery_type TEXT NOT NULL,      -- 'delivery' or 'pickup'
                delivery_address TEXT,
                total_amount REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'CONFIRMED', -- 'CONFIRMED', 'DELIVERED', 'CANCELLED'
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 3. Order Line Items
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT NOT NULL,
                product_id INTEGER NOT NULL,
                product_name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                subtotal REAL NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders (order_id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products (id)
            );
        """)

        # 4. Seed Popular Supermarket Products
        catalog = [
            # Groceries & Staples
            ("Fortune Sunlite SunflowerOil 1L", "Groceries", 140.0, "1 Liter", 50),
            ("India Gate Basmati Rice 5kg", "Groceries", 399.0, "5 kg", 30),
            ("Tata Salt 1kg", "Groceries", 28.0, "1 kg", 100),
            ("Aashirvaad Superior MP Atta 5kg", "Groceries", 245.0, "5 kg", 40),
            ("Tata Sampann Toor Dal 1kg", "Groceries", 165.0, "1 kg", 60),
            ("Madhur Pure Sugar 1kg", "Groceries", 45.0, "1 kg", 80),
            
            # Dairy & Bakery
            ("Amul Taaza Toned Milk 1L", "Dairy", 54.0, "1 Liter", 40),
            ("Amul Butter 500g", "Dairy", 275.0, "500 g", 35),
            ("Britannia 100% Whole Wheat Bread", "Bakery", 45.0, "400 g", 25),
            ("Farm Fresh Eggs (Pack of 6)", "Dairy", 50.0, "6 pieces", 50),
            
            # Snacks & Beverages
            ("Maggi 2-Minute Noodles 4-Pack", "Snacks", 56.0, "280 g", 70),
            ("Red Label Tea 500g", "Beverages", 260.0, "500 g", 45),
            ("Nescafe Classic Instant Coffee 50g", "Beverages", 195.0, "50 g", 30),
            
            # Household & Personal Care
            ("Surf Excel Easy Wash Detergent Powder 1kg", "Household", 135.0, "1 kg", 50),
            ("Dettol Original Soap (Pack of 3)", "Personal Care", 110.0, "3x75g", 40),
        ]
        
        cursor.executemany("""
            INSERT OR IGNORE INTO products (name, category, price, unit, stock_quantity)
            VALUES (?, ?, ?, ?, ?)
        """, catalog)

    logger.info(f"D Mart databse initiaized at {settings.DATABASE_PATH}")

if __name__ == "__main__":
    init_db()

