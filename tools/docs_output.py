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
