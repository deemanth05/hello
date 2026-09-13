import sys
import asyncio
import time
import ollama

sys.stdout.reconfigure(encoding='utf-8')

async def main():
    client = ollama.AsyncClient()
    short_prompt = (
        "You are Priya, AI phone assistant for DMart Express. Speak natural Kannada.\n"
        "Customer: Deemanth, Registered Address: Krishna Nagar, Bengaluru.\n"
        "Never ask for address or phone number.\n"
        "Tools:\n"
        "- search_catalog: {\"tool\": \"search_catalog\", \"arguments\": {\"query\": \"...\"}}\n"
        "- place_order: {\"tool\": \"place_order\", \"arguments\": {\"items\": [{\"name\": \"...\", \"quantity\": 1}], \"delivery_type\": \"delivery\"}}\n"
        "Output tool call as JSON. After tool result, reply politely in 1 short Kannada sentence. No asterisks or markdown."
    )
    t0 = time.time()
    res = await client.chat(
        model='gemma3:latest',
        messages=[
            {'role':'system', 'content': short_prompt},
            {'role':'user', 'content':'ನನಗೆ 2 ಪ್ಯಾಕೆಟ್ ಹಾಲು ಬೇಕು'}
        ],
        options={'num_predict': 50, 'temperature': 0.1}
    )
    t1 = time.time()
    print("Gemma3 message:\n", res['message']['content'])
    print("Total wall time (s):", t1 - t0)
    print("Prompt eval duration (s):", res.get('prompt_eval_duration', 0) / 1e9)
    print("Eval duration (s):", res.get('eval_duration', 0) / 1e9)

if __name__ == "__main__":
    asyncio.run(main())
