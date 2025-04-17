"""
crs_parser.py
Module for extracting structured data from CRS Property Report PDFs.
Handles both deterministic parsing and prepares input for LLMs for ambiguous fields.
"""
import re
from typing import Dict, Optional, List

def parse_crs_text(crs_text: str) -> Dict[str, Optional[str]]:
    """
    Extracts key fields from CRS Property Report text.
    Returns a dictionary with as many proposal template variables as possible.
    """
    result = {}

    # Property Address
    address_match = re.search(r"Property Address\s+(.+?)\s+([A-Za-z ]+),\s*([A-Z]{2})\s*(\d{5}(-\d{4})?)", crs_text)
    if address_match:
        result["property_street_address"] = address_match.group(1).strip()
        result["property_city"] = address_match.group(2).strip()
        result["property_state"] = address_match.group(3).strip()
        result["property_postal_code"] = address_match.group(4).strip()
        # For template compatibility
        result["client_city"] = result["property_city"]
        result["client_state"] = result["property_state"]
        result["client_postal_code"] = result["property_postal_code"]

    # Mailing Address (client address fields)
    mailing_match = re.search(r"Mailing Address\s+(.+?)\s+([A-Za-z ]+),\s*([A-Z]{2})\s*(\d{5}(-\d{4})?)", crs_text)
    if mailing_match:
        result["client_street_address"] = mailing_match.group(1).strip()
        result["client_city"] = mailing_match.group(2).strip()
        result["client_state"] = mailing_match.group(3).strip()
        result["client_postal_code"] = mailing_match.group(4).strip()

    # Owner(s)
    owner_matches = re.findall(r"Owner\s+(.+?)(?:\n|$)", crs_text)
    if owner_matches:
        # Combine all owners into a single string, separated by ' and '
        owner_names = [name.strip().replace('Etux', '').replace('Etal', '').replace('Et', '').replace('Et Vir', '').replace('Et Ux', '').replace('Etux.', '').replace('Etal.', '').replace('Et.', '') for name in owner_matches]
        owner_names = [re.sub(r'\s+', ' ', n) for n in owner_names if n]
        owner_names = [n for n in owner_names if n]
        result["owner_name"] = " and ".join(owner_names)

    # Lot Size (acres and sq ft)
    lot_match = re.search(r"Acreage\s+([\d\.]+)", crs_text)
    if lot_match:
        result["lot_size_acres"] = lot_match.group(1)
    lot_sqft_match = re.search(r"Lot Square Feet\s+([\d,]+)", crs_text)
    if lot_sqft_match:
        result["lot_size_sqft"] = lot_sqft_match.group(1).replace(",", "")

    # Appraised Value
    appraised_match = re.search(r"Total T ax Appraisal\s*\$([\d,]+)", crs_text)
    if appraised_match:
        result["appraised_value"] = appraised_match.group(1).replace(",", "")

    # Year Built
    year_built_match = re.search(r"Year Built\s+(\d{4})", crs_text)
    if year_built_match:
        result["year_built"] = year_built_match.group(1)

    # Square Feet
    sqft_match = re.search(r"Square Feet\s+(\d+)", crs_text)
    if sqft_match:
        result["square_feet"] = sqft_match.group(1)

    # Property Type
    prop_type_match = re.search(r"Property T ype\s+([A-Za-z ]+)", crs_text)
    if prop_type_match:
        result["property_type"] = prop_type_match.group(1).strip()

    # Improvement Type
    improvement_match = re.search(r"Improvement T ype\s+([A-Za-z ]+)", crs_text)
    if improvement_match:
        result["improvement_type"] = improvement_match.group(1).strip()

    # Zoning (if present)
    zoning_match = re.search(r"Zoning Code\s+([\w\- ]+)", crs_text)
    if zoning_match:
        result["zoning"] = zoning_match.group(1).strip()

    # Additional fields can be added as needed
    return result

def summarize_for_llm(fields: Dict[str, Optional[str]], full_text: str) -> str:
    """
    Create a structured summary for the LLM prompt, combining parsed fields and raw text for context.
    """
    summary = ["CRS Property Report Summary:"]
    for k, v in fields.items():
        if v:
            summary.append(f"{k.replace('_', ' ').title()}: {v}")
    summary.append("\nFull CRS Text (for reference):\n" + full_text)
    return "\n".join(summary)
