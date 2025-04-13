# modules/llm_interface.py
import google.generativeai as genai
import logging
import time
import re
import os # Added to potentially access API key if not passed directly

import config # Import the central config

logger = logging.getLogger(__name__)

# --- Global LLM Client (Lazy Initialization) ---
LLM_CLIENTS = {} # Dictionary to hold initialized models

# --- Initialize LLM Client ---
def initialize_llm(model_name):
    """Initializes the GenerativeModel for a specific model name if not already done."""
    global LLM_CLIENTS
    if model_name not in LLM_CLIENTS:
        logger.info(f"Initializing Gemini model: {model_name}")
        if not config.GOOGLE_API_KEY:
             logger.error("GOOGLE_API_KEY not found in config. Cannot initialize Gemini model.")
             raise ValueError("GOOGLE_API_KEY is not configured.")
        try:
            # Configure the API key
            genai.configure(api_key=config.GOOGLE_API_KEY)
            # Create the model instance
            model = genai.GenerativeModel(model_name)
            LLM_CLIENTS[model_name] = model
            logger.info(f"Gemini model '{model_name}' initialized successfully.")
            # Optional: Add a small test query to confirm initialization?
            # try:
            #     model.generate_content("test", generation_config={"max_output_tokens": 5})
            #     logger.info(f"Test query successful for {model_name}.")
            # except Exception as test_e:
            #     logger.error(f"Test query failed for {model_name}: {test_e}", exc_info=True)
            #     del LLM_CLIENTS[model_name] # Remove if test fails
            #     raise ConnectionError(f"Failed to connect or query model {model_name} after initialization.") from test_e

        except Exception as e:
            logger.error(f"Failed to initialize Gemini model '{model_name}': {e}", exc_info=True)
            # Don't add to LLM_CLIENTS if initialization fails
            raise ConnectionError(f"Failed to initialize Gemini model {model_name}.") from e
    return LLM_CLIENTS[model_name]

# --- Query LLM Function ---
def query_llm(prompt, model_name, max_tokens, temperature, retries=2, delay=5):
    """
    Sends a prompt to the specified Google Gemini model and returns the response.

    Args:
        prompt (str): The input prompt for the LLM.
        model_name (str): The name of the Gemini model to use (e.g., "gemini-1.5-flash-latest").
        max_tokens (int): The maximum number of tokens to generate.
        temperature (float): The sampling temperature for generation.
        retries (int): Number of times to retry on failure.
        delay (int): Delay in seconds between retries.

    Returns:
        str: The generated text content from the LLM, or an error message string starting with "Error:".
    """
    try:
        model = initialize_llm(model_name) # Get or initialize the model
    except (ValueError, ConnectionError) as init_err:
        logger.error(f"LLM Initialization Error for {model_name}: {init_err}")
        return f"Error: LLM Initialization Failed - {init_err}"

    # Configure generation parameters
    generation_config = genai.types.GenerationConfig(
        max_output_tokens=max_tokens,
        temperature=temperature
        # Add other parameters if needed (top_p, top_k, stop_sequences)
        # top_p=0.9,
        # top_k=40,
    )

    # Configure safety settings (adjust as needed)
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    ]

    logger.debug(f"Sending prompt to {model_name} (approx {len(prompt)} chars). Max Tokens: {max_tokens}, Temp: {temperature}")

    for attempt in range(retries + 1):
        try:
            response = model.generate_content(
                prompt,
                generation_config=generation_config,
                safety_settings=safety_settings
                # stream=False # Set to True for streaming responses if needed later
            )

            # --- Handle potential safety blocks or empty responses ---
            if not response.candidates:
                 # Check prompt feedback for blockage reason
                 block_reason = response.prompt_feedback.block_reason if response.prompt_feedback else 'Unknown'
                 block_details = response.prompt_feedback.safety_ratings if response.prompt_feedback else 'No details'
                 logger.warning(f"LLM ({model_name}) response blocked. Reason: {block_reason}. Details: {block_details}. Prompt length: {len(prompt)} chars.")
                 # Return a specific error message for blocked content
                 # Shorten prompt in log/error message if it's too long
                 prompt_snippet = (prompt[:200] + '...') if len(prompt) > 200 else prompt
                 return f"Error: Response blocked due to safety settings (Reason: {block_reason}). Review prompt content near: '{prompt_snippet}'"

            # Check the first candidate for finish reason
            candidate = response.candidates[0]
            finish_reason = candidate.finish_reason.name if candidate.finish_reason else 'UNKNOWN'

            if finish_reason == "STOP": # Normal completion
                logger.debug(f"LLM ({model_name}) generated response successfully. Finish reason: {finish_reason}")
                return candidate.content.parts[0].text
            elif finish_reason == "MAX_TOKENS":
                 logger.warning(f"LLM ({model_name}) response truncated due to max_tokens ({max_tokens}). Consider increasing limit or refining prompt.")
                 return candidate.content.parts[0].text # Return truncated text
            elif finish_reason == "SAFETY":
                 safety_ratings = candidate.safety_ratings if candidate.safety_ratings else 'No details'
                 logger.warning(f"LLM ({model_name}) response generation stopped due to safety settings. Finish Reason: {finish_reason}. Details: {safety_ratings}")
                 return f"Error: Response generation stopped by safety settings (Reason: {finish_reason})."
            elif finish_reason == "RECITATION":
                 logger.warning(f"LLM ({model_name}) response generation stopped due to recitation concerns. Finish Reason: {finish_reason}.")
                 return f"Error: Response generation stopped due to recitation concerns (Reason: {finish_reason})."
            else: # OTHER, UNKNOWN, etc.
                 logger.warning(f"LLM ({model_name}) response generation finished with unexpected reason: {finish_reason}. Response text (if any): {candidate.content.parts[0].text[:100] if candidate.content.parts else 'N/A'}...")
                 # Return text if available, otherwise indicate an issue
                 if candidate.content and candidate.content.parts:
                      return candidate.content.parts[0].text
                 else:
                      return f"Error: Response generation finished unexpectedly (Reason: {finish_reason}). No content returned."

        except Exception as e:
            logger.error(f"Error querying LLM ({model_name}) on attempt {attempt + 1}/{retries + 1}: {e}", exc_info=True)
            if attempt < retries:
                logger.info(f"Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                # Check for common API errors in the exception message
                error_str = str(e)
                if "API key not valid" in error_str:
                     return "Error: Invalid Google API Key. Please check your configuration."
                elif "quota" in error_str.lower():
                     return f"Error: API quota exceeded for model {model_name}. Please check your Google Cloud project limits."
                elif "resource_exhausted" in error_str.lower():
                      return f"Error: Resource exhausted for model {model_name}. The service might be temporarily overloaded. Please try again later."
                # Generic error if specific checks fail
                return f"Error: Failed to query LLM {model_name} after {retries + 1} attempts. Last error: {e}"

    # Should not be reachable if loop completes, but added for safety
    return f"Error: LLM query failed for {model_name} after retries."


# --- Clean LLM Output Function ---
def clean_llm_output(raw_text, is_evaluation=False):
    """
    Cleans the raw text output from the LLM.
    Removes common artifacts like markdown formatting characters,
    leading/trailing whitespace, and potentially unwanted preamble/postamble.
    """
    if raw_text is None:
        return ""
    if not isinstance(raw_text, str):
         logger.warning(f"clean_llm_output received non-string input: {type(raw_text)}. Returning empty string.")
         return ""

    text = raw_text

    # Remove common markdown code block fences and language identifiers
    text = re.sub(r"```[\w\s]*\n", "", text)
    text = re.sub(r"```", "", text)

    # Remove common markdown emphasis/strong markers if they wrap the entire response or parts
    # Be cautious not to remove them if they are part of legitimate content (e.g., code examples)
    # This is a simple removal, might need refinement
    text = text.replace("**", "").replace("__", "")
    text = text.replace("*", "").replace("_", "") # More aggressive removal

    # Remove leading/trailing whitespace
    text = text.strip()

    # Optional: Remove common conversational filler if not desired in final output
    # (Be careful with this, might remove intended conversational style)
    # common_fillers = ["Okay, ", "Alright, ", "Sure, ", "Certainly, ", "Here is ", "Here's "]
    # for filler in common_fillers:
    #     if text.lower().startswith(filler.lower()):
    #         text = text[len(filler):]

    # Specific cleaning for evaluations (remove preamble if model adds it)
    if is_evaluation:
         # Find the start of the structured evaluation part
         start_keywords = ["Evaluation:", "Relevance & Understanding:"]
         start_index = -1
         for keyword in start_keywords:
              try:
                   idx = text.index(keyword)
                   if start_index == -1 or idx < start_index:
                        start_index = idx
              except ValueError:
                   continue # Keyword not found

         if start_index > 0: # If keyword found and it's not at the very beginning
              # Check if the text before the keyword is just short filler/noise
              preamble = text[:start_index].strip()
              if len(preamble) < 50 and '\n' not in preamble: # Heuristic for short preamble
                   logger.debug(f"Removing potential evaluation preamble: '{preamble}'")
                   text = text[start_index:]
         elif start_index == -1:
              logger.warning("Could not find standard evaluation start keywords. Using raw cleaned text.")

    # Final strip just in case
    text = text.strip()

    return text

# --- Optional: Function to initialize all configured models at once ---
def initialize_llms():
    """Initializes all LLM models defined in the config."""
    logger.info("Initializing all configured LLMs...")
    models_to_init = [
        config.INTERVIEWER_LLM_MODEL_NAME,
        config.EVALUATOR_LLM_MODEL_NAME
    ]
    initialized_count = 0
    for model_name in set(models_to_init): # Use set to avoid duplicates
        if model_name: # Check if model name is defined
            try:
                initialize_llm(model_name)
                initialized_count += 1
            except Exception as e:
                 logger.error(f"Failed to initialize {model_name} during bulk init: {e}")
        else:
             logger.warning("Skipping initialization for an undefined LLM model name in config.")
    logger.info(f"LLM bulk initialization complete. {initialized_count} models ready.")