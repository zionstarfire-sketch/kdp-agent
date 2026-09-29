import os

def save_document(filename: str, content: str, output_dir: str = "output") -> str:
    """
    Save text content (e.g., chapters, outlines, briefs) to a file in the output directory.

    Args:
        filename: The filename (e.g., 'outline.md' or 'chapter1.md').
        content: The text content to write.
        output_dir: The directory to save into (defaults to 'output').

    Returns:
        A message confirming where the file was saved.
    """
    try:
        os.makedirs(output_dir, exist_ok=True)
        # Clean filename to prevent writing outside output
        filename = os.path.basename(filename)
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
            
        return f"File successfully saved to: {filepath}"
    except Exception as e:
        return f"Failed to save file: {str(e)}"

def upload_to_google_docs(title: str, content_html: str = "", content_md: str = "") -> dict:
    """
    Uploads the generated guide to Google Docs via Google Apps Script Webhook.
    Returns a dict with 'success' and 'url' or 'error'.
    """
    import httpx
    webhook_url = os.getenv("GOOGLE_DOCS_WEBHOOK_URL")
    if not webhook_url or "script.google.com" not in webhook_url:
        return {"success": False, "url": None, "reason": "GOOGLE_DOCS_WEBHOOK_URL not configured in .env"}

    try:
        payload = {
            "title": title,
            "html": content_html,
            "markdown": content_md,
        }
        print(f"[GoogleDocs] Uploading '{title}' to Google Docs via webhook...")
        resp = httpx.post(webhook_url, json=payload, timeout=60.0, follow_redirects=True)
        if resp.status_code == 200:
            try:
                data = resp.json()
                doc_url = data.get("url")
                if doc_url:
                    print(f"[GoogleDocs] Successfully created Google Doc: {doc_url}")
                    return {"success": True, "url": doc_url}
            except Exception:
                pass
            return {"success": True, "url": resp.text.strip()}
        else:
            return {"success": False, "url": None, "reason": f"HTTP {resp.status_code}"}
    except Exception as e:
        print(f"[GoogleDocs Warning] Failed to upload to Google Docs: {e}")
        return {"success": False, "url": None, "reason": str(e)}
