from pathlib import Path

def extract_text_file(file_path: Path):
    """Reads text directly from a text-based file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
        print(f"Successfully read text file: {file_path.name}")
        return text
    except Exception as e:
        print(f"Error reading text file {file_path.name}: {e}")
        return None # Return None on error 