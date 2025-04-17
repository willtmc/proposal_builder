#!/usr/bin/env python3

from dotenv import load_dotenv
load_dotenv()

import os
import sys
import json # Added for pretty printing JSON
import shutil # Import shutil for dependency checking
from pathlib import Path
from datetime import datetime, timedelta, date # Added date imports
import calendar
import subprocess
import re

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

def load_template_var_index(template_filename):
    # Remove .txt extension if present
    if template_filename.endswith('.txt'):
        template_var_index_filename = template_filename[:-4] + '.json'
    else:
        template_var_index_filename = template_filename + '.json'
    template_var_index_path = Path("template_var_indexes") / template_var_index_filename
    with open(template_var_index_path, "r") as f:
        return json.load(f)

def has_template_changed(template_path, template_var_index_path):
    index_mtime = template_var_index_path.stat().st_mtime if template_var_index_path.exists() else 0
    template_mtime = template_path.stat().st_mtime
    return template_mtime > index_mtime

def render_template(template, values):
    import re
    def replacer(match):
        key = match.group(1).strip()
        return str(values.get(key, f"[MISSING:{key}]") )
    return re.sub(r"{{\s*([a-zA-Z0-9_]+)\s*}}", replacer, template)

def run_template_indexer(template_filename):
    script_path = Path("scripts/template_variable_indexer.py")
    template_name_no_ext = template_filename[:-4] if template_filename.endswith(".txt") else template_filename
    # Run the indexer script for this template
    result = subprocess.run([
        "python3", str(script_path)
    ], capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print("Error: Failed to re-index template variables.\n" + result.stderr)
        return False
    return True

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

    # --- Ask for Auction Date (weeks out) BEFORE folder selection ---
    while True:
        try:
            weeks = int(input("How many weeks from today should the auction end date be? (integer): ").strip())
            break
        except Exception:
            print("Please enter a valid integer for weeks.")

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

    # Load template variable index
    template_vars = load_template_var_index(template_filename)
    template_var_index_path = Path("template_var_indexes") / (template_filename[:-4] + ".json" if template_filename.endswith(".txt") else template_filename + ".json")
    if has_template_changed(template_path, template_var_index_path):
        print("WARNING: The template has changed since the last variable index was generated.")
        choice = input("Would you like to re-index variables now? (Y/n): ").strip().lower()
        if choice in ("", "y", "yes"):
            if run_template_indexer(template_filename):
                print("Template variable index regenerated. Reloading index...")
                template_vars = load_template_var_index(template_filename)
            else:
                print("Failed to regenerate index. Exiting.")
                sys.exit(1)
        else:
            print("Cannot proceed with outdated index. Exiting.")
            sys.exit(1)

    # --- Step 2: Process Data Folder ---
    # data_processor handles iterating, extracting text, and summarizing errors
    all_extracted_text, error_summary, image_paths = data_processor.process_folder(folder_path)

    # --- AI Extraction Function ---
    def extract_variables_with_ai(llm, doc_text, variable_index):
        extract_vars = [v['name'] for v in variable_index if v['source'] == 'extracted']
        if not extract_vars:
            return {}
        system_prompt = (
            "You are an expert at reading real estate documents. Given the following document, extract values for these variables: "
            f"{extract_vars}. Return your answer as a JSON object mapping variable names to values. If a variable is not present, use null or ''."
        )
        user_prompt = f"Document:\n{doc_text}\n\nExtract these variables: {extract_vars}\nReturn as JSON."
        try:
            response, _ = llm._call_openai_api(system_prompt, user_prompt, llm.config.get("openai_model", "gpt-4o"))
            import json as _json
            if response:
                try:
                    json_start = response.find('{')
                    json_end = response.rfind('}') + 1
                    json_str = response[json_start:json_end]
                    return _json.loads(json_str)
                except Exception:
                    print("Warning: Could not parse JSON from LLM response.\nResponse was:\n", response)
            return {}
        except Exception as e:
            print(f"Error during LLM extraction: {e}")
            return {}

    # --- AI Variable Extraction for Each Document ---
    ai_extracted_vars = {}
    ai_vars = extract_variables_with_ai(llm, all_extracted_text, template_vars)
    if ai_vars:
        ai_extracted_vars.update({k: v for k, v in ai_vars.items() if v not in (None, "", "null")})

    # --- Interview and Value Filling ---
    extracted_data_dict = dict(ai_extracted_vars) # Start with AI-filled vars
    for var in template_vars:
        name = var["name"]
        source = var["source"]
        is_currency = var["is_currency"]
        is_date = var["is_date"]
        value = extracted_data_dict.get(name)
        if value:
            continue  # Already filled from AI
        # 1. Calculated fields: skip for now, calculate after interview
        if source == "calculated":
            continue
        # 2. User fields: always prompt if missing
        if source == "user":
            value = input(f"Enter value for '{name.replace('_',' ').title()}': ")
        # 3. Extracted fields: should have been filled by AI, but if not, prompt as fallback
        elif source == "extracted":
            value = input(f"Enter value for '{name.replace('_',' ').title()}': ")
        extracted_data_dict[name] = value

    # --- Calculate and Format Calculated Fields ---
    # Dates (using user-provided and business rules)
    def get_next_weekday(base_date, weekday):
        days_ahead = weekday - base_date.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        return base_date + timedelta(days=days_ahead)

    def get_second_monday(base_date):
        first_monday = get_next_weekday(base_date, 0)
        return first_monday + timedelta(days=7)

    def get_next_business_day(base_date):
        if base_date.weekday() == 5:
            return base_date + timedelta(days=2)
        elif base_date.weekday() == 6:
            return base_date + timedelta(days=1)
        return base_date

    def get_second_friday(base_date):
        first_friday = get_next_weekday(base_date, 4)
        return first_friday + timedelta(days=7)

    today = date.today()

    # 1. Auction Date: Use weeks collected earlier, set to next Thursday after that
    auction_base = today + timedelta(weeks=weeks)
    auction_date = get_next_weekday(auction_base, 3)  # 3=Thursday

    # 2. Proposal Date: always today
    proposal_date = today

    # 3. Contract Date: second Friday after proposal date
    contract_date = get_second_friday(proposal_date)

    # 4. Advertising Start Date: Second Monday after proposal date
    advertising_start_date = get_second_monday(proposal_date)

    # 5. Closing Date: 30 days after auction date, or next business day if weekend
    closing_date_base = auction_date + timedelta(days=30)
    closing_date = get_next_business_day(closing_date_base)

    # Format all dates as "Month DD, YYYY"
    def fmt(dt):
        return dt.strftime("%B %d, %Y")

    extracted_data_dict["proposal_date"] = fmt(proposal_date)
    extracted_data_dict["contract_date"] = fmt(contract_date)
    extracted_data_dict["advertising_start_date"] = fmt(advertising_start_date)
    extracted_data_dict["auction_end_date"] = fmt(auction_date)
    extracted_data_dict["closing_date"] = fmt(closing_date)

    # Marketing total cost
    marketing_keys = [
        "marketing_facebook_cost", "marketing_google_cost", "marketing_direct_mail_cost",
        "marketing_drone_cost", "marketing_signs_cost"
    ]
    total = 0.0
    for k in marketing_keys:
        v = extracted_data_dict.get(k, "0")
        try:
            amount = float(str(v).replace("$","").replace(",","").strip())
        except Exception:
            amount = 0.0
        total += amount
        extracted_data_dict[k] = f"{amount:,.2f}"
    extracted_data_dict["marketing_total_cost"] = f"{total:,.2f}"

    # Retainer formatting (now 'retainer', not 'retainer_fee')
    retainer = extracted_data_dict.get("retainer", extracted_data_dict.get("retainer_fee", "0"))
    try:
        retainer_amount = float(str(retainer).replace("$","").replace(",","").strip())
    except Exception:
        retainer_amount = 0.0
    extracted_data_dict["retainer"] = f"{retainer_amount:,.2f}"

    # Total due at contract
    extracted_data_dict["total_due_at_contract"] = f"{(total + retainer_amount):,.2f}"

    # Currency formatting for all currency fields (plain numbers, no $)
    for var in template_vars:
        if var["is_currency"]:
            k = var["name"]
            v = extracted_data_dict.get(k)
            if v is not None:
                try:
                    amount = float(str(v).replace("$","").replace(",","").strip())
                    extracted_data_dict[k] = f"{amount:,.2f}"
                except Exception:
                    pass

    # --- Render Template ---
    with open(template_path, "r") as f:
        template_content = f.read()

    proposal_text = render_template(template_content, extracted_data_dict)

    # --- Write Proposal Output to Selected Folder with Timestamp ---
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_filename = f"generated_proposal_{timestamp}.md"
    output_path = folder_path / output_filename
    with open(output_path, "w") as f:
        f.write(proposal_text)
    print(f"Proposal generated and saved to {output_path}")


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