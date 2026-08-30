import json
from typing import List, Dict, Any, AsyncGenerator
import ollama
from loguru import logger
from src.config import settings
from src.tools.booking_tools import STORE_TOOLS, execute_tool_call

SYSTEM_PROMPT = f"""You are 'Priya', a friendly and efficient AI phone ordering assistant for {settings.STORE_NAME}.
Your job is to help customers place grocery orders, check item availability, and manage their orders over the phone.

PHONE CONVERSATION RULES:
1. Speak in concise, natural, spoken English (1 to 2 sentences per turn max).
2. NEVER use markdown, emojis, asterisks (*), hashtags (#), or bullet points because your response is converted directly to voice audio.
3. Pronounce numbers and currency naturally (e.g. say "two hundred and forty rupees" or "twenty rupees", not symbols).
4. Always check item stock or search the catalog using your tools when a customer asks about products. Never invent products or prices.
5. Before placing an order with `place_order`, ALWAYS confirm with the customer:
   - Their name and phone number
   - The list of items and quantities
   - Delivery or Pickup preference (and address if delivery)
6. Once an order is placed, clearly state their Order ID and total amount.
7. Keep your tone cheerful, helpful, and courteous.
"""

class LLMService:
    def __init__(self, model: str = None, host: str = None):
        self.model = model or settings.OLLAMA_MODEL
        self.client = ollama.AsyncClient(host=host or settings.OLLAMA_HOST)
        self.system_prompt = SYSTEM_PROMPT

    def create_initial_conversation(self) -> List[Dict[str, Any]]:
        """Initializes a conversation with the phone system prompt."""
        return [
            {"role": "system", "content": self.system_prompt}
        ]

    async def chat(self, messages: List[Dict[str, Any]]) -> str:
        """
        Sends message history to Ollama, resolves any tool calls automatically,
        and returns the final assistant voice reply.
        """
        response = await self.client.chat(
            model=self.model,
            messages=messages,
            tools=STORE_TOOLS
        )
        
        msg = response.get("message", {})
        
        # Check if Ollama wants to call a tool
        tool_calls = msg.get("tool_calls")
        if tool_calls:
            # 1. Append assistant's tool_call request to history
            messages.append(msg)
            
            # 2. Execute each tool call
            for tool in tool_calls:
                fn = tool.get("function", {})
                fn_name = fn.get("name")
                fn_args = fn.get("arguments", {})
                
                # In some versions of ollama, arguments might be a JSON string
                if isinstance(fn_args, str):
                    try:
                        fn_args = json.loads(fn_args)
                    except Exception:
                        pass
                
                tool_output = execute_tool_call(fn_name, fn_args)
                
                # 3. Append tool execution result back to conversation
                messages.append({
                    "role": "tool",
                    "content": tool_output
                })
            
            # 4. Re-query the model to get its spoken response with the tool results
            second_response = await self.client.chat(
                model=self.model,
                messages=messages
            )
            final_reply = second_response["message"]["content"]
            messages.append(second_response["message"])
            return final_reply
        else:
            # Normal conversational reply without tool call
            reply = msg.get("content", "")
            messages.append({"role": "assistant", "content": reply})
            return reply
