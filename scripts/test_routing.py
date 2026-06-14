import asyncio
import sys
import os

# Ensure the root folder is in the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.providers import parse_model_string
from providers.router import MultiProviderRouter

async def main():
    model = sys.argv[1] if len(sys.argv) > 1 else "gemini/gemini-2.5-flash"
    prompt = sys.argv[2] if len(sys.argv) > 2 else "What is the capital of France?"
    
    print("====================================================")
    print("            Unlocked AI LLM Routing Test            ")
    print("====================================================")
    
    p, m = parse_model_string(model)
    print(f"[*] Input Model String:  {model}")
    print(f"[*] Resolved Provider:   {p}")
    print(f"[*] Resolved Model:      {m}")
    
    router = MultiProviderRouter()
    
    try:
        client = router._get_client(p)
        print(f"[+] Client Class:        {client.__class__.__name__}")
        print(f"[+] Status:              Configured & Ready")
    except ValueError as e:
        print(f"[-] Status:              Failed")
        print(f"[-] Reason:              {e}")
        print("\n[!] To enable this provider, add its corresponding API key to your .env file.")
    except Exception as e:
        print(f"[-] Unexpected Error:    {e}")

if __name__ == "__main__":
    asyncio.run(main())
