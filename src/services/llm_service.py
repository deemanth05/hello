import json
import re
import asyncio
from typing import List, Dict, Any, Optional
import ollama
from loguru import logger
from src.config import settings
from src.database.customer_repo import get_customer
from src.tools.booking_tools import STORE_TOOLS, execute_tool_call

def clean_speech_text(text: str) -> str:
    """
    Cleans LLM response text for natural TTS voice playback:
    Removes JSON blocks, markdown symbols (*, #, _, `, [ ]), emojis, and excessive whitespace.
    Preserves Kannada Unicode characters (U+0C80..U+0CFF) and English letters/numbers.
    """
    if not text:
        return ""
    # Strip any JSON markdown blocks
    text = re.sub(r"```(?:json)?\s*[\s\S]*?```", "", text)
    # Strip any complete JSON objects or lists
    text = re.sub(r"\{[\s\S]*?\}", "", text)
    text = re.sub(r"\[[\s\S]*?\]", "", text)
    # Strip stray JSON key-value remnants (e.g. "delivery_type": "delivery")
    text = re.sub(r"\"[a-zA-Z0-9_-]+\"\s*:\s*\"[^\"]*\"", "", text)
    text = re.sub(r"\"[a-zA-Z0-9_-]+\"\s*:\s*[\d.]+", "", text)
    # Strip curly braces, square brackets, quotes
    text = re.sub(r"[{}\[\]\"\']", "", text)
    # Remove markdown formatting
    cleaned = re.sub(r"[*#_`~]", "", text)
    # Remove emojis / symbols while keeping Kannada Unicode and ASCII
    cleaned = re.sub(r"[^\x00-\x7F\u0C80-\u0CFF]+", " ", cleaned)
    # Normalize commas, spaces, punctuation
    cleaned = re.sub(r"\s*,\s*,+", ", ", cleaned)
    cleaned = re.sub(r"^[,.\s\-_]+", "", cleaned)
    cleaned = re.sub(r"[,;\s\-_]+$", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned

TOOL_INSTRUCTIONS = """Tools:
- search_catalog: {"tool": "search_catalog", "arguments": {"query": "..."}}
- check_stock: {"tool": "check_stock", "arguments": {"product_name": "...", "quantity": 1}}
- place_order: {"tool": "place_order", "arguments": {"items": [{"name": "...", "quantity": 1}], "delivery_type": "delivery"}}
- register_caller: {"tool": "register_caller", "arguments": {"customer_name": "...", "delivery_address": "..."}}
To call a tool, output only a JSON block: {"tool": "...", "arguments": {...}}. After receiving the tool result, reply in 1-2 short, polite sentences in Kannada (ಕನ್ನಡ)."""

def build_system_prompt(caller_phone: str, language: str = "kn") -> str:
    cust = get_customer(caller_phone)
    store_name = settings.STORE_NAME
    
    if cust:
        return f"""You are Priya, AI phone assistant for {store_name}. Speak natural spoken Kannada.
Customer: {cust['name']}, Phone: {cust['phone_number']}, Address: {cust['address']}.
RULES:
1. Registered customer. Never ask for address or phone number.
2. When customer asks for grocery items in Kannada/English, call search_catalog.
3. When confirmed, call place_order. Summarize items, total rupees, and 35-45 mins delivery to {cust['address']}.
4. Keep spoken replies short (1-2 sentences). Never use asterisks, bullet points, or markdown.

{TOOL_INSTRUCTIONS}"""
    else:
        return f"""You are Priya, AI phone assistant for {store_name}. Speak natural spoken Kannada.
Caller: {caller_phone} (Not registered).
RULES:
1. When caller provides name and address, call register_caller immediately.
2. Then ask what groceries they need, use search_catalog and place_order.
3. Keep spoken replies short (1-2 sentences). No markdown or asterisks.

{TOOL_INSTRUCTIONS}"""

class LLMService:
    def __init__(self, model: str = None, host: str = None):
        self.model = model or settings.OLLAMA_MODEL
        self.client = ollama.AsyncClient(host=host or settings.OLLAMA_HOST)
        self.supports_native_tools = "qwen" in self.model.lower() or "llama3" in self.model.lower()

    def create_initial_conversation(self, caller_phone: str = "+919876543210") -> List[Dict[str, Any]]:
        """Initializes a conversation with the caller-specific system prompt."""
        system_prompt = build_system_prompt(caller_phone, language=settings.LANGUAGE)
        return [
            {"role": "system", "content": system_prompt}
        ]

    def get_initial_greeting(self, caller_phone: str = "+919876543210") -> str:
        """Returns the immediate welcome greeting in Kannada."""
        cust = get_customer(caller_phone)
        if cust:
            return f"ನಮಸ್ಕಾರ {cust['name']}, {settings.STORE_NAME} ಗೆ ಸ್ವಾಗತ! ನಿಮಗೆ ಇಂದು ಯಾವ ದಿನಸಿ ಸಾಮಗ್ರಿಗಳು ಬೇಕು?"
        else:
            return f"ನಮಸ್ಕಾರ! {settings.STORE_NAME} ಗೆ ಸ್ವಾಗತ. ನಿಮ್ಮ ಮೊಬೈಲ್ ನಂಬರ್ ನೋಂದಣಿ ಆಗಿಲ್ಲ, ದಯವಿಟ್ಟು ನಿಮ್ಮ ಹೆಸರು ಮತ್ತು ವಿಳಾಸ ತಿಳಿಸುತ್ತೀರಾ?"

    def _extract_json_tool_call(self, text: str) -> Optional[Dict[str, Any]]:
        """Extracts JSON tool calls formatted in Markdown codeblocks or raw JSON."""
        # 1. Match ```json { ... } ```
        block_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
        if block_match:
            try:
                data = json.loads(block_match.group(1))
                if "tool" in data or "name" in data:
                    return data
            except Exception:
                pass
        
        # 2. Match raw JSON object with "tool" or "name" key
        json_matches = re.findall(r"(\{(?:[^{}]|(?:\{[^{}]*\}))*\})", text, re.DOTALL)
        for m in json_matches:
            try:
                data = json.loads(m)
                if ("tool" in data or "name" in data) and ("arguments" in data or "parameters" in data or "query" in data):
                    return data
            except Exception:
                pass
                
        return None

    async def chat(self, messages: List[Dict[str, Any]], caller_phone: Optional[str] = None) -> str:
        """
        Sends message history to local Ollama (supports gemma3 and qwen2.5), 
        executes tool calls seamlessly, and returns clean spoken Kannada text.
        """
        max_iterations = 3
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            response = None
            last_err = None
            for attempt in range(2):
                try:
                    chat_kwargs = {
                        "model": self.model,
                        "messages": messages,
                        "options": {"num_predict": 75, "temperature": 0.1}
                    }
                    if self.supports_native_tools:
                        chat_kwargs["tools"] = STORE_TOOLS
                    
                    response = await self.client.chat(**chat_kwargs)
                    break
                except Exception as e:
                    last_err = e
                    if "does not support tools" in str(e) or "400" in str(e):
                        self.supports_native_tools = False
                        continue
                except Exception as e:
                    last_err = e
                    if "Failed to connect" in str(e) or "connection" in str(e).lower():
                        logger.warning(f"Ollama connection attempt {attempt+1} failed, retrying in 1.5s...")
                        await asyncio.sleep(1.5)
                    else:
                        break

            if response is None:
                logger.error(f"Error calling local Ollama model {self.model}: {last_err}")
                return "ಕ್ಷಮಿಸಿ, ಸಂಪರ್ಕದಲ್ಲಿ ಸಣ್ಣ ಸಮಸ್ಯೆಯಾಗಿದೆ. ದಯವಿಟ್ಟು ಇನ್ನೊಮ್ಮೆ ಹೇಳುತ್ತೀರಾ?"

            msg = response.get("message", {})
            content = msg.get("content", "")
            tool_calls = msg.get("tool_calls")
            
            # Step 2: Check for Native Tool Calls
            if tool_calls:
                messages.append(msg)
                for tool in tool_calls:
                    fn = tool.get("function", {})
                    fn_name = fn.get("name")
                    fn_args = fn.get("arguments", {})
                    if isinstance(fn_args, str):
                        try:
                            fn_args = json.loads(fn_args)
                        except Exception:
                            pass
                    tool_output = execute_tool_call(fn_name, fn_args, default_phone=caller_phone)
                    messages.append({
                        "role": "tool",
                        "content": tool_output
                    })
                continue

            # Step 3: Check for Prompt-based JSON Tool Calls (for gemma3:latest)
            json_tool = self._extract_json_tool_call(content)
            if json_tool:
                tool_name = json_tool.get("tool") or json_tool.get("name")
                tool_args = json_tool.get("arguments") or json_tool.get("parameters") or {}
                
                messages.append({"role": "assistant", "content": content})
                tool_output = execute_tool_call(tool_name, tool_args, default_phone=caller_phone)
                
                messages.append({
                    "role": "user",
                    "content": f"[TOOL RESULT for {tool_name}]: {tool_output}\nNow respond politely to the caller in Kannada (ಕನ್ನಡ)."
                })
                continue
                
            # Step 4: Final Spoken Reply
            messages.append({"role": "assistant", "content": content})
            cleaned = clean_speech_text(content)
            return cleaned or "ಹೌದು, ನಾನು ನಿಮಗೆ ಇನ್ನೇನು ಸಹಾಯ ಮಾಡಬಹುದು?"

        return "ನಿಮ್ಮ ಆರ್ಡರ್ ಪ್ರಕ್ರಿಯೆಗೊಳಿಸಲಾಗಿದೆ. ಧನ್ಯವಾದಗಳು!"
