import os
import sqlite3
from typing import Generator
from contextlib import contextmanager
from loguru import logger
from src.config import settings

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.DATABASE_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.row_factory = sqlite3.Row
    return conn

@contextmanager
def get_db_cursor() -> Generator[sqlite3.Cursor, None, None]:
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
    """Initializes tables, indexes, and seeds DMart grocery catalog and customers."""
    with get_db_cursor() as cursor:
        # 1. Customers Table (Caller ID Registry)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone_number TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                address TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone_number);")

        # 2. Products / Inventory Table
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
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);")

        # 3. Orders Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT UNIQUE NOT NULL,
                customer_name TEXT NOT NULL,
                customer_phone TEXT NOT NULL,
                delivery_type TEXT NOT NULL,      -- 'delivery' or 'pickup'
                delivery_address TEXT,
                total_amount REAL NOT NULL,
                estimated_delivery_time TEXT,     -- e.g. '45 minutes (approx 6:15 PM)'
                status TEXT NOT NULL DEFAULT 'CONFIRMED', -- 'CONFIRMED', 'DELIVERED', 'CANCELLED'
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_phone ON orders(customer_phone);")

        # Migrate orders table if created previously without estimated_delivery_time
        cursor.execute("PRAGMA table_info(orders);")
        columns = [col["name"] for col in cursor.fetchall()]
        if "estimated_delivery_time" not in columns:
            cursor.execute("ALTER TABLE orders ADD COLUMN estimated_delivery_time TEXT;")

        # 4. Order Line Items Table
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

        # 5. Store Settings Table (Dynamic Configuration)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS store_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                description TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Seed initial store settings if not already present
        initial_settings = [
            ("store_name", getattr(settings, "STORE_NAME", "D mart Express"), "Display name of the supermarket"),
            ("store_phone", getattr(settings, "STORE_PHONE", "+18554161860"), "Public Twilio store phone number"),
            ("delivery_fee", str(getattr(settings, "DELIVERY_FEE", 30.0)), "Standard delivery fee in Rupees"),
            ("free_delivery_threshold", str(getattr(settings, "FREE_DELIVERY_THRESHOLD", 800.0)), "Order amount for free delivery"),
            ("default_eta_minutes", "40", "Standard delivery ETA in minutes"),
            ("active_language", "kn", "Primary voice assistant language (kn/en)"),
            ("welcome_greeting", "ನಮಸ್ಕಾರ, {store_name} ಗೆ ಸ್ವಾಗತ! ನಿಮಗೆ ಇಂದು ಯಾವ ದಿನಸಿ ಸಾಮಗ್ರಿಗಳು ಬೇಕು?", "Spoken greeting template")
        ]
        cursor.executemany("""
            INSERT INTO store_settings (key, value, description)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO NOTHING;
        """, initial_settings)

        # 6. Call Logs Table (Twilio Telephony Activity)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS call_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                call_sid TEXT UNIQUE NOT NULL,
                caller_phone TEXT NOT NULL,
                customer_name TEXT,
                call_status TEXT DEFAULT 'IN_PROGRESS',
                duration_seconds INTEGER DEFAULT 0,
                order_id TEXT,
                summary TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_call_logs_phone ON call_logs(caller_phone);")

        # 7. Seed Registered Customers for Testing (Generic Demo Profiles)
        test_customers = [
            ("+919876543210", "Rahul Sharma", "Flat 402, Sunshine Heights, Mumbai"),
            ("+919812345678", "Priya Patel", "House 12, Green Glen Layout, Bangalore"),
            ("+919765432100", "Ananya Iyer", "A-204, Palm Meadows, Whitefield, Bangalore"),
            ("9876543210", "Rahul Sharma", "Flat 402, Sunshine Heights, Mumbai"),
            ("9812345678", "Priya Patel", "House 12, Green Glen Layout, Bangalore"),
            ("+919008474173", "Vedashree", "Krishna Nagar, Bengaluru"),
            ("9008474173", "Vedashree", "Krishna Nagar, Bengaluru"),
        ]

        # Securely load custom caller profile from private environment variables
        env_phone = os.getenv("TEST_CUSTOMER_PHONE") or os.getenv("CALLER_PHONE")
        env_name = os.getenv("TEST_CUSTOMER_NAME") or os.getenv("CALLER_NAME", "Valued Customer")
        env_address = os.getenv("TEST_CUSTOMER_ADDRESS") or os.getenv("CALLER_ADDRESS", "Bengaluru, Karnataka")
        if env_phone:
            clean_p = env_phone.strip()
            test_customers.append((clean_p, env_name, env_address))
            if clean_p.startswith("+91"):
                test_customers.append((clean_p.replace("+91", ""), env_name, env_address))
            elif not clean_p.startswith("+"):
                test_customers.append((f"+91{clean_p}", env_name, env_address))

        cursor.executemany("""
            INSERT INTO customers (phone_number, name, address)
            VALUES (?, ?, ?)
            ON CONFLICT(phone_number) DO UPDATE SET
                name = excluded.name,
                address = excluded.address
        """, test_customers)

        # 6. Seed Popular Supermarket Products Catalog
        catalog = [
            # Groceries & Staples
            ("Fortune Sunlite Sunflower Oil 1L", "Groceries", 140.0, "1 Liter", 50),
            ("Fortune Premium Kachi Ghani Mustard Oil 1L", "Groceries", 155.0, "1 Liter", 40),
            ("India Gate Basmati Rice 5kg", "Groceries", 399.0, "5 kg", 30),
            ("Kolam Rice 5kg", "Groceries", 290.0, "5 kg", 35),
            ("Tata Salt 1kg", "Groceries", 28.0, "1 kg", 100),
            ("Aashirvaad Superior MP Atta 5kg", "Groceries", 245.0, "5 kg", 40),
            ("Aashirvaad Shudh Chakki Atta 10kg", "Groceries", 460.0, "10 kg", 25),
            ("Tata Sampann Toor Dal 1kg", "Groceries", 165.0, "1 kg", 60),
            ("Tata Sampann Moong Dal 1kg", "Groceries", 145.0, "1 kg", 50),
            ("Madhur Pure & Hygienic Sugar 1kg", "Groceries", 45.0, "1 kg", 80),
            
            # Dairy, Bakery & Eggs
            ("Amul Taaza Toned Milk 1L", "Dairy", 54.0, "1 Liter", 50),
            ("Amul Gold Full Cream Milk 1L", "Dairy", 68.0, "1 Liter", 40),
            ("Amul Butter 500g", "Dairy", 275.0, "500 g", 35),
            ("Amul Malai Paneer 200g", "Dairy", 90.0, "200 g", 30),
            ("Britannia 100% Whole Wheat Bread", "Bakery", 45.0, "400 g", 25),
            ("Britannia Milk Bread", "Bakery", 40.0, "400 g", 25),
            ("Farm Fresh Eggs (Pack of 6)", "Eggs", 50.0, "6 pieces", 50),
            ("Farm Fresh Eggs (Pack of 12)", "Eggs", 95.0, "12 pieces", 40),
            
            # Snacks & Beverages
            ("Maggi 2-Minute Noodles 4-Pack", "Snacks", 56.0, "280 g", 70),
            ("Red Label Tea 500g", "Beverages", 260.0, "500 g", 45),
            ("Taj Mahal Tea 500g", "Beverages", 320.0, "500 g", 30),
            ("Nescafe Classic Instant Coffee 50g", "Beverages", 195.0, "50 g", 30),
            ("BRU Instant Coffee 100g", "Beverages", 210.0, "100 g", 30),
            ("Parle-G Gold Biscuits 1kg", "Snacks", 120.0, "1 kg", 60),
            ("Lay's Classic Salted Chips 50g", "Snacks", 20.0, "50 g", 80),
            
            # Fresh Produce / Staples
            ("Fresh Red Onions 1kg", "Produce", 35.0, "1 kg", 80),
            ("Fresh Potatoes 1kg", "Produce", 30.0, "1 kg", 80),
            ("Fresh Hybrid Tomatoes 1kg", "Produce", 25.0, "1 kg", 60),
            
            # Household & Personal Care
            ("Surf Excel Easy Wash Detergent Powder 1kg", "Household", 135.0, "1 kg", 50),
            ("Vim Lemon Dishwash Gel 500ml", "Household", 105.0, "500 ml", 40),
            ("Dettol Original Soap (Pack of 3)", "Personal Care", 110.0, "3x75g", 40),
            ("Colgate Strong Teeth Toothpaste 200g", "Personal Care", 98.0, "200 g", 50),
        ]
        
        cursor.executemany("""
            INSERT INTO products (name, category, price, unit, stock_quantity)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                category = excluded.category,
                price = excluded.price,
                unit = excluded.unit
        """, catalog)

    logger.info(f"DMart database initialized successfully at {settings.DATABASE_PATH}")

if __name__ == "__main__":
    init_db()

