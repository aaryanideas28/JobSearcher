import asyncio
import httpx
from config.settings import get_settings

async def main():
    settings = get_settings()
    api_key = settings.huggingface_api_key
    print("HF Key:", api_key)
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    hf_payload = {
        "inputs": "<|system|>\nYou are a helpful assistant.\n<|user|>\nHello\n<|assistant|>\n",
        "parameters": {
            "temperature": 0.2,
            "max_new_tokens": 1024,
        },
    }
    
    for model in ["Qwen/Qwen2.5-3B-Instruct", "Qwen/Qwen2.5-7B-Instruct"]:
        url = f"https://api-inference.huggingface.co/models/{model}"
        print(f"Testing model {model} at {url}...")
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(url, json=hf_payload, headers=headers)
                print("Status Code:", response.status_code)
                print("Response JSON:", response.text[:500])
        except Exception as e:
            print("Error:", e)

if __name__ == "__main__":
    asyncio.run(main())
