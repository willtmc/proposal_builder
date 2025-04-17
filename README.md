# AI Proposal Builder

This script automates the creation of auction proposals by combining information from source documents (text, PDF, images) with predefined templates using AI (OpenAI GPT-4o).

## Features

- Extracts text from TXT files and PDFs (using OCR via Tesseract/Poppler as fallback).
- Optionally analyzes images in the source folder using GPT-4o multimodal capabilities to generate an inventory description.
- Uses predefined text templates (`templates/` directory) for different proposal types (Personal Property, Real Estate, Combined).
- Calculates key dates (proposal date, acceptance deadline, ad start) automatically.
- Prompts user for auction duration to calculate end date **before folder selection**.
- Uses OpenAI GPT-4o for:
    - Analyzing the chosen template to identify variables.
    - Extracting information from source documents (including bios and optional photo description) to fill variables.
    - Generating the final proposal in Markdown format.
- Interactively prompts the user to fill in any information the AI couldn't find, **including all variables marked as `user` in the template index (e.g., retainer, buyer's premium)**.
- Reports OpenAI token usage for each API call.
- Checks for required external dependencies (Tesseract, Poppler) on startup.

## Variable Handling

- **Variable Sources:** Each template variable is marked as `calculated`, `extracted`, or `user` in the template index JSON.
    - `calculated`: Dates and totals computed by business logic.
    - `extracted`: AI attempts to extract from documents, user is prompted if missing.
    - `user`: Always prompted for user input (e.g., retainer, buyer's premium).
- **Currency Formatting:** All currency variables are formatted as plain numbers (no `$`), and the template handles currency symbols.

## Setup

1.  **Clone Repository:** Get the code onto your local machine.
2.  **Dependencies:**
    *   **Python:** Ensure you have Python 3 installed.
    *   **External Tools:**
        *   **Tesseract OCR:** Required for reading text from PDFs/images. Installation varies by OS:
            *   macOS: `brew install tesseract`
            *   Debian/Ubuntu: `sudo apt-get install tesseract-ocr`
        *   **Poppler:** Required by `pdf2image` for PDF processing. Installation varies by OS:
            *   macOS: `brew install poppler`
            *   Debian/Ubuntu: `sudo apt-get install poppler-utils`
        *   *Ensure both `tesseract` and `pdftoppm` (from Poppler) are in your system's PATH.*
    *   **Python Packages:** Create and activate a virtual environment, then install required packages:
        ```bash
        python -m venv venv
        source venv/bin/activate # On Windows use `venv\Scripts\activate`
        pip install -r requirements.txt
        ```
3.  **API Key:**
    *   Create a file named `.env` in the project's root directory.
    *   Add your OpenAI API key to the file like this:
        ```
        OPENAI_API_KEY=your_openai_api_key_here
        ```
4.  **Configuration:**
    *   Review and modify `config.json` if needed (e.g., change the default OpenAI model).
5.  **Templates:**
    *   Review and polish the `.txt` files in the `templates/` directory. Ensure `{{variable_names}}` match expected data.
    *   Review `templates/will_mclemore_bio.txt` and `templates/mac_bio.txt`.
6.  **Prompts:**
    *   Review the prompt files in the `prompts/` directory. These control how the AI behaves.

## Usage

1.  **Activate Environment:** `source venv/bin/activate`
2.  **Prepare Data:** Place your source documents (text files, PDFs containing details, relevant images) into a specific folder.
3.  **Run Script:** Execute the main script from the project root:
    ```bash
    python main.py
    ```
4.  **Follow Prompts:**
    *   The script will first check for Tesseract/Poppler.
    *   It will prompt you for the number of weeks until the auction **before folder selection**.
    *   It will ask you to select the data folder using a file dialog.
    *   It will ask you to choose the template type (1, 2, or 3).
    *   If images are found in the data folder, it will ask if you want to generate a description from them (this uses the multimodal API and may take time/cost money).
    *   It will process files and call the OpenAI API.
    *   If information is missing, it will prompt you to enter values for all `user` and missing `extracted` variables.
    *   Token usage for API calls will be printed.
5.  **Output:** The final proposal will be saved as `generated_proposal.md` (or as configured in `config.json`) inside the data folder you selected.
    *   If photo analysis was run, `_photo_inventory_description.txt` will also be saved/updated in the data folder. 