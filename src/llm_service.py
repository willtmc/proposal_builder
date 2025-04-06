import os
import json
import openai
import base64
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any, Tuple
from openai.types import CompletionUsage

PROMPT_DIR_ABS = Path(__file__).resolve().parent.parent / "prompts"
PHOTO_DESC_PROMPT_FILENAME = "photo_description_prompt.txt"
MAX_IMAGES_PER_BATCH = 5

class LLMService:
    def __init__(self, api_key: str, config: Dict):
        if not api_key:
            raise ValueError("OpenAI API key is required.")
        self.client = openai.OpenAI(api_key=api_key)
        self.config = config
        self._load_prompts()

    def _load_prompts(self):
        """Loads system and user prompts from text files."""
        self.prompts = {}
        try:
            self.prompts["template_analysis_system"] = "You are a template analysis expert. Your task is to convert a document into a template format, identifying fields that need to be filled with variables while preserving static content."
            self.prompts["template_analysis_user"] = self._read_prompt_file("template_analysis_prompt.txt")
            
            self.prompts["information_extraction_system"] = (
                "You are a professional real estate analyst. Your task is to extract detailed property information from documents. "
                "Pay special attention to:\n"
                "1. Property details (sq ft, beds/baths, lot size)\n"
                "2. Financial information (listing price, appraisal)\n"
                "3. Legal documents (permits, zoning)\n"
                "4. Special features and amenities\n"
                "5. Location details and accessibility\n"
                "Format all numbers consistently and include units."
            )
            self.prompts["information_extraction_user"] = self._read_prompt_file("information_extraction_prompt.txt")

            self.prompts["final_generation_system"] = "You are a professional proposal writer for a real estate auction company. Fill in the template with the provided information exactly as specified."
            self.prompts["final_generation_user"] = self._read_prompt_file("final_generation_prompt.txt")

            # Load photo description prompt (optional, only needed for that specific function)
            try:
                self.prompts["photo_description_user"] = self._read_prompt_file(PHOTO_DESC_PROMPT_FILENAME)
                self.prompts["photo_description_system"] = "You are an expert inventory specialist and auction cataloger. Describe the items shown in the images in detail, suitable for an auction proposal or inventory list."
            except FileNotFoundError:
                print(f"Warning: Photo description prompt ({PROMPT_DIR_ABS / PHOTO_DESC_PROMPT_FILENAME}) not found. Photo analysis feature will not work.")
                self.prompts["photo_description_user"] = None
                self.prompts["photo_description_system"] = None

        except FileNotFoundError as e:
            # Raise a more general error encapsulating the FileNotFoundError details
            raise RuntimeError(f"Required prompt file missing: {e}. Please ensure all prompt files exist in {PROMPT_DIR_ABS}") from e
        except Exception as e:
            raise RuntimeError(f"Failed to load prompts: {e}")

    def _read_prompt_file(self, filename: str) -> str:
        """Reads a prompt file from the prompt directory using an absolute path."""
        file_path = PROMPT_DIR_ABS / filename
        if not file_path.is_file():
            # Raise FileNotFoundError with a message string (positional argument)
            raise FileNotFoundError(f"Prompt file not found: {file_path}")
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()

    def _call_openai_api(self, system_prompt: str, user_prompt: str, model: str) -> Optional[Tuple[str, CompletionUsage]]:
        """Helper function to call the OpenAI Chat Completion API. Returns content and usage."""
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )
            content = response.choices[0].message.content
            usage = response.usage
            if not content or not content.strip():
                 print("Warning: OpenAI API returned empty content.")
                 return None, usage
            return content, usage
        except openai.APIConnectionError as e:
            print(f"OpenAI API Connection Error: {e}")
        except openai.RateLimitError as e:
            print(f"OpenAI API Rate Limit Error: {e}")
        except openai.APIStatusError as e:
            print(f"OpenAI API Status Error: {e.status_code} - {e.response}")
        except Exception as e:
            print(f"An unexpected error occurred calling OpenAI API: {e}")
        return None, None

    def analyze_template(self, template_text: str) -> Optional[Tuple[str, CompletionUsage]]:
        """Analyzes the template text to identify variables. Returns template_with_vars and usage."""
        print("Step 1: Analyzing template and creating variable structure...")
        if not template_text:
             print("Error: Template text is empty.")
             return None
             
        current_date = datetime.now().strftime("%B %d, %Y")
        user_prompt = self.prompts["template_analysis_user"].format(
            template_text=template_text,
            current_date=current_date
        )
        
        model = self.config.get("openai_model", "gpt-4o")
        template_with_vars, usage = self._call_openai_api(
            self.prompts["template_analysis_system"],
            user_prompt,
            model
        )
        if template_with_vars:
            print("Successfully created template structure.")
            if usage:
                print(f"  Token Usage: Prompt={usage.prompt_tokens}, Completion={usage.completion_tokens}, Total={usage.total_tokens}")
        else:
            print("Error: Failed to create template structure from LLM.")
        return template_with_vars, usage

    def extract_information(self, template_with_vars: str, source_content: str) -> Optional[Tuple[str, CompletionUsage]]:
        """Extracts information from source documents. Returns JSON string and usage."""
        print("\nStep 2: Analyzing source documents...")
        if not source_content:
             print("Error: Source content is empty.")
             return None
             
        user_prompt = self.prompts["information_extraction_user"].format(
            template_with_vars=template_with_vars, 
            combined_source_text=source_content
        )

        model = self.config.get("openai_model", "gpt-4o")
        extracted_info_json, usage = self._call_openai_api(
            self.prompts["information_extraction_system"],
            user_prompt,
            model
        )
        
        if not extracted_info_json:
            print("Error: Failed to extract information from source documents using LLM.")
            return None, usage
            
        # Validate if the response is valid JSON before returning
        try:
            # Clean up potential markdown fences if LLM adds them despite instructions
            if extracted_info_json.startswith("```json"):
                extracted_info_json = extracted_info_json[7:]
            if extracted_info_json.endswith("```"):
                extracted_info_json = extracted_info_json[:-3]
            
            json.loads(extracted_info_json.strip()) # Try parsing
            print("Successfully extracted required information as valid JSON.")
            if usage:
                print(f"  Token Usage: Prompt={usage.prompt_tokens}, Completion={usage.completion_tokens}, Total={usage.total_tokens}")
            return extracted_info_json.strip(), usage
        except json.JSONDecodeError:
            print("Error: LLM response for extracted information is not valid JSON.")
            print("--- LLM Response Start ---")
            print(extracted_info_json)
            print("--- LLM Response End ---")
            return None, usage

    def generate_final_proposal(self, template_with_vars: str, extracted_info_json: str) -> Optional[Tuple[str, CompletionUsage]]:
        """Generates the final proposal by filling the template. Returns markdown string and usage."""
        print("\nStep 3: Generating final proposal...")
        user_prompt = self.prompts["final_generation_user"].format(
            template_with_vars=template_with_vars,
            extracted_info=extracted_info_json
        )

        model = self.config.get("openai_model", "gpt-4o")
        final_proposal, usage = self._call_openai_api(
            self.prompts["final_generation_system"],
            user_prompt,
            model
        )
        if final_proposal:
             print(f"Successfully generated final proposal content (Length: {len(final_proposal)}).")
             if usage:
                 print(f"  Token Usage: Prompt={usage.prompt_tokens}, Completion={usage.completion_tokens}, Total={usage.total_tokens}")
        else:
             print("Error: Failed to generate final proposal from LLM.")
             
        return final_proposal, usage 

    def _encode_image_to_base64(self, image_path: Path) -> Optional[str]:
        """Reads an image file and encodes it to Base64."""
        try:
            print(f"Encoding image: {image_path.name}")
            # Consider adding resizing logic here if needed
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except FileNotFoundError:
            print(f"Warning: Image file not found during encoding: {image_path}")
        except Exception as e:
            print(f"Warning: Error encoding image {image_path.name}: {e}")
        return None

    def _call_openai_multimodal_api(self,
            system_prompt: str, 
            user_text_prompt: str, 
            image_paths: List[Path], 
            model: str,
            max_images_per_call: int = MAX_IMAGES_PER_BATCH
    ) -> Tuple[Optional[str], Optional[CompletionUsage]]:
        """Calls OpenAI API with text and a list of images (handling multiple batches if necessary)."""
        
        all_content_parts = []
        total_usage_dict = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        
        # Process images in batches
        for i in range(0, len(image_paths), max_images_per_call):
            batch_image_paths = image_paths[i:i + max_images_per_call]
            print(f"\nProcessing image batch {i // max_images_per_call + 1}/{ (len(image_paths) + max_images_per_call - 1)// max_images_per_call } ({len(batch_image_paths)} images)...")
            
            messages: List[Dict[str, Any]] = [
                {"role": "system", "content": system_prompt}
            ]
            user_content: List[Dict[str, Any]] = []
            
            # Add user text prompt
            current_user_prompt = user_text_prompt + f"\n\nImages for this batch ({i // max_images_per_call + 1}):"
            user_content.append({"type": "text", "text": current_user_prompt})

            # Add image parts for the current batch
            encoded_image_count = 0
            for img_path in batch_image_paths:
                base64_image = self._encode_image_to_base64(img_path)
                if base64_image:
                    user_content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}" 
                        }
                    })
                    encoded_image_count += 1
                else:
                    print(f"Skipping image {img_path.name} due to encoding error.")
            
            if encoded_image_count == 0:
                print("No images successfully encoded for this batch. Skipping API call.")
                continue
            
            messages.append({"role": "user", "content": user_content})
            
            try:
                print(f"Sending batch {i // max_images_per_call + 1} to OpenAI API ({encoded_image_count} images)...")
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=3000 # Adjust as needed for description length
                )
                content = response.choices[0].message.content
                usage = response.usage

                if content:
                    all_content_parts.append(content.strip())
                    print(f"Received description part for batch {i // max_images_per_call + 1}.")
                    if usage:
                        print(f"  Token Usage (Batch): Prompt={usage.prompt_tokens}, Completion={usage.completion_tokens}, Total={usage.total_tokens}")
                        total_usage_dict["prompt_tokens"] += usage.prompt_tokens
                        total_usage_dict["completion_tokens"] += usage.completion_tokens
                        total_usage_dict["total_tokens"] += usage.total_tokens
                else:
                    print(f"Warning: OpenAI API returned empty content for batch {i // max_images_per_call + 1}.")

            except openai.APIConnectionError as e:
                print(f"OpenAI API Connection Error during batch {i // max_images_per_call + 1}: {e}")
            except openai.RateLimitError as e:
                print(f"OpenAI API Rate Limit Error during batch {i // max_images_per_call + 1}: {e}")
            except openai.APIStatusError as e:
                print(f"OpenAI API Status Error during batch {i // max_images_per_call + 1}: {e.status_code} - {e.response}")
            except Exception as e:
                if "content length" in str(e).lower() or "request entity too large" in str(e).lower():
                    print(f"Error: API request failed for batch {i // max_images_per_call + 1}, likely due to large image sizes or too many images per batch. {e}")
                    print(f"Suggestion: Try reducing MAX_IMAGES_PER_BATCH (currently {max_images_per_call}).")
                else:
                    print(f"An unexpected error occurred calling OpenAI API for batch {i // max_images_per_call + 1}: {e}")
            # Continue to next batch even if one fails

        if not all_content_parts:
            return None, None

        # Combine content from all batches
        final_content = "\n\n".join(all_content_parts)
        
        # Create a pseudo-Usage object for the total
        final_usage = CompletionUsage(**total_usage_dict)

        return final_content, final_usage

    def generate_description_from_photos(self, image_paths: List[Path], target_folder: Path) -> Optional[str]:
        """Generates a description from images and saves it to the target folder."""
        print("--- Starting Photo Description Generation --- ")
        
        if not self.prompts.get("photo_description_user") or not self.prompts.get("photo_description_system"):
            print("Error: Photo description prompts not loaded. Cannot generate description.")
            return None
            
        if not image_paths:
            print("No image paths provided for photo description generation.")
            return None
            
        model = self.config.get("openai_model", "gpt-4o")

        generated_description, total_usage = self._call_openai_multimodal_api(
            system_prompt=self.prompts["photo_description_system"],
            user_text_prompt=self.prompts["photo_description_user"],
            image_paths=image_paths,
            model=model,
            max_images_per_call=MAX_IMAGES_PER_BATCH
        )

        # Report total usage
        if total_usage:
            print(f"\n--- Total Token Usage for Photo Analysis (All Batches) ---")
            print(f"  Prompt: {total_usage.prompt_tokens}")
            print(f"  Completion: {total_usage.completion_tokens}")
            print(f"  Total: {total_usage.total_tokens}")
            print("--------------------------------------------------------")

        # Save the result
        if generated_description:
            output_path = target_folder / "_photo_inventory_description.txt"
            try:
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(generated_description)
                print(f"\nSuccessfully generated description and saved to: {output_path}")
                return generated_description
            except Exception as e:
                print(f"\nError saving description file: {e}")
                return None
        else:
            print("\nFailed to generate description from images.")
            return None 