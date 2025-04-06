import pytesseract
from pdf2image import convert_from_path
from PIL import Image
from pathlib import Path

def extract_text_from_image(image_path: Path):
    """Perform OCR on an image file."""
    try:
        with Image.open(image_path) as img:
            text = pytesseract.image_to_string(img)
        print(f"Successfully extracted text from image: {image_path.name}")
        return text
    except pytesseract.TesseractNotFoundError:
        print("Error: Tesseract is not installed or not in your PATH. OCR will not function.")
        # Re-raise the error after logging it to stop execution if Tesseract is missing
        raise
    except Exception as e:
        print(f"Error performing OCR on image {image_path.name}: {e}")
        return None # Return None on other image processing errors

def extract_text_from_pdf_pages(pdf_path: Path):
    """Convert PDF pages to images and perform OCR on each page."""
    extracted_text = ""
    try:
        # Check if poppler is installed (pdf2image dependency)
        images = convert_from_path(str(pdf_path))
        print(f"Converted {pdf_path.name} to {len(images)} images for OCR.")
        for i, image in enumerate(images):
            print(f"Processing page {i+1}/{len(images)} with OCR...")
            try:
                # Use pytesseract to do OCR on the image
                page_text = pytesseract.image_to_string(image) or ""
                extracted_text += page_text + "\n\n" # Add newline between pages
                if page_text.strip():
                    preview = page_text.strip().replace("\n", " ")[:100]
                    print(f"  Preview of OCR text (Page {i+1}): {preview}...")
                else:
                    print(f"  No text detected on page {i+1}")
            except pytesseract.TesseractNotFoundError:
                print("Error: Tesseract is not installed or not in your PATH. OCR will not function.")
                raise # Stop execution if Tesseract is missing
            except Exception as page_e:
                print(f"  Error performing OCR on page {i+1} of {pdf_path.name}: {page_e}")
                # Continue to the next page even if one page fails
                extracted_text += f"[OCR Error on Page {i+1}]\n\n"
                
        if extracted_text.strip():
            print(f"Successfully extracted text using OCR from {pdf_path.name}")
            return extracted_text
        else:
            print(f"OCR processing completed, but no text was extracted from {pdf_path.name}")
            return None
            
    except ImportError:
         print("Error: pdf2image or its dependencies (like poppler) might not be installed correctly.")
         raise
    except Exception as e:
        print(f"Error converting PDF to images for {pdf_path.name}: {str(e)}")
        # Consider if pdf file might be corrupted or password protected
        if "PDFSyntaxError" in str(type(e).__name__):
             print(f"Suggestion: Check if {pdf_path.name} is a valid, non-corrupted PDF.")
        elif "Password required" in str(e):
             print(f"Suggestion: {pdf_path.name} seems to be password-protected.")
        return None # Return None if conversion fails 