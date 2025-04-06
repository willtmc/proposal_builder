from pathlib import Path
from PyPDF2 import PdfReader
from src import ocr_service

MIN_TEXT_LENGTH_THRESHOLD = 50 # Minimum characters to consider direct extraction successful

def extract_text_from_pdf(pdf_path: Path):
    """Extract text from PDF using direct extraction first, then OCR if needed."""
    text = None
    direct_extraction_attempted = False
    direct_extraction_successful = False

    # 1. Try direct text extraction first
    try:
        print(f"Attempting direct text extraction from PDF: {pdf_path.name}")
        with open(pdf_path, 'rb') as file:
            reader = PdfReader(file)
            extracted_parts = []
            total_pages = len(reader.pages)
            print(f"PDF has {total_pages} pages")
            
            for i, page in enumerate(reader.pages):
                print(f"Directly extracting text from page {i+1}/{total_pages}...")
                page_text = page.extract_text() or ""
                extracted_parts.append(page_text)
                if page_text.strip():
                    preview = page_text.strip().replace("\n", " ")[:100]
                    print(f"  Preview of direct text (Page {i+1}): {preview}...")
                else:
                    print(f"  No text directly extracted from page {i+1}")
            
            text = "\n\n".join(extracted_parts)
            direct_extraction_attempted = True

            # Check if the extracted text is substantial enough
            if text and len(text.strip()) > MIN_TEXT_LENGTH_THRESHOLD:
                print(f"Successfully extracted substantial text directly from {pdf_path.name}")
                direct_extraction_successful = True
                return text # Return the directly extracted text
            else:
                 print(f"Direct text extraction from {pdf_path.name} yielded minimal or no results.")
                 text = None # Reset text if not successful
                 
    except Exception as e:
        print(f"Error during direct PDF text extraction for {pdf_path.name}: {str(e)}")
        if "Password required" in str(e):
             print(f"  Suggestion: {pdf_path.name} seems to be password-protected.")
             # Don't attempt OCR on password-protected files unless handled
             return None 
        # If other error occurred during direct extraction, we might still try OCR
        print("Will attempt OCR as fallback.")
        direct_extraction_attempted = True # Mark as attempted even if failed

    # 2. If direct extraction failed or yielded minimal text, attempt OCR
    if not direct_extraction_successful:
        print(f"Falling back to OCR for {pdf_path.name}...")
        try:
            # Call the dedicated OCR service function
            text = ocr_service.extract_text_from_pdf_pages(pdf_path)
            if text:
                return text # Return OCR text if successful
            else:
                print(f"OCR also failed to extract text from {pdf_path.name}")
                return None # Return None if OCR also fails
        except Exception as ocr_e:
            # Errors within ocr_service should be logged there, but catch any unexpected ones here
            print(f"An unexpected error occurred during OCR fallback for {pdf_path.name}: {ocr_e}")
            return None
            
    # Should not be reachable if logic is correct, but as a safeguard:
    return text # Returns None if neither method worked 