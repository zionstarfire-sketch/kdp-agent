import os
import re
import shutil
import datetime
import subprocess
import httpx

# ============================================================
# PROMPT ENHANCEMENT SUITE (DRISTICALLY IMPROVED PROMPT QUALITY)
# ============================================================

def enhance_cover_prompt(prompt: str, title: str = "", subtitle: str = "") -> str:
    """
    Constructs an award-winning, editorial travel field guide cover visual prompt.
    Avoids generic clichés; emphasizes medium-format optics, dramatic scale, and authentic textures.
    """
    clean_prompt = prompt.replace("\n", " ").strip()
    return (
        f"Prestigious travel field guide book cover visual for '{title}'. "
        f"Subject: {clean_prompt}. "
        "Style: Award-winning documentary travel and landscape photography, National Geographic Traveler cover aesthetic. "
        "Composition: Breathtaking wide shot, strong geometric leading lines, striking architectural or natural focal point, dramatic scale. "
        "Lighting: Golden hour morning light with rich warm atmospheric depth, realistic environmental shadows, crystal clear crisp clarity. "
        "Camera & Lens: Shot on medium format Hasselblad H6D-100c, 35mm wide prime lens, f/4 aperture, hyper-detailed surface textures (weathered stone, mist, textured woodwork, reflective cobblestones). "
        "Negative Constraints: Hyper-realistic documentary photograph, candid and authentic, absolutely NO CGI, NO 3D rendering, NO oversaturated digital illustration, NO plastic smoothing, NO stock photo clichés, NO text, NO book title typography, NO words, NO logos."
    )

def enhance_chapter_illustration_prompt(prompt: str, chapter_title: str = "") -> str:
    """
    Constructs an editorial travel photojournalism prompt for chapter openers.
    """
    clean_prompt = prompt.replace("\n", " ").strip()
    return (
        f"Editorial travel field photography for '{chapter_title}'. "
        f"Subject: {clean_prompt}. "
        "Style: Authentic documentary travel photojournalism, Conde Nast Traveler editorial style. "
        "Atmosphere: Natural daylight, authentic ambient atmospheric conditions, candid documentary angle, real-world travel perspective. "
        "Camera & Lens: Shot on 35mm prime lens, f/2.8, Leica SL2, natural depth of field, tactile environmental textures, realistic color grading. "
        "Negative Constraints: Authentic candid documentary photograph, NO CGI, NO digital painting, NO cartoon, NO 3D render, NO artificial AI glow, NO text, NO watermarks."
    )

def enhance_evidence_prompt(prompt: str, category: str = "general") -> str:
    """
    Constructs a photographic evidence prompt verifying practical travel elements:
    entrances, signs, ticket machines, queues, menus, street layouts, bathrooms, transit, food portions, storefronts.
    """
    clean_prompt = prompt.replace("\n", " ").strip()
    category_guidance = {
        "ticket machines": "Close-up practical documentary shot of automated transit ticket vending machines, touchscreens, bill/coin slots, and bilingual instructions in practical transit lighting.",
        "entrances signs": "Eye-level candid photograph of actual entrance doorway, exterior signage, wayfinding boards, and facade architecture under natural daytime light.",
        "queues menus": "Candid eye-level documentary shot of waiting line or chalkboard/printed physical menu board with clearly visible pricing, dish names, and counter layout.",
        "street layouts": "Authentic streetscape perspective showing cobblestone intersection, pedestrian crosswalks, alleyway geometry, and neighborhood wayfinding signs.",
        "bathrooms": "Clean, practical documentary view of public restroom signage, accessibility features, or station facilities under realistic interior lighting.",
        "transportation infrastructure": "Documentary station platform, train boarding gate, bus shelter, or transit turnstile showing real-world operational hardware and signage.",
        "food portions": "Overhead or 45-degree angle table shot of authentic freshly served food portions on traditional dinnerware, natural cafe/bistro light, real textures.",
        "storefronts landmarks": "Unstaged street view of authentic local shop facade, awning, entrance window, and physical neighborhood context."
    }.get(category.lower().strip(), "Practical documentary field photojournalism, eye-level candid traveler view.")

    return (
        f"Photographic verification evidence: {clean_prompt}. "
        f"Verification Context: {category_guidance} "
        "Style: Authentic candid documentary field photograph, Magnum Photos / National Geographic field reporting style. "
        "Camera & Lens: Shot on Fujifilm GFX 100S, 35mm prime lens, f/3.2, unposed eye-level perspective, tactile real-world textures (brushed stainless steel, worn stone, wood grain, authentic paper). "
        "Lighting: Natural practical daylight or authentic ambient interior lighting, realistic shadow falloff, no studio fill. "
        "Negative Constraints: Hyper-realistic documentary evidence, candid realism, NO CGI, NO 3D rendering, NO digital illustration, NO plastic AI skin, NO surreal fantasy glow, NO stock photography clichés, NO watermarks, NO overlaid text."
    )

# ============================================================
# PUBLIC PHOTOGRAPHIC EVIDENCE DISCOVERY (WIKIMEDIA COMMONS)
# ============================================================

def search_public_photo(query: str, filename: str, output_dir: str = "output/images") -> dict:
    """
    Searches Wikimedia Commons for authentic, publicly available field photographs
    verifying travel infrastructure (ticket machines, entrance signs, transit, street layouts, landmarks).
    Records true source, date, and license. Never claims the photo is the author's own.
    """
    url = "https://commons.wikimedia.org/w/api.php"
    search_params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": "6",
        "gsrlimit": "5",
        "prop": "imageinfo",
        "iiprop": "url|size|extmetadata",
        "format": "json"
    }
    headers = {"User-Agent": "TravelGuideEvidenceBot/1.0 (bot@ebookguide.org; educational field research)"}
    
    try:
        r = httpx.get(url, params=search_params, headers=headers, timeout=12)
        if r.status_code != 200:
            return {"found": False}
        
        pages = r.json().get("query", {}).get("pages", {})
        for pid, page in pages.items():
            imageinfo = page.get("imageinfo", [])
            if not imageinfo:
                continue
            info = imageinfo[0]
            img_url = info.get("url", "")
            url_clean = img_url.split("?")[0].lower()
            if not url_clean.endswith((".jpg", ".jpeg", ".png")):
                continue
            
            os.makedirs(output_dir, exist_ok=True)
            if not filename.endswith((".png", ".jpg", ".jpeg")):
                ext = os.path.splitext(url_clean)[1] or ".jpg"
                filename = filename + ext
            filepath = os.path.join(output_dir, filename)
            
            # Download image bytes
            img_resp = httpx.get(img_url, headers=headers, timeout=20, follow_redirects=True)
            if img_resp.status_code == 200 and len(img_resp.content) > 2000:
                with open(filepath, "wb") as f:
                    f.write(img_resp.content)
                
                meta = info.get("extmetadata", {})
                raw_date = meta.get("DateTimeOriginal", {}).get("value") or meta.get("DateTime", {}).get("value") or "Undated"
                clean_date = re.sub(r"<[^>]+>", "", str(raw_date)).strip()[:10]
                raw_artist = meta.get("Artist", {}).get("value") or "Wikimedia Commons"
                clean_artist = re.sub(r"<[^>]+>", "", str(raw_artist)).strip()
                if len(clean_artist) > 35:
                    clean_artist = clean_artist[:35] + "..."
                clean_title = page.get("title", "").replace("File:", "").replace(".jpg", "").replace(".png", "").replace("_", " ").strip()
                license_name = meta.get("LicenseShortName", {}).get("value") or "Public Record"
                
                print(f"[PhotoEvidence] Found verified public photo for '{query}': {clean_title} ({clean_date})")
                return {
                    "found": True,
                    "title": clean_title,
                    "source": f"Wikimedia Commons / {clean_artist}",
                    "date": clean_date,
                    "license": license_name,
                    "filepath": filepath,
                    "filename": filename,
                    "attribution": f"Source: Wikimedia Commons ({clean_artist}), Date: {clean_date} | License: {license_name} | Public Record"
                }
    except Exception as e:
        print(f"[PhotoEvidence Warning] Public photo search for '{query}' failed ({e}).")
        
    return {"found": False}

# ============================================================
# PHOTOGRAPHIC EVIDENCE COORDINATOR
# ============================================================

def acquire_photographic_evidence(
    query: str,
    fallback_scene: str,
    filename: str,
    output_dir: str = None,
    category: str = "general"
) -> tuple[str, str]:
    """
    Acquires photographic evidence for a practical verification subject:
    1. First attempts to discover a real public domain / CC photograph (Wikimedia Commons).
    2. If no public photo exists, generates a hyper-realistic photographic evidence visual via Antigravity CLI.
    3. Truthfully records provenance and date. NEVER claims author ownership.

    Returns:
        tuple of (saved_filename, attribution_caption_string)
    """
    target_dir = output_dir if output_dir else os.path.join("output", "images")
    os.makedirs(target_dir, exist_ok=True)
    
    # 1. Try public photo search
    if query and len(query.strip()) > 3:
        public_res = search_public_photo(query, filename, target_dir)
        if public_res.get("found"):
            return public_res["filename"], public_res["attribution"]
    
    # 2. Fallback: Generate drastically improved documentary photo visual
    scene_text = fallback_scene if fallback_scene else query
    enhanced_prompt = enhance_evidence_prompt(scene_text, category)
    gen_result = generate_image_tool(enhanced_prompt, filename, target_dir)
    
    current_date = datetime.datetime.now().strftime("%B %Y")
    attribution = f"Source: Field Visual Reconstruction (AI), Date: {current_date} | Photographic Evidence Simulation"
    
    return filename, attribution

# ============================================================
# CORE AI IMAGE GENERATION ENGINE (ANTIGRAVITY CLI PRIORITY 1)
# ============================================================

def generate_image_tool(prompt: str, filename: str, output_dir: str = None) -> str:
    """
    Generate an illustration or book cover using AI and save it to disk.
    
    This function dynamically prioritizes:
    1. Google Antigravity CLI binary (Keyless & High Quality via local CLI auth)
    2. Hugging Face Serverless Inference API (stabilityai/stable-diffusion-3-medium-diffusers) as fallback.
    3. Pollinations.ai (Keyless fallback).

    Args:
        prompt: A descriptive prompt for the image.
        filename: The name of the file to save the image (e.g., 'cover.png').
        output_dir: Target directory to save the image. Defaults to 'output/images'.

    Returns:
        A message indicating where the image was saved, and which provider was used.
    """
    # Setup directory
    target_dir = output_dir if output_dir else os.path.join("output", "images")
    os.makedirs(target_dir, exist_ok=True)
    filename = os.path.basename(filename)
    if not filename.endswith(('.png', '.jpg', '.jpeg')):
        filename += '.png'
    filepath = os.path.join(target_dir, filename)
    abs_filepath = os.path.abspath(filepath)

    # 1. Try Google Antigravity CLI binary (Priority 1)
    agy_bin = shutil.which("agy.exe") or shutil.which("agy") or r"C:\Users\USER\AppData\Local\agy\bin\agy.exe"
    norm_filepath = abs_filepath.replace("\\", "/")
    if agy_bin and os.path.exists(agy_bin):
        try:
            print(f"[ImageGen] Generating via Antigravity CLI (Priority 1): '{prompt[:60]}...'")
            clean_prompt = prompt.replace('"', "'").replace("\n", " ").strip()
            agy_cmd = [
                agy_bin,
                "--dangerously-skip-permissions",
                "-p",
                f"Use generate_image to create an image for: {clean_prompt}. Save or copy the resulting image file to '{norm_filepath}'."
            ]
            result = subprocess.run(agy_cmd, capture_output=True, text=True, timeout=120.0)
            if os.path.exists(abs_filepath) and os.path.getsize(abs_filepath) > 1000:
                return f"Image successfully generated via Antigravity CLI and saved to: {filepath}"
            else:
                print(f"[ImageGen Warning] Antigravity CLI completed without saving valid image. Falling back to Hugging Face...")
        except subprocess.TimeoutExpired:
            print("[ImageGen Warning] Antigravity CLI timed out after 120s. Falling back to Hugging Face...")
        except Exception as e:
            print(f"[ImageGen Warning] Antigravity CLI failed ({e}). Falling back to Hugging Face...")

    # 2. Try Hugging Face Serverless Inference API (SD3 Medium) as fallback
    hf_token = os.getenv("HF_TOKEN")
    if hf_token:
        try:
            url = "https://router.huggingface.co/hf-inference/models/stabilityai/stable-diffusion-3-medium-diffusers"
            headers = {"Authorization": f"Bearer {hf_token}"}
            payload = {"inputs": prompt}
            
            print(f"[ImageGen] Generating via Hugging Face (SD3 Medium): '{prompt[:60]}...'")
            response = httpx.post(url, headers=headers, json=payload, timeout=45.0)
            if response.status_code == 503:
                # Model loading, wait and retry once
                import time
                print("[ImageGen] Hugging Face model loading (503), waiting 12s...")
                time.sleep(12)
                response = httpx.post(url, headers=headers, json=payload, timeout=45.0)
                
            if response.status_code == 200 and len(response.content) > 1000:
                with open(filepath, "wb") as f:
                    f.write(response.content)
                return f"Image successfully generated via Hugging Face (SD3) and saved to: {filepath}"
            else:
                print(f"[ImageGen Warning] Hugging Face returned status {response.status_code}. Falling back to Pollinations.ai...")
        except Exception as e:
            print(f"[ImageGen Warning] Hugging Face failed ({e}). Falling back to Pollinations.ai...")

    # 3. Resilient Keyless Fallback: Pollinations.ai
    try:
        import urllib.parse
        import random
        clean_prompt = prompt.replace("\n", " ").strip()
        encoded = urllib.parse.quote(clean_prompt)
        seed = random.randint(1000, 999999)
        url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=768&nologo=true&seed={seed}"
        print(f"[ImageGen] Generating via Pollinations.ai: '{prompt[:60]}...'")
        response = httpx.get(url, timeout=30.0, follow_redirects=True)
        if response.status_code == 200 and len(response.content) > 1000:
            with open(filepath, "wb") as f:
                f.write(response.content)
            return f"Image successfully generated via Pollinations.ai and saved to: {filepath}"
        else:
            return f"Pollinations returned status {response.status_code}."
    except Exception as e:
        return f"All image generation methods failed. Last error: {str(e)}"
