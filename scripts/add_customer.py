import sys
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.database.db import init_db
from src.database.customer_repo import register_customer, get_customer, list_all_customers

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def main():
    init_db()
    
    if len(sys.argv) >= 4:
        phone = sys.argv[1].strip()
        name = sys.argv[2].strip()
        address = sys.argv[3].strip()
    elif len(sys.argv) == 2 and sys.argv[1] in ["--list", "-l", "list"]:
        customers = list_all_customers()
        print(f"\nTotal Registered Customers: {len(customers)}")
        print("-" * 70)
        for c in customers:
            print(f"ID: {c['id']:<3} | Phone: {c['phone_number']:<15} | Name: {c['name']:<15} | Address: {c['address']}")
        print("-" * 70)
        return
    else:
        print("=== Register Customer for DMart Express Voice AI ===")
        phone = input("Enter Phone Number (e.g. +919876543210): ").strip()
        if not phone:
            print("Error: Phone number is required.")
            return
        name = input("Enter Customer Name (e.g. Deemanth): ").strip()
        if not name:
            print("Error: Name is required.")
            return
        address = input("Enter Delivery Address (e.g. Krishna Nagar, Bengaluru): ").strip()
        if not address:
            print("Error: Address is required.")
            return

    res = register_customer(phone_number=phone, name=name, address=address)
    if res.get("success"):
        print(f"\n[SUCCESS] Successfully registered customer!")
        print(f"  Name:    {res['name']}")
        print(f"  Phone:   {res['phone_number']}")
        print(f"  Address: {res['address']}")
        print(f"\nThe Voice Bot will now recognize this caller by name and skip asking for address!")
    else:
        print(f"\n[ERROR] Failed to register: {res.get('error')}")

if __name__ == "__main__":
    main()
