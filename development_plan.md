# Development Plan - Proposal Builder

## Current Status (As of Apr 17, 2025)

- **Core Functionality:** The script successfully reads source documents (TXT, PDF via OCR) and combines them with selected templates (stored as TXT) to generate proposals using OpenAI (`gpt-4o`).
- **Refactoring:** The initial monolithic script (`proposal_builder.py`) has been refactored into a modular structure within the `src/` directory, improving maintainability.
- **Configuration:** Key settings (model name, output filename) are managed via `config.json`. API key is managed via `.env`.
- **Template Handling:** Uses `.txt` templates stored in the `templates/` directory. User selects template type via command-line prompt.
- **Date Handling:** Automatically calculates proposal date, contract date, advertising start, auction end, and closing date using business rules. Prompts user for auction duration (weeks) **before folder selection**.
- **Variable Indexing:** Each template variable is indexed as `calculated`, `extracted`, or `user` in the template index JSON:
    - `calculated`: Dates and totals computed by business logic.
    - `extracted`: AI attempts to extract from documents, user is prompted if missing.
    - `user`: Always prompted for user input (e.g., retainer, buyer's premium).
- **Currency Handling:** All currency variables are formatted as plain numbers (no `$`), with the template handling currency symbols for output.
- **Interactive Interview:** If the LLM cannot find specific information required by the template in the source documents, the script interactively prompts the user to provide the missing values, including all `user` variables.
- **Token Usage Reporting:** Prints OpenAI token usage after each API call.
- **Dependency Checks:** Checks for required external dependencies (Tesseract, Poppler) on startup and provides installation guidance if missing.
- **Optional Photo Analysis:**
    - If images are found in the data folder, the user is prompted whether to perform AI analysis (via `gpt-4o` multimodal).
    - If yes, the script analyzes images (in batches), generates a description, and saves it to `_photo_inventory_description.txt` within the data folder.
    - The main script includes this generated (or pre-existing) photo description in the context sent to the LLM for information extraction.

## Potential Next Steps / Improvements

1.  **Refine Prompts:** Continue testing with various source documents and templates to refine the LLM prompts (especially `information_extraction_prompt.txt`) for better accuracy and handling of edge cases (e.g., different ways data might be formatted in source files).
2.  **Error Handling:**
    *   More granular error handling within LLM interaction steps (e.g., specific handling for API errors vs. empty responses).
    *   Potentially offer retry logic for transient API errors.
3.  **Photo Analysis Enhancements:**
    *   **Resizing:** Implement image resizing before encoding/uploading to potentially reduce API costs and stay within payload limits.
    *   **Batching Strategy:** Refine the logic for how batches are sent and results combined, especially if descriptions need to flow coherently.
    *   **Prompt Tuning:** Improve the `photo_description_prompt.txt` based on results.
    *   **Configurable Batch Size:** Make `MAX_IMAGES_PER_BATCH` configurable in `config.json`.
4.  **Output Formatting:**
    *   Optionally allow omitting sections/lines entirely in the final proposal if information is missing (instead of printing `[Information Not Found]`). This would require adjusting the final generation prompt.
    *   Explore outputting to different formats (e.g., DOCX) potentially using libraries like `pandoc` (requires external installation).
5.  **Input Flexibility:**
    *   Allow user to specify output filename/location.
    *   Support more source file types if needed.
6.  **User Experience:**
    *   Consider a simple GUI (e.g., using `PySimpleGUI` or a web framework like Flask/FastAPI for a future web version) instead of pure command-line interaction, especially for the interview step.
7.  **Testing:** Implement automated tests (unit tests, integration tests) to ensure reliability and prevent regressions during future development.
8.  **Cost Tracking:** Add optional (estimated) cost calculation based on token usage reported by the API. 