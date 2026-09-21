import os
import sys
import httpx
from dotenv import load_dotenv

# Reconfigure stdout/stderr to use UTF-8 to prevent encoding crashes on Windows consoles
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Load env variables from the root folder
load_dotenv(override=True)

# Output directory
os.makedirs("output", exist_ok=True)

PROMPT = "A professional, minimalist book cover illustration for a student productivity guide, flat vector design, high quality, soft pastel colors"

def test_huggingface(prompt: str, token: str) -> bool:
    """
    Test Hugging Face Serverless Inference API (Stable Diffusion 3 Medium).
    This is 100% free but requires a free Hugging Face API Token with "Inference Provider" permission.
    """
    print("\n--- Testing Hugging Face (SD3 Medium) ---")
    if not token:
        print("[-] Skipping: HF_TOKEN is not set in .env")
        print("    Get a free token here: https://huggingface.co/settings/tokens")
        return False
        
    url = "https://router.huggingface.co/hf-inference/models/stabilityai/stable-diffusion-3-medium-diffusers"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"inputs": prompt}
    
    try:
        print("[+] Sending request to Hugging Face...")
        response = httpx.post(url, headers=headers, json=payload, timeout=45.0)
        
        # Hugging Face sometimes needs to load the model first and returns a 503
        if response.status_code == 503:
            print("[!] Model is loading, waiting 15 seconds and retrying...")
            import time
            time.sleep(15)
            response = httpx.post(url, headers=headers, json=payload, timeout=45.0)
            
        response.raise_for_status()
        
        filepath = "output/test_hf.png"
        with open(filepath, "wb") as f:
            f.write(response.content)
            
        print(f"[+] SUCCESS! Image saved to: {filepath}")
        return True
    except Exception as e:
        print(f"[-] Failed Hugging Face: {str(e)}")
        if 'response' in locals() and response is not None:
            print(f"    Response Status: {response.status_code}")
            print(f"    Response Content: {response.text[:250]}")
            if response.status_code == 403 and "Inference Providers" in response.text:
                print("\n[TIP] To fix the 403 error on Hugging Face:")
                print("1. Go to https://huggingface.co/settings/tokens")
                print("2. Create or edit a Fine-grained token.")
                print("3. Check the 'Make calls to Inference Providers' permission under the Inference section.")
                print("4. Update your HF_TOKEN in your .env file.")
        return False

def main():
    hf_token = os.getenv("HF_TOKEN")
    
    print("====================================================")
    print("        IMAGE GENERATOR API TEST RUNNER             ")
    print("====================================================")
    print(f"Target Prompt: '{PROMPT}'")
    
    # Run test
    hf_success = test_huggingface(PROMPT, hf_token)
    
    print("\n=================== SUMMARY ========================")
    print(f"Hugging Face (Free SD3): {'SUCCESS' if hf_success else 'FAILED/SKIPPED'}")
    print("====================================================")

if __name__ == "__main__":
    main()
