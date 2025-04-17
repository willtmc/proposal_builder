"""
crs_parser.py
Module for extracting structured data from CRS Property Report PDFs using LLM-based extraction.
"""
import os
import json
from typing import Dict, Optional, List
from pathlib import Path
from .llm_service import LLMService

# CONFIGURATION - update as needed for your environment
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
LLM_CONFIG = {"openai_model": "gpt-4o"}  # or your preferred model
# Path to the variable index JSON (single source of truth)
VAR_INDEX_PATH = Path(__file__).parent.parent / "template_var_indexes/real_estate_auction_proposal.json"
PROMPT_PATH = Path(__file__).parent.parent / "prompts/information_extraction_prompt.txt"


def extract_variables_from_document(source_content: str, var_index_path: Optional[Path] = None, prompt_path: Optional[Path] = None) -> Optional[Dict]:
    """
    Extract template variables (as defined in the variable index JSON) from any document using LLMService.
    :param source_content: The full text of the CRS or other source document(s).
    :param var_index_path: Path to the variable index JSON. Defaults to VAR_INDEX_PATH.
    :param prompt_path: Path to the extraction prompt. Defaults to PROMPT_PATH.
    :return: Dict of extracted variable values, or None on failure.
    """
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY environment variable not set.")
    llm = LLMService(api_key=OPENAI_API_KEY, config=LLM_CONFIG)
    if var_index_path is None:
        var_index_path = VAR_INDEX_PATH
    if prompt_path is None:
        prompt_path = PROMPT_PATH
    # Load variable names from index, filtering for source == "extracted"
    with open(var_index_path, "r", encoding="utf-8") as f:
        var_index = json.load(f)
    variable_names = [v["name"] for v in var_index if v.get("source") == "extracted"]
    # Build the prompt: list variables explicitly, do NOT include the template
    variable_list_str = "\n".join([f"- {name}" for name in variable_names])
    user_prompt = (
        f"Here is the list of required variables for the proposal (use these as JSON keys):\n"
        f"{variable_list_str}\n\n"
        f"Here are the source documents (potentially including a photo-based inventory description, agent bio, company bio, and client documents):\n\n"
        f"{source_content}\n\n"
        f"---\n"
        f"Special Instructions for CRS Property Reports:\n"
        f"- For owner_name, if the CRS lists a name like 'Brock Perry Lynn Etux Phyllis', convert this to 'Perry Lynn and Phyllis Brock'. The first part is the primary owner (first and middle names), and 'Etux' or 'Et Vir' means 'and [spouse first name]'. Place the last name at the end.\n"
        f"  Example: 'Smith John Etux Jane' → 'John and Jane Smith'\n"
        f"- For owner address fields (client_street_address, client_city, client_state, client_postal_code), always use the 'Mailing Address' line directly below the owner name in the CRS Property Report.\n"
        f"- If the owner is a company, map the company name to client_company and leave individual name fields blank.\n"
        f"- If there are multiple owners, list all of them in the owner_name field, separated by 'and'.\n"
        f"- If a value is definitively not found in the source documents for a specific variable, use the exact placeholder '[Information Not Found]'. Do not guess or make up information.\n"
        f"- Format the response as a JSON object where keys are variable names (no curly braces) and values are the extracted content or the placeholder.\n"
        f"- Ensure the output is ONLY the JSON object, with no preamble or explanation.\n"
    )
    system_prompt = (
        "You are a professional real estate analyst. Your task is to extract detailed property information from documents. "
        "Pay special attention to: Property details, financial information, legal documents, special features, location details. "
        "Format all numbers consistently and include units."
    )
    # Call LLM
    extracted_json, _ = llm._call_openai_api(system_prompt, user_prompt, LLM_CONFIG["openai_model"])
    if not extracted_json:
        print("Failed to extract information from document.")
        return None
    try:
        # Clean up potential markdown fences if LLM adds them
        if extracted_json.startswith("```json"):
            extracted_json = extracted_json[7:]
        if extracted_json.endswith("```"):
            extracted_json = extracted_json[:-3]
        return json.loads(extracted_json.strip())
    except Exception as e:
        print(f"Failed to parse extracted JSON: {e}")
        return None
