import asyncio
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

import ollama
import json
import re
from src.tools.booking_tools import execute_tool_call

PROMPT = """You are 'Priya', AI phone ordering assistant for DMart Express in Karnataka.
You speak Kannada (ಕನ್ನಡ).

You have access to the following tools:
1. register_caller(customer_name: str, delivery_address: str)
2. search_catalog(query: str)
3. place_order(items: list of {name, quantity}, delivery_type: str)

If you need to perform an action (register, search, or place order), reply ONLY with a JSON object in this format:
```json
{
  "tool": "register_caller",
  "arguments": {
    "customer_name": "...",
    "delivery_address": "..."
  }
}
```
Otherwise, if no tool is needed or you are answering the user with the final response, speak in polite Kannada (ಕನ್ನಡ).
"""

async def main():
    client = ollama.AsyncClient()
    messages = [
        {"role": "system", "content": PROMPT},
        {"role": "user", "content": "ನನ್ನ ಹೆಸರು ರಮೇಶ್ ಕುಮಾರ್, ನನ್ನ ವಿಳಾಸ #12, 4ನೇ ಮುಖ್ಯರಸ್ತೆ, ಜಯನಗರ, ಬೆಂಗಳೂರು."}
    ]
    res = await client.chat(model="gemma3:latest", messages=messages)
    reply = res["message"]["content"]
    print("Gemma 3 Response:")
    print(reply)
    
    # Check if JSON tool call is in response
    match = re.search(r"```json\s*(\{.*?\})\s*```", reply, re.DOTALL) or re.search(r"(\{.*?\})", reply, re.DOTALL)
    if match:
        data = json.loads(match.group(1))
        tool_name = data.get("tool") or data.get("name")
        args = data.get("arguments", {})
        print(f"Detected Tool: {tool_name} with args {args}")
        out = execute_tool_call(tool_name, args, default_phone="+919888777666")
        print("Tool Result:", out)

if __name__ == "__main__":
    asyncio.run(main())
