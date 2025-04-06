from pathlib import Path
import sys
# Add src to sys.path to allow importing modules from src
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src import ocr_service

def read_full_pdf_ocr(pdf_filename):
    pdf_path = Path(".") / pdf_filename
        
    if not pdf_path.is_file():
        print(f"Error: Input PDF not found: {pdf_path}")
        return None
        
    print(f"Reading full {pdf_filename} using OCR...")
    try:
        extracted_text = ocr_service.extract_text_from_pdf_pages(pdf_path)
        if extracted_text:
            print(f"Successfully extracted text from {pdf_filename}")
            # Print the full text to the console for analysis
            print("\n--- FULL OCR TEXT START ---")
            print(extracted_text)
            print("--- FULL OCR TEXT END ---")
            return extracted_text # Return for potential future use
        else:
            print(f"Failed to extract text from {pdf_filename}.")
            return None
    except Exception as e:
        print(f"Error during OCR read of {pdf_filename}: {e}")
        return None

# Read Real Estate PDF fully
read_full_pdf_ocr("Real Estate Auction Proposal.pdf") 