#!/usr/bin/env python3

import os
import sys
import json # Added for pretty printing JSON
import shutil # Import shutil for dependency checking
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, timedelta, date # Added date imports
import calendar

# Import functions/classes from the new modules
from src import config_loader, ui_handler, data_processor, llm_service, file_utils, pdf_handler

# --- Helper Function for Logging --- 
def log_section(title, content, truncate=1000):
    print(f"\n--- DEBUG: {title} ---")
    if isinstance(content, str):
        if len(content) > truncate:
            print(content[:truncate] + f"... [truncated at {truncate} chars]")
        else:
            print(content)
    elif isinstance(content, dict) or isinstance(content, list):
        try:
             print(json.dumps(content, indent=2)) # Pretty print JSON
        except Exception:
             print(content) # Fallback for non-JSON serializable
    else:
        print(content)
    print(f"--- END DEBUG: {title} ---")
# --- End Helper --- 

def run_proposal_builder():
    """
    Main workflow for the proposal builder.
    """
    print("Welcome to the Refactored Proposal Builder!")

    # Load configuration
    config = config_loader.load_config()
    if not config:
        sys.exit(1) # Exit if config loading fails

    # Load API Key from .env or prompt user
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("\nOpenAI API key not found in .env file.")
        api_key = input("Please enter your OpenAI API key: ").strip()
        if not api_key:
             print("API Key is required. Exiting.")
             sys.exit(1)

    # Initialize LLM Service
    try:
        llm = llm_service.LLMService(api_key=api_key, config=config)
    except (ValueError, FileNotFoundError, RuntimeError) as e:
         print(f"Error initializing LLM Service: {e}")
         sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred during LLM service initialization: {e}")
        sys.exit(1)

    # --- Calculate Dynamic Dates --- 
    today = date.today()
    proposal_date_str = today.strftime("%B %d, %Y") # Format for potential use

    # Step 1: Get Auction End Date from User
    auction_weeks = None
    while auction_weeks is None:
        try:
            weeks_input = input(f"\nEnter number of weeks from today ({proposal_date_str}) until Auction End Date: ").strip()
            auction_weeks = int(weeks_input)
            if auction_weeks <= 0:
                 print("Please enter a positive number of weeks.")
                 auction_weeks = None
        except ValueError:
            print("Invalid input. Please enter a number.")
    auction_end_date = today + timedelta(weeks=auction_weeks)
    auction_end_date_str = auction_end_date.strftime("%B %d, %Y")

    # --- New: Calculate Closing Date (30 days after auction, next business day if needed) ---
    def next_business_day(start_date):
        d = start_date
        while d.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
            d += timedelta(days=1)
        return d
    closing_candidate = auction_end_date + timedelta(days=30)
    closing_date = next_business_day(closing_candidate)
    closing_date_str = closing_date.strftime("%B %d, %Y")

    # --- New: Calculate Contract Date (Friday of week following proposal date) ---
    # Find next week's Monday
    days_until_next_monday = (0 - today.weekday() + 7) % 7
    next_monday = today + timedelta(days=days_until_next_monday)
    # Friday of that week
    contract_date = next_monday + timedelta(days=4)
    contract_date_str = contract_date.strftime("%B %d, %Y")

    # --- New: Advertising Start Date (second Monday after contract date) ---
    days_until_monday_from_contract = (0 - contract_date.weekday() + 7) % 7
    first_monday_after_contract = contract_date + timedelta(days=days_until_monday_from_contract)
    advertising_start_date = first_monday_after_contract + timedelta(weeks=1) # Second Monday after contract
    advertising_start_date_str = advertising_start_date.strftime("%B %d, %Y")

    # --- Calculate Acceptance Deadline (Friday after today) ---
    days_until_friday = (4 - today.weekday() + 7) % 7
    if days_until_friday == 0: # If today is Friday, get next Friday
        days_until_friday = 7
    acceptance_deadline_date = today + timedelta(days=days_until_friday)
    acceptance_deadline_date_str = acceptance_deadline_date.strftime("%B %d, %Y")

    print(f"  Calculated Proposal Date: {proposal_date_str}")
    print(f"  Calculated Acceptance Deadline: {acceptance_deadline_date_str}")
    print(f"  Calculated Contract Date: {contract_date_str}")
    print(f"  Calculated Advertising Start Date: {advertising_start_date_str}")
    print(f"  Calculated Auction End Date: {auction_end_date_str}")
    print(f"  Calculated Closing Date: {closing_date_str}")

    # --- Step 1: Select Data Folder ---
    print("\nStep 1: Select the folder containing your source documents")
    print("A file dialog will open - please select the folder.")
    folder_path_str = ui_handler.select_data_folder()
    if not folder_path_str:
        print("No data folder selected. Exiting.")
        sys.exit(1)
    
    folder_path = Path(folder_path_str)
    if not folder_path.is_dir():
        print(f"Error: The path '{folder_path_str}' is not a valid directory.")
        sys.exit(1)
    print(f"Data folder selected: {folder_path}")

    # --- New Step: Select Template Type --- 
    print("\nSelect the type of proposal template to use:")
    print("  1: Personal Property Auction Proposal")
    print("  2: Real Estate Auction Proposal")
    print("  3: Real Estate and Personal Property Auction Proposal")
    
    template_choice = input("Enter choice (1, 2, or 3): ").strip()
    
    # Map choice to TXT filenames in the templates/ directory
    template_filenames = {
        "1": "personal_property_auction_proposal.txt",
        "2": "real_estate_auction_proposal.txt",
        "3": "real_estate_and_personal_property_auction_proposal.txt"
    }
    
    template_filename = template_filenames.get(template_choice)
    
    if not template_filename:
        print("Invalid choice. Exiting.")
        sys.exit(1)
        
    # Construct path to the template TXT file in the templates/ directory
    template_path = Path("templates") / template_filename 
    if not template_path.is_file():
        print(f"Error: Template file not found at expected location: {template_path}")
        print("Please ensure the required template TXT files are in the 'templates' directory.")
        sys.exit(1)
        
    print(f"Using template: {template_filename}")
    # --- End New Step ---

    # --- Step 2: Process Data Folder ---
    # data_processor handles iterating, extracting text, and summarizing errors
    all_extracted_text, error_summary, image_paths = data_processor.process_folder(folder_path)

    # --- Add Default Bios (Will and MAC) to Source Text --- 
    # Read bio files (handle potential errors)
    will_bio = ""
    mac_bio = ""
    try:
        will_bio_path = Path("templates") / "will_mclemore_bio.txt"
        if will_bio_path.is_file():
            will_bio = file_utils.extract_text_file(will_bio_path) or ""
        else:
            print("Warning: templates/will_mclemore_bio.txt not found.")
    except Exception as e:
        print(f"Warning: Could not read Will McLemore bio: {e}")
        
    try:
        mac_bio_path = Path("templates") / "mac_bio.txt"
        if mac_bio_path.is_file():
            mac_bio = file_utils.extract_text_file(mac_bio_path) or ""
        else:
            print("Warning: templates/mac_bio.txt not found.")
    except Exception as e:
        print(f"Warning: Could not read MAC bio: {e}")
        
    # --- Add Optional Photo Description --- 
    photo_description = ""
    photo_desc_path = folder_path / "_photo_inventory_description.txt"
    if photo_desc_path.is_file():
        print(f"Found photo description file: {photo_desc_path.name}")
        try:
            photo_description = file_utils.extract_text_file(photo_desc_path) or ""
            if photo_description:
                print("Successfully read photo description.")
            else:
                print("Warning: Photo description file is empty.")
        except Exception as e:
             print(f"Warning: Could not read photo description file: {e}")
    else:
        print("Photo description file not found. To generate one, run generate_photo_description.py")
        
    # --- Optional: Ask User to Generate Photo Description --- 
    run_photo_analysis = False
    if image_paths:
        user_choice = input(f"Found {len(image_paths)} images. Generate description from photos? (Requires API call, may take time/cost) [y/N]: ").strip().lower()
        if user_choice == 'y':
            run_photo_analysis = True
            # Reset photo_description in case an old file exists but we want to regenerate
            photo_description = ""
            # Call the LLM service method to generate and save the description
            generated_desc = llm.generate_description_from_photos(image_paths, folder_path)
            if generated_desc:
                 photo_description = generated_desc # Use the newly generated description
            else:
                 print("Photo description generation failed. Proceeding without it.")
        else:
             print("Skipping photo analysis.")

    # --- Load Photo Description (if not generated above, check again) --- 
    if not run_photo_analysis and photo_desc_path.is_file(): # Check again if we skipped generation but file exists
        print(f"Using existing photo description file: {photo_desc_path.name}")
        try:
            photo_description = file_utils.extract_text_file(photo_desc_path) or ""
            if not photo_description:
                print("Warning: Existing photo description file is empty.")
        except Exception as e:
             print(f"Warning: Could not read existing photo description file: {e}")
             photo_description = "" # Ensure it's empty on error
            
    # Combine bios with the text extracted from the data folder
    # Using clear separators for the LLM
    # Ensure all_extracted_text exists, even if empty
    client_docs_text = all_extracted_text if all_extracted_text else "[No client documents processed]"
    # Combine all text sources
    combined_source_text = (
        f"PHOTO-BASED INVENTORY:\n{photo_description}\n\n"
        f"AGENT BIO:\n{will_bio}\n\n"
        f"COMPANY BIO:\n{mac_bio}\n\n"
        f"CLIENT DOCUMENTS:\n{client_docs_text}"
    )

    # Print error summary
    if error_summary:
        print("\n--- File Processing Error Summary ---")
        for error in error_summary:
            print(f"- File: {error['file']}, Error: {error['error']}")
        print("------------------------------------")

    if not all_extracted_text:
        print("\nNo text could be extracted from any supported files in the folder.")
        print("Please ensure the folder contains readable files of supported types (PDF, TXT, common image formats).")
        sys.exit(1)

    print(f"\nSuccessfully consolidated text from source documents (Total length: {len(all_extracted_text)} characters).")
    # Log the combined text including bios
    log_section("Combined Source Text (for LLM)", combined_source_text)
    
    # --- Step 4: Read Template File --- (Path determined above)
    print(f"\nReading template file: {template_path.name}...")
    template_text = None
    
    try:
        # Always read the template as a TXT file now
        template_text = file_utils.extract_text_file(template_path)
            
        if not template_text:
            print(f"Failed to extract any text from the template file: {template_path.name}")
            sys.exit(1)
            
        print(f"Successfully extracted {len(template_text)} characters from template.")
        log_section("Extracted Template Text", template_text)

    except Exception as e:
         print(f"An unexpected error occurred while reading the template file: {e}")
         sys.exit(1)

    # --- Step 5: Generate Proposal using LLM ---
    print("\n--- Starting LLM Proposal Generation ---")
    try:
        # Step 5a: Analyze Template
        template_with_vars, usage_analyze = llm.analyze_template(template_text)
        if not template_with_vars:
            print("LLM template analysis failed. Cannot proceed.")
            sys.exit(1)
            
        # Log template_with_vars for debugging
        log_section("Template with Variables (from LLM)", template_with_vars)

        # Step 5b: Extract Information
        extracted_info_json, usage_extract = llm.extract_information(template_with_vars, combined_source_text)
        if not extracted_info_json:
             print("LLM information extraction failed. Cannot proceed.")
             sys.exit(1)
             
        # Log extracted_info_json for debugging
        log_section("Extracted Information JSON (from LLM)", extracted_info_json)

        # --- New Step: Interview User for Missing Information --- 
        updated_extracted_info_json = extracted_info_json # Start with the original
        if extracted_info_json:
            try:
                extracted_data_dict = json.loads(extracted_info_json)

                # --- Inject Calculated/Provided Dates --- 
                print("\nInjecting calculated/provided dates into extracted data...")
                # Overwrite specific date fields with calculated values
                # Ensure keys match the expected variables in templates
                if 'proposal_date' in extracted_data_dict:
                     extracted_data_dict['proposal_date'] = proposal_date_str
                extracted_data_dict['acceptance_deadline_date'] = acceptance_deadline_date_str
                extracted_data_dict['contract_date'] = contract_date_str
                extracted_data_dict['advertising_start_date'] = advertising_start_date_str
                extracted_data_dict['auction_end_date'] = auction_end_date_str
                extracted_data_dict['closing_date'] = closing_date_str
                # --- Marketing fields ---
                extracted_data_dict['deposit_percentage'] = "15" # Always 15%
                extracted_data_dict['marketing_website_newsletter_cost'] = "No Charge"
                # Calculate marketing_total_cost with correct formatting and logic
                def parse_money(val):
                    try:
                        v = str(val).replace('$','').replace(',','').strip()
                        if not v or v.lower() == 'no charge':
                            return 0.0
                        return float(v)
                    except Exception:
                        return 0.0
                total = 0.0
                has_any_value = False
                for k in ['marketing_facebook_cost','marketing_google_cost','marketing_direct_mail_cost','marketing_drone_cost','marketing_signs_cost']:
                    v = extracted_data_dict.get(k)
                    if v is not None and v != '' and str(v).lower() != 'no charge':
                        total += parse_money(v)
                        has_any_value = True
                        # Format each value as currency with commas and 2 decimals
                        try:
                            extracted_data_dict[k] = f"${parse_money(v):,.2f}"
                        except Exception:
                            extracted_data_dict[k] = v
                # Only show 'No Charge' if all fields are zero/blank/No Charge, else show total as $X,XXX.XX
                if has_any_value and total > 0:
                    extracted_data_dict['marketing_total_cost'] = f"${total:,.2f}"
                else:
                    extracted_data_dict['marketing_total_cost'] = "No Charge"
                # Remove eliminated fields if present
                for obsolete in ['marketing_expenses','marketing_retainer_fee_description','commission_reduction_amount']:
                    if obsolete in extracted_data_dict:
                        del extracted_data_dict[obsolete]
                # --- End Date Injection ---

                # --- Fix 1: Only include client_company if present and non-blank ---
                if 'client_company' in extracted_data_dict and (not extracted_data_dict['client_company'] or extracted_data_dict['client_company'].strip() == ''):
                    del extracted_data_dict['client_company']

                # --- Fix 2: Always prompt for marketing budget line items if missing, blank, zero, or 'No Charge' ---
                marketing_keys = [
                    'marketing_facebook_cost',
                    'marketing_google_cost',
                    'marketing_direct_mail_cost',
                    'marketing_drone_cost',
                    'marketing_signs_cost'
                ]
                for k in marketing_keys:
                    v = extracted_data_dict.get(k, None)
                    if v is None or str(v).strip() in ('', '0', '0.0', '$0', '$0.00', 'No Charge', '[Information Not Found]'):
                        extracted_data_dict[k] = '[Information Not Found]'

                # --- Fix 3: Ensure all currency fields use commas and two decimals ---
                def parse_money(val):
                    try:
                        v = str(val).replace('$','').replace(',','').strip()
                        if not v or v.lower() == 'no charge' or v == '[Information Not Found]':
                            return None
                        return float(v)
                    except Exception:
                        return None
                total = 0.0
                has_any_value = False
                for k in marketing_keys:
                    v = extracted_data_dict.get(k)
                    amount = parse_money(v)
                    if amount is not None:
                        has_any_value = True
                        total += amount
                        extracted_data_dict[k] = f"${amount:,.2f}"
                    else:
                        extracted_data_dict[k] = '[Information Not Found]'
                if has_any_value and total > 0:
                    extracted_data_dict['marketing_total_cost'] = f"${total:,.2f}"
                else:
                    extracted_data_dict['marketing_total_cost'] = "No Charge"

                missing_keys = [
                    key for key, value in extracted_data_dict.items() 
                    if value == "[Information Not Found]" and key not in ['marketing_expenses','marketing_retainer_fee_description','commission_reduction_amount']
                ]
                
                if missing_keys:
                    print("\n--- Missing Information Interview ---")
                    print("Some information required by the template was not found in the documents.")
                    print("Please provide the missing details below (or press Enter to omit):")
                    
                    for key in missing_keys:
                        # Create a more user-friendly prompt label
                        prompt_label = key.replace('_', ' ').title()
                        user_value = input(f"  Enter value for '{prompt_label}' (leave blank to omit): ").strip()
                        if user_value:
                            extracted_data_dict[key] = user_value
                        else:
                            extracted_data_dict[key] = "" # Set to blank instead of keeping placeholder
                            
                    # Remove blank fields from the dictionary
                    extracted_data_dict = {k: v for k, v in extracted_data_dict.items() if v not in (None, "", "[Information Not Found]")}
                    # Convert the updated dictionary back to JSON
                    updated_extracted_info_json = json.dumps(extracted_data_dict, indent=2)
                    log_section("Updated Extracted Information JSON (after interview)", updated_extracted_info_json)
                    print("--- Interview Complete ---")
                else:
                     print("\nAll required template information appears to have been found in the documents.")
                     
            except json.JSONDecodeError:
                print("\nWarning: Could not parse extracted information JSON. Skipping user interview.")
            except Exception as e:
                 print(f"\nWarning: An error occurred during the interview process: {e}. Skipping interview.")
        # --- End Interview Step ---

        # Step 5c: Generate Final Proposal
        # Use the potentially updated JSON from the interview
        final_proposal_md, usage_generate = llm.generate_final_proposal(template_with_vars, updated_extracted_info_json)
        if not final_proposal_md:
            print("LLM final proposal generation failed.")
            sys.exit(1)
            
        log_section("Final Proposal Markdown (from LLM)", final_proposal_md)

        # Remove markdown/code block formatting from final proposal output
        # If the LLM output contains triple backticks or markdown code fences, strip them
        def strip_markdown_code_blocks(text):
            import re
            # Remove code blocks (```...```)
            return re.sub(r'```[a-zA-Z]*[\r\n]+|```', '', text)
        final_proposal_md = strip_markdown_code_blocks(final_proposal_md)

    except Exception as e:
        print(f"An unexpected error occurred during the LLM generation process: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # --- Step 6: Save Final Proposal ---
    try:
        # Use timestamp in filename to avoid overwrite
        base_output_filename = config.get("output_filename", "generated_proposal.md")
        stem, ext = os.path.splitext(base_output_filename)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_filename = f"{stem}_{timestamp}{ext}"
        output_file_path = folder_path / output_filename
        print(f"\nSaving generated proposal to: {output_file_path}")
        with open(output_file_path, "w", encoding="utf-8") as f:
            f.write(final_proposal_md)
        print("\nDone! The proposal has been successfully generated.")
    except Exception as e:
        print(f"Error saving the generated proposal file: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Ensure necessary external dependencies like poppler and tesseract are mentioned.
    # Consider adding checks or better error messages in ocr_service if they are missing.
    
    # --- Check for External Dependencies --- 
    tesseract_path = shutil.which("tesseract")
    # Check for pdftoppm, a common tool from poppler-utils used by pdf2image
    poppler_tool_path = shutil.which("pdftoppm") 
    
    missing_deps = []
    if not tesseract_path:
        missing_deps.append("Tesseract OCR (Install via: brew install tesseract OR sudo apt-get install tesseract-ocr)")
    if not poppler_tool_path:
         missing_deps.append("Poppler (Install via: brew install poppler OR sudo apt-get install poppler-utils)")
        
    if missing_deps:
         print("\n--- ERROR: Missing External Dependencies ---", file=sys.stderr)
         for dep in missing_deps:
             print(f" - {dep}", file=sys.stderr)
         print("Please install the missing dependencies and ensure they are in your system PATH.", file=sys.stderr)
         print("---------------------------------------------", file=sys.stderr)
         sys.exit(1) # Exit if dependencies are missing
    else:
         print("External dependencies (Tesseract, Poppler) found.")
    # --- End Dependency Check --- 
    
    run_proposal_builder()

# --- Remove old, unused functions ---
# (All functions previously defined in this file should now be in modules)