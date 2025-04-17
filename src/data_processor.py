#!/usr/bin/env python3
import os
import mimetypes
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import json

from src import pdf_handler, ocr_service, file_utils
from src.crs_parser import extract_variables_from_document  

# Add more image types if needed
SUPPORTED_IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif"]
# Add more text types if needed
SUPPORTED_TEXT_EXTENSIONS = [".txt", ".md", ".py", ".csv", ".json", ".html", ".xml"]

def process_folder(folder_path: Path) -> Tuple[str, List[Dict[str, str]], List[Path]]:
    """
    Processes all supported files in a given folder, extracts text from text/PDF,
    collects image paths, and returns consolidated text, an error summary, and image paths.

    Args:
        folder_path: The Path object representing the folder to process.

    Returns:
        A tuple containing:
            - consolidated_text (str): All extracted text joined together.
            - error_summary (List[Dict[str, str]]): Errors encountered during processing.
            - image_paths (List[Path]): List of paths to supported image files found.
    """
    consolidated_texts = []
    error_summary = []
    image_paths = [] # Initialize list for image paths

    print(f"\nProcessing files in folder: {folder_path}")

    for item in folder_path.iterdir():
        # --- Skip output/previously generated files ---
        if item.name.startswith("generated_proposal") or item.name.endswith("_output.md") or item.name.endswith("_proposal.md"):
            print(f"Skipping previously generated output file: {item.name}")
            continue
        if item.is_file():
            print(f"\n--- Processing File: {item.name} ---")
            file_path = item.absolute()
            extracted_text: Optional[str] = None
            error_info: Optional[str] = None
            processed_as_image = False # Flag to track if we handled it as an image

            try:
                # CRS PDF SPECIAL HANDLING
                if item.name.lower().startswith("crs property report") and item.suffix.lower() == ".pdf":
                    print("Detected CRS Property Report PDF. Using CRS-specific parser.")
                    raw_text = pdf_handler.extract_text_from_pdf(file_path)
                    if raw_text:
                        crs_fields = extract_variables_from_document(raw_text)
                        extracted_text = json.dumps(crs_fields, indent=2) if crs_fields else ""
                        print("CRS extracted fields:")
                        print(extracted_text)
                    else:
                        error_info = "Failed to extract text from CRS PDF."
                else:
                    # Basic checks
                    if not os.access(file_path, os.R_OK):
                        error_info = "File is not readable (permissions?)."
                        print(f"Warning: {error_info}")
                    elif not file_path.stat().st_size > 0:
                        # Allow empty files, but log warning. Don't skip image files.
                        if item.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
                            error_info = "File is empty (0 bytes)."
                            print(f"Warning: {error_info}")
                        else:
                            # Images can be 0 bytes temporarily during sync etc., still collect path
                            print(f"Notice: Image file {item.name} has 0 bytes, collecting path anyway.")

                    # Only proceed if no critical error yet (readable, or 0-byte image)
                    if error_info != "File is not readable (permissions?).":
                        # Determine file type and process
                        file_ext = item.suffix.lower()
                        mime_type, _ = mimetypes.guess_type(file_path)
                        mime_type = mime_type or "" # Ensure mime_type is a string

                        print(f"Detected extension: {file_ext}, MIME type: {mime_type}")

                        if file_ext == '.pdf' or "pdf" in mime_type:
                            extracted_text = pdf_handler.extract_text_from_pdf(file_path)
                        elif file_ext in SUPPORTED_IMAGE_EXTENSIONS or mime_type.startswith("image"):
                            # Instead of OCR, collect the image path
                            print(f"Collecting image file for analysis: {item.name}")
                            image_paths.append(file_path)
                            processed_as_image = True # Mark that we handled this as an image
                        elif file_ext in SUPPORTED_TEXT_EXTENSIONS or mime_type.startswith("text"):
                            extracted_text = file_utils.extract_text_file(file_path)
                        elif error_info is None: # Only mark unsupported if no prior error
                            error_info = f"Unsupported file type (ext: {file_ext}, mime: {mime_type}). Skipped."
                            print(f"Notice: {error_info}")

                # Consolidate results
                if extracted_text:
                    print(f"Successfully processed and extracted text from {item.name}")
                    consolidated_texts.append(extracted_text)
                elif error_info:
                    error_summary.append({"file": item.name, "error": error_info})
                # Handle case where text extraction failed (returned None) but wasn't an 'error_info' case
                # And ensure it wasn't processed as an image (where None is expected)
                elif not processed_as_image and (file_ext == '.pdf' or file_ext in SUPPORTED_TEXT_EXTENSIONS):
                    error_info = "Text extraction failed (check logs for details)."
                    print(f"Warning: {item.name} - {error_info}")
                    error_summary.append({"file": item.name, "error": error_info})

            except Exception as e:
                # Catch unexpected errors during processing attempt
                print(f"!!! Unexpected Error processing {item.name}: {str(e)} !!!")
                import traceback
                traceback.print_exc() # Print traceback for debugging
                error_summary.append({"file": item.name, "error": f"Unexpected error: {str(e)}"})
                continue # Move to the next file
            finally:
                 print(f"--- Finished Processing File: {item.name} ---")

    # Join all successfully extracted texts
    all_extracted_text = "\n\n==== End of Document ====\n\n".join(consolidated_texts)
    
    print(f"\nFinished processing folder. Processed {len(list(folder_path.iterdir()))} items.")
    print(f"Successfully extracted text from {len(consolidated_texts)} files.")
    if error_summary:
        print(f"Encountered errors in {len(error_summary)} files.")
    if image_paths:
        print(f"Found {len(image_paths)} image files for potential analysis.")

    return all_extracted_text, error_summary, image_paths