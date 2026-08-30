import asyncio
from src.services.llm_service import LLMService
from src.database.db import init_db

async def main():
    print("Initializing Database...")
    init_db()
    
    print("\nConnecting to Local Ollama LLM...")
    llm = LLMService()
    conversation = llm.create_initial_conversation()
    
    # Test Scenario: Customer checks for milk and buys 2 packets
    user_inputs = [
        "Hi, do you have Amul Milk in stock?",
        "Yes, I want to order 2 packets of Amul Milk. My name is Alex, phone is 9876543210, and deliver it to 101 Park Street."
    ]
    
    for user_text in user_inputs:
        print(f"\nCaller: {user_text}")
        conversation.append({"role": "user", "content": user_text})
        
        reply = await llm.chat(conversation)
        print(f"Priya (AI): {reply}")

if __name__ == "__main__":
    asyncio.run(main())
