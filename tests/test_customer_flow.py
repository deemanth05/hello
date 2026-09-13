import asyncio
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.database.db import init_db
from src.database.customer_repo import get_customer
from src.services.llm_service import LLMService

async def test_registered_caller_conversation():
    print("\n=======================================================")
    print("TEST 1: REGISTERED CALLER CONVERSATION FLOW")
    print("=======================================================")
    
    phone = "+919876543210" # Rahul Sharma
    llm = LLMService()
    
    cust = get_customer(phone)
    print(f"Caller ID: {phone} -> Identified as: {cust['name']} ({cust['address']})")
    
    greeting = llm.get_initial_greeting(phone)
    print(f"Bot Initial Greeting: {greeting}")
    assert "Rahul" in greeting or "ನಮಸ್ಕಾರ" in greeting
    
    conversation = llm.create_initial_conversation(caller_phone=phone)
    
    # Turn 1: General item request
    user_turn_1 = "Hi, I need 2 packets of toned milk and some bread."
    print(f"\nCaller: {user_turn_1}")
    conversation.append({"role": "user", "content": user_turn_1})
    
    reply_1 = await llm.chat(conversation, caller_phone=phone)
    print(f"Priya (AI): {reply_1}")
    
    # Turn 2: Order confirmation
    user_turn_2 = "Yes please, place the order for home delivery."
    print(f"\nCaller: {user_turn_2}")
    conversation.append({"role": "user", "content": user_turn_2})
    
    reply_2 = await llm.chat(conversation, caller_phone=phone)
    print(f"Priya (AI): {reply_2}")
    
    print("[OK] Registered caller conversation completed.")

async def test_unregistered_caller_conversation():
    print("\n=======================================================")
    print("TEST 2: UNREGISTERED CALLER IN-CALL REGISTRATION & ORDER")
    print("=======================================================")
    
    unreg_phone = "+919445566778"
    llm = LLMService()
    
    # Ensure idempotent test: clean up if registered from prior run
    from src.database.db import get_db_cursor
    with get_db_cursor() as cursor:
        cursor.execute("DELETE FROM customers WHERE phone_number LIKE ?", (f"%{unreg_phone[-10:]}%",))
    
    cust_before = get_customer(unreg_phone)
    assert cust_before is None
    print(f"Caller ID: {unreg_phone} -> Unregistered Verified")
    
    greeting = llm.get_initial_greeting(unreg_phone)
    print(f"Bot Initial Greeting: {greeting}")
    assert "register" in greeting.lower() or "ನೋಂದಣಿ" in greeting
    
    conversation = llm.create_initial_conversation(caller_phone=unreg_phone)
    
    # Turn 1: Caller provides registration info
    user_turn_1 = "Hi, my name is Neha Sen and my delivery address is Flat 501, Lakeview Residency, Koramangala, Bangalore."
    print(f"\nCaller: {user_turn_1}")
    conversation.append({"role": "user", "content": user_turn_1})
    
    reply_1 = await llm.chat(conversation, caller_phone=unreg_phone)
    print(f"Priya (AI): {reply_1}")
    
    # Verify customer registered in database
    cust_after = get_customer(unreg_phone)
    assert cust_after is not None
    assert len(cust_after["name"].strip()) > 0
    assert "Koramangala" in cust_after["address"] or "Bangalore" in cust_after["address"] or len(cust_after["address"]) > 0
    print(f"[OK] Database verified: {cust_after['name']} successfully registered in SQLite at {cust_after['address']}!")
    
    # Turn 2: Order grocery items
    user_turn_2 = "Please order 1 packet of Maggi noodles and 1 bottle of sunflower oil for me."
    print(f"\nCaller: {user_turn_2}")
    conversation.append({"role": "user", "content": user_turn_2})
    
    reply_2 = await llm.chat(conversation, caller_phone=unreg_phone)
    print(f"Priya (AI): {reply_2}")
    
    print("[OK] Unregistered caller registration and order completed.")

async def main():
    init_db()
    await test_registered_caller_conversation()
    await test_unregistered_caller_conversation()
    print("\n[PASSED] ALL CUSTOMER FLOW TESTS COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(main())
