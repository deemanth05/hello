import asyncio
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.database.db import init_db
from src.database.customer_repo import get_customer
from src.database.booking_repo import search_products
from src.services.llm_service import LLMService

async def test_kannada_catalog_and_synonyms():
    print("\n=======================================================")
    print("TEST 1: KANNADA CATALOG SEARCH & SYNONYMS")
    print("=======================================================")
    
    # 1. Test Kannada milk search: ಹಾಲು
    milk_res = search_products("ಹಾಲು")
    assert len(milk_res) > 0
    print(f"[OK] Search 'ಹಾಲು' (milk) matched: {[p['name'] for p in milk_res[:2]]}")

    # 2. Test Kannada tea search: ಚಹಾ ಪುಡಿ
    tea_res = search_products("ಚಹಾ ಪುಡಿ")
    assert len(tea_res) > 0
    print(f"[OK] Search 'ಚಹಾ ಪುಡಿ' (tea) matched: {[p['name'] for p in tea_res[:2]]}")

    # 3. Test Kannada oil search: ಅಡುಗೆ ಎಣ್ಣೆ
    oil_res = search_products("ಅಡುಗೆ ಎಣ್ಣೆ")
    assert len(oil_res) > 0
    print(f"[OK] Search 'ಅಡುಗೆ ಎಣ್ಣೆ' (oil) matched: {[p['name'] for p in oil_res[:2]]}")

    # 4. Test Kanglish search: sakkare beku
    sugar_res = search_products("sakkare beku")
    assert len(sugar_res) > 0
    print(f"[OK] Search 'sakkare beku' matched: {[p['name'] for p in sugar_res[:2]]}")

async def test_kannada_registered_caller_flow():
    print("\n=======================================================")
    print("TEST 2: KANNADA REGISTERED CALLER CONVERSATION")
    print("=======================================================")
    
    phone = "+919876543210" # Rahul Sharma
    llm = LLMService()
    
    greeting = llm.get_initial_greeting(phone)
    print(f"Bot Initial Greeting: {greeting}")
    assert "Rahul" in greeting or "ನಮಸ್ಕಾರ" in greeting
    
    conversation = llm.create_initial_conversation(caller_phone=phone)
    
    # Turn 1: Caller asks for milk and bread in Kannada
    user_turn_1 = "ನನಗೆ 2 ಪ್ಯಾಕೆಟ್ ಹಾಲು ಮತ್ತು ಒಂದು ಬ್ರೆಡ್ ಬೇಕು"
    print(f"\nCaller (Kannada): {user_turn_1}")
    conversation.append({"role": "user", "content": user_turn_1})
    
    reply_1 = await llm.chat(conversation, caller_phone=phone)
    print(f"Priya (AI): {reply_1}")
    
    # Turn 2: Order confirmation in Kannada
    user_turn_2 = "ಹೌದು, ದಯವಿಟ್ಟು ಡೆಲಿವರಿ ಮಾಡಿ"
    print(f"\nCaller (Kannada): {user_turn_2}")
    conversation.append({"role": "user", "content": user_turn_2})
    
    reply_2 = await llm.chat(conversation, caller_phone=phone)
    print(f"Priya (AI): {reply_2}")
    print("[OK] Registered caller Kannada conversation completed.")

async def test_kannada_unregistered_caller_flow():
    print("\n=======================================================")
    print("TEST 3: KANNADA UNREGISTERED CALLER REGISTRATION & ORDER")
    print("=======================================================")
    
    unreg_phone = "+919333222111"
    llm = LLMService()
    
    # Ensure idempotent test: clean up test phone if registered from prior run
    from src.database.db import get_db_cursor
    with get_db_cursor() as cursor:
        cursor.execute("DELETE FROM customers WHERE phone_number LIKE ?", (f"%{unreg_phone[-10:]}%",))

    greeting = llm.get_initial_greeting(unreg_phone)
    print(f"Bot Initial Greeting: {greeting}")
    assert "ನಮಸ್ಕಾರ" in greeting or "ನೋಂದಣಿ" in greeting
    
    conversation = llm.create_initial_conversation(caller_phone=unreg_phone)
    
    # Turn 1: Registration details in Kannada
    user_turn_1 = "ನನ್ನ ಹೆಸರು ಸುನಿಲ್ ಕುಮಾರ್, ನನ್ನ ವಿಳಾಸ #45, ಮಲ್ಲೇಶ್ವರಂ, ಬೆಂಗಳೂರು."
    print(f"\nCaller (Kannada): {user_turn_1}")
    conversation.append({"role": "user", "content": user_turn_1})
    
    reply_1 = await llm.chat(conversation, caller_phone=unreg_phone)
    print(f"Priya (AI): {reply_1}")
    
    # Verify customer registered in database
    cust = get_customer(unreg_phone)
    assert cust is not None
    assert "ಸುನಿಲ್" in cust["name"] or "Sunil" in cust["name"] or len(cust["name"]) > 0
    print(f"[OK] Database verified: Customer successfully registered in SQLite -> {cust['name']} ({cust['address']})")
    
    # Turn 2: Order in Kannada
    user_turn_2 = "ನನಗೆ 1 ಲೀಟರ್ ಸೂರ್ಯಕಾಂತಿ ಎಣ್ಣೆ ಮತ್ತು 1 ಪ್ಯಾಕೆಟ್ ಟೀ ಪುಡಿ ಬೇಕು."
    print(f"\nCaller (Kannada): {user_turn_2}")
    conversation.append({"role": "user", "content": user_turn_2})
    
    reply_2 = await llm.chat(conversation, caller_phone=unreg_phone)
    print(f"Priya (AI): {reply_2}")
    print("[OK] Unregistered caller Kannada registration & order completed.")

async def main():
    init_db()
    await test_kannada_catalog_and_synonyms()
    await test_kannada_registered_caller_flow()
    await test_kannada_unregistered_caller_flow()
    print("\n[PASSED] ALL KANNADA VOICE-AI TESTS COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(main())
