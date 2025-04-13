# modules/interview_logic.py
import logging
import re
import time
import json
import requests
import socket
import os

# Local module imports
import config
# Use absolute imports within the package if running as a module
from . import utils
from . import llm_interface
from . import prompt_templates
from . import audio_utils # For STT call
from . import report_generator

logger = logging.getLogger(__name__)

# --- Helper to Send Text to NeuroSync Player ---
def send_text_to_player(text_to_send):
    """Sends text to the NeuroSync Player service over TCP."""
    host = config.NEUROSYNC_PLAYER_HOST
    port = config.NEUROSYNC_PLAYER_PORT
    if not text_to_send:
        logger.warning("Attempted to send empty text to player.")
        return False
    logger.info(f"Sending text to NeuroSync Player ({host}:{port}): '{text_to_send[:80]}...'")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5.0) # Timeout for connection and send
            s.connect((host, port))
            s.sendall(text_to_send.encode('utf-8'))
            s.shutdown(socket.SHUT_WR) # Signal end of sending

            # Optional: Wait briefly for confirmation (NeuroSync Player needs to send one back)
            try:
                 confirmation = s.recv(1024)
                 if confirmation:
                      logger.info(f"Received confirmation from player: {confirmation.decode('utf-8')}")
                      return True
                 else:
                      # This might happen if player closes connection immediately after receiving
                      logger.warning("No confirmation received from player (but text likely sent).")
                      return True # Assume sent if no error
            except socket.timeout:
                 logger.warning("Timeout waiting for confirmation from player (text likely sent).")
                 return True # Assume sent if no error
            except ConnectionResetError:
                 logger.warning("Player closed connection before confirmation could be read (text likely sent).")
                 return True

    except socket.timeout:
         logger.error(f"Timeout connecting or sending to NeuroSync Player at {host}:{port}.")
         return False
    except ConnectionRefusedError:
        logger.error(f"Connection refused by NeuroSync Player at {host}:{port}. Is it running?")
        return False
    except socket.error as sock_err:
         logger.error(f"Socket error sending text to player: {sock_err}", exc_info=True)
         return False
    except Exception as e:
        logger.error(f"Unexpected error sending text to player: {e}", exc_info=True)
        return False

# --- Helper to Parse Questions ---
def parse_generated_questions(raw_text):
    """
    Parses the LLM response (expected to be a numbered list) to extract questions.
    Removes common LLM preamble/postamble and specific tags used in generation.
    """
    if not raw_text: return []
    questions = []
    # Regex to find lines starting with number., -, *, etc., possibly after tags or whitespace
    # Allow for optional closing punctuation on the number (like ')')
    pattern = re.compile(r"^\s*(?:\[.*?\])?\s*(?:\d{1,2}[\.\)])?\s*(?:[-*•])?\s*(.*)")

    lines = raw_text.strip().split('\n')

    # Expanded list of potential tags/prefixes to remove
    q_type_tags_to_remove = [
        # Specific types from template
        "[Technical/Conceptual]", "[Database Concept]", "[Database Administration]",
        "[Database Concept/Administration]", "[SQL Query]", "[SQL Query Writing]",
        "[SQL Query (Advanced)]", "[Troubleshooting/Problem Solving]", "[Troubleshooting]",
        "[Troubleshooting/Performance]", "[Behavioral/Learning]", "[Coding/Algorithmic]",
        "[System Design]", "[Security Concept]", "[Cloud Concept (if relevant)]",
        "[Behavioral/Teamwork]", "[Behavioral/Problem Solving]", "[DB Concept]",
        "[DB Admin Task]", "[DB Design/Schema]", "[DB Scenario]", "[Performance Scenario]",
        "[Security Scenario]", "[Cloud Scenario]", "[Learning Scenario]", "[Backup/Recovery Scenario]",
        "[Project Deep Dive]", "[Technical Concept/Tradeoff]", "[Coding Challenge (Scenario)]",
        "[System Design (Scenario)]", "[Debugging Scenario]", "[Behavioral Scenario (Teamwork)]",
        "[Behavioral Scenario (Learning)]", "[Technical Scenario]", "[Problem Solving Scenario]",
        "[Tool/Concept Question]", "[Design Question]", "[Behavioral Question]", "[Learning Question]",
        "[DB Concept/Scenario]", "[SQL Query (Scenario)]", "[Troubleshooting Scenario]",
        "[DB Admin Task/Scenario]", "[Security Scenario]", "[Behavioral Scenario (Learning)]",
        # Generic Prefixes often added by LLMs
        "Question:", "Follow-up:", "Next question:", "Okay, next:", "Let's discuss:", "How about:", "Can you explain:",
        "Scenario:", "Task:", "Problem:", "Concept:", "Behavioral:", "Technical:", "Coding:", "Design:"
    ]
    # Common preamble/postamble phrases to ignore completely
    skip_prefixes = ("okay", "great", "thanks", "sure", "understood", "evaluation:", "alignment",
                     "technical accuracy", "relevance", "strengths:", "areas for improvement",
                     "overall score", "here are", "generating", "note:", "based on the", "the question",
                     "interview questions:", "response:", "answer:", "certainly", "here is", "here's")

    for line in lines:
        line_strip = line.strip()
        # Skip empty lines or lines that only contain preamble/postamble
        if not line_strip or any(line_strip.lower().startswith(p) for p in skip_prefixes):
            continue

        match = pattern.match(line_strip)
        if match:
            question_text = match.group(1).strip()
            original_text = question_text # Keep track
            cleaned_text = question_text

            # Iteratively remove known tags/prefixes from the beginning
            cleaned_something = True
            while cleaned_something:
                cleaned_something = False
                for tag in q_type_tags_to_remove:
                    # Case-insensitive match, allowing optional colon/dash and space after tag
                    tag_pattern = r'^\s*' + re.escape(tag) + r'\s*[:\-\s]?\s*'
                    if re.match(tag_pattern, cleaned_text, re.IGNORECASE):
                        new_text = re.sub(tag_pattern, '', cleaned_text, count=1, flags=re.IGNORECASE).strip()
                        if new_text != cleaned_text: # Check if substitution actually happened
                           # logger.debug(f"Removed tag/prefix '{tag}' -> '{new_text}'")
                           cleaned_text = new_text
                           cleaned_something = True
                           break # Restart check with potentially new prefixes revealed

            # Add question if it looks valid
            # Heuristics: not empty, reasonable length, ends with '?' or contains typical question words
            # or if significant cleaning happened.
            if cleaned_text and len(cleaned_text) > 10:
                 q_words = {"what", "how", "why", "explain", "describe", "tell", "compare", "contrast", "give", "scenario"}
                 ends_q = cleaned_text.endswith('?')
                 has_q_word = any(word in cleaned_text.lower() for word in q_words)
                 if ends_q or has_q_word or len(cleaned_text) > 30 or (cleaned_text != original_text):
                      # Prefer cleaned text unless it became suspiciously short/empty
                      final_text = cleaned_text if len(cleaned_text) > 5 else original_text
                      if final_text not in questions: # Avoid duplicates
                           questions.append(final_text)
                 else:
                      # If no strong indicators, but it passed initial regex, maybe keep original?
                      logger.warning(f"Question candidate doesn't strongly look like a question, keeping original: '{original_text}'")
                      if original_text not in questions:
                           questions.append(original_text)

    # Fallback if regex parsing yielded too few results but there are multiple lines
    if not questions and len(lines) > 1:
         logger.warning("Primary regex failed to parse questions, using basic newline/length split fallback.")
         potential_questions = [l.strip() for l in lines if l.strip() and len(l.strip()) > 20 and not any(l.strip().lower().startswith(p) for p in skip_prefixes)]
         # Basic cleaning for fallback
         for q in potential_questions:
             q_cleaned = re.sub(r'^\s*\d+[\.\)]?\s*', '', q).strip() # Remove leading numbers
             if q_cleaned and q_cleaned not in questions:
                 questions.append(q_cleaned)

    questions = [q for q in questions if q] # Final filter for empty strings
    logger.info(f"Parsed {len(questions)} potential questions from LLM generation.")
    return questions


# --- Interview Session Class ---
class InterviewSession:
    def __init__(self, interview_id, resume_text, jd_text):
        self.interview_id = interview_id
        self.resume_text_raw = resume_text
        self.jd_text_raw = jd_text
        self.role_title = "Relevant Role (Check JD)"
        self.resume_summary = ""
        self.jd_summary = ""
        self.project_details = ""
        self.focus_topics = []
        self.prepared_questions = []
        self.conversation_history = [] # List of {"speaker": name, "text": content}
        self.interview_qna = [] # List of turn data dicts for evaluation/report
        self.asked_questions_indices = set() # Tracks indices of prepared questions *successfully asked*
        self.current_turn_number = 0 # Increments when candidate response is processed
        self.state = "INITIALIZING" # INITIALIZING, READY, IN_PROGRESS, ASKING, AWAITING_RESPONSE, EVALUATING, FINISHED, ERROR
        self.last_ai_message = "" # Store the last question/message AI sent
        self.last_question_context = {} # Store info about the question AI just asked for QnA linking
        self.evaluation_complete = False
        self.report_generated = False
        self.report_path = None
        self.error_message = None # Store specific error message if state is ERROR

        self._initialize_session()

    def _set_error_state(self, message):
        """Helper to set the error state and log."""
        logger.error(f"[{self.interview_id}] Error: {message}")
        self.state = "ERROR"
        self.error_message = message
        # Send error message to player? Maybe not, frontend handles displaying errors.
        # send_text_to_player(f"An internal error occurred: {message}")
        self.last_ai_message = f"An error occurred: {message}" # For frontend display

    def _initialize_session(self):
        """Performs initial text analysis and question generation."""
        logger.info(f"[{self.interview_id}] Initializing interview session...")
        try:
            # 1. Summarize and Extract Details (Basic cleaning)
            self.resume_summary = utils.clean_text(self.resume_text_raw[:config.MAX_SUMMARY_LENGTH * 2])[:config.MAX_SUMMARY_LENGTH]
            self.jd_summary = utils.clean_text(self.jd_text_raw[:config.MAX_SUMMARY_LENGTH * 2])[:config.MAX_SUMMARY_LENGTH]
            # Use the raw text for project details extraction as cleaning might remove structure
            self.project_details = utils.extract_project_details(self.resume_text_raw)
            if len(self.project_details) > config.MAX_PROJECT_SUMMARY_LENGTH:
                 self.project_details = self.project_details[:config.MAX_PROJECT_SUMMARY_LENGTH] + "... (truncated)"
            logger.info(f"[{self.interview_id}] Input texts summarized. Extracted {len(self.project_details)} chars of project/experience details.")

            # 2. Identify Role and Focus Topics
            role_match = re.search(r"^(?:Job\s+)?Title\s*[:\-]?\s*(.*?)(\n|$)", self.jd_text_raw, re.IGNORECASE | re.MULTILINE)
            self.role_title = role_match.group(1).strip() if role_match else "Relevant Role (from Job Description)"
            logger.info(f"[{self.interview_id}] Identified Role Title: {self.role_title}")
            # Ensure focus topics are relevant and not too generic
            self.focus_topics = utils.get_focus_topics(self.resume_text_raw, self.jd_text_raw, top_n=5)
            logger.info(f"[{self.interview_id}] Identified Focus Topics: {self.focus_topics}")

            # 3. Prepare RAG Context (Optional)
            rag_context = "No RAG context available or enabled."
            # RAG logic remains the same as before...
            if config.RETRIEVAL_TOP_K > 0:
                # Ensure embedding model is loaded (utils.py should handle this)
                if not utils.embedding_model:
                    logger.warning(f"[{self.interview_id}] RAG enabled but embedding model not loaded. Skipping retrieval.")
                else:
                    search_queries = utils.generate_search_queries(self.resume_summary, self.jd_summary) # Use summaries
                    if search_queries:
                        all_retrieved_docs = []
                        logger.info(f"[{self.interview_id}] Retrieving RAG context for {len(search_queries)} queries...")
                        for query in search_queries:
                            docs = utils.retrieve_similar_documents(query, top_k=config.RETRIEVAL_TOP_K, threshold=config.RETRIEVAL_SIMILARITY_THRESHOLD)
                            if docs: all_retrieved_docs.extend(docs)

                        if all_retrieved_docs:
                            unique_docs_dict = {doc['content']: doc for doc in all_retrieved_docs} # Simple dedupe by content
                            sorted_unique_docs = sorted(unique_docs_dict.values(), key=lambda x: x.get("score", 0), reverse=True)
                            rag_context = utils.format_rag_context(sorted_unique_docs, max_length=config.MAX_CONTEXT_LENGTH)
                            logger.info(f"[{self.interview_id}] RAG context prepared (length: {len(rag_context)} chars).")
                        else:
                            logger.warning(f"[{self.interview_id}] No relevant documents found in knowledge base for RAG.")
                    else:
                        logger.warning(f"[{self.interview_id}] Could not generate search queries for RAG.")
            else:
                logger.info(f"[{self.interview_id}] Skipping RAG context retrieval (RETRIEVAL_TOP_K <= 0).")


            # 4. Determine Role-Specific Guidance (Refined based on role title check)
            role_lower = self.role_title.lower()
            if "database admin" in role_lower or "dba" in role_lower or "database administrator" in role_lower:
                q_types_list = ["[DB Concept/Scenario]", "[SQL Query (Scenario)]", "[Troubleshooting Scenario]", "[DB Admin Task/Scenario]", "[Security Scenario]", "[Behavioral/Learning Scenario]"]
                role_guidance = {"role": "Probe core DB concepts, backup/recovery, performance tuning.", "code": "Focus on practical SQL for administration & querying.", "solve": "Present common DBA challenges (e.g., locking, slow queries, disk space)."}
            elif "software engineer" in role_lower or "developer" in role_lower or "programmer" in role_lower:
                q_types_list = ["[Technical Concept/Tradeoff]", "[Coding Challenge (Scenario)]", "[System Design (Scenario)]", "[Debugging Scenario]", "[Behavioral Scenario (Teamwork)]", "[Behavioral Scenario (Learning)]"]
                role_guidance = {"role": "Assess CS fundamentals, data structures, algorithms.", "code": "Provide small coding problems (logic, syntax).", "solve": "Debugging/design scenarios related to application development."}
            else: # Default / Analyst / Other
                q_types_list = ["[Technical Scenario]", "[Problem Solving Scenario]", "[Tool/Concept Question]", "[Data Interpretation (if relevant)]", "[Behavioral Question]", "[Learning Question]"]
                role_guidance = {"role": "Focus on general tech concepts relevant to the JD.", "code": "Ask about high-level logic or specific tool usage.", "solve": "Present general technical or analytical challenges."}
            logger.info(f"[{self.interview_id}] Using role guidance for '{role_lower}': {role_guidance}")


            # 5. Prepare Prompt Arguments for Question Generation
            num_questions_total = config.NUM_QUESTIONS + 1 # +1 for project deep dive
            qg_prompt_args = {
                "role_title": self.role_title,
                "resume_summary": self.resume_summary or "Not provided.",
                "jd_summary": self.jd_summary or "Not provided.",
                "project_details": self.project_details or "No specific project details extracted.",
                "focus_str": ', '.join(self.focus_topics) if self.focus_topics else f'General skills for {self.role_title}',
                "context_str": rag_context,
                "num_questions": config.NUM_QUESTIONS, # Number of main questions
                "num_questions_plus_one": num_questions_total, # Total including deep dive
                "role_specific_guidance": role_guidance["role"],
                "coding_guidance": role_guidance["code"],
                "problem_solving_guidance": role_guidance["solve"],
                "extra_hints_str": "Ensure questions are distinct and progressively probe deeper if appropriate.",
            }

            # Dynamically generate the structure for the question list in the prompt
            q_lines_for_template = ""
            for i in range(num_questions_total):
                q_index = i % len(q_types_list) # Cycle through base types
                # Assign a specific type, ensure last one is Project Deep Dive
                q_type = "[Project Deep Dive]" if i == config.NUM_QUESTIONS else q_types_list[q_index]
                qg_prompt_args[f"q_type_{i}"] = q_type
                q_lines_for_template += f"{i+1}. {q_type} ...\n" # Let LLM fill in the question text

            # Find the placeholder section in the template and replace it
            # Making the pattern more robust to find the start and end of the example list
            placeholder_pattern = re.compile(
                 r"(?:Here is the desired format:?\s*\n)?\s*1\.\s*\[.*?\]\s*\.\.\..*?\n\s*" + # Start of example list
                 str(num_questions_total) + r"\.\s*\[.*?\]\s*\.\.\.", # End of example list
                 re.DOTALL | re.IGNORECASE
            )

            if placeholder_pattern.search(prompt_templates.QUESTION_GENERATION_PROMPT_TEMPLATE):
                 modified_qg_template = placeholder_pattern.sub(
                      f"Here is the desired format:\n{q_lines_for_template.strip()}", # Replace with dynamic lines
                      prompt_templates.QUESTION_GENERATION_PROMPT_TEMPLATE,
                      count=1 # Replace only the first occurrence
                 )
                 logger.debug(f"[{self.interview_id}] Modified question generation template with dynamic types.")
            else:
                 logger.warning(f"[{self.interview_id}] Could not find placeholder pattern in question generation template. Using original template.")
                 modified_qg_template = prompt_templates.QUESTION_GENERATION_PROMPT_TEMPLATE
                 # Add the args anyway, they might be used elsewhere in the template
                 modified_qg_template += "\n\n# Question Types:\n" + q_lines_for_template

            # Format the final prompt
            try:
                 question_gen_prompt = modified_qg_template.format(**qg_prompt_args)
            except KeyError as fmt_err:
                 self._set_error_state(f"Missing key in question generation prompt template: {fmt_err}")
                 return

            # 6. Call LLM to Generate Questions
            logger.info(f"[{self.interview_id}] Generating ~{num_questions_total} interview questions via LLM ({config.INTERVIEWER_LLM_MODEL_NAME})...")
            # Use a higher token limit for generation as it includes context + questions
            generation_max_tokens = max(config.INTERVIEWER_MAX_TOKENS * 2, 1500)
            raw_questions_text = llm_interface.query_llm(
                question_gen_prompt, config.INTERVIEWER_LLM_MODEL_NAME,
                generation_max_tokens,
                config.INTERVIEWER_TEMPERATURE
            )

            if raw_questions_text is None or raw_questions_text.startswith("Error:"):
                error_detail = raw_questions_text if raw_questions_text else "LLM call failed."
                self._set_error_state(f"Failed to generate initial questions. Details: {error_detail}")
                return

            cleaned_questions_text = llm_interface.clean_llm_output(raw_questions_text)
            self.prepared_questions = parse_generated_questions(cleaned_questions_text)

            # Validate number of questions generated
            if not self.prepared_questions or len(self.prepared_questions) < config.NUM_QUESTIONS: # Check for at least the core number
                logger.error(f"[{self.interview_id}] Failed to parse sufficient questions (expected ~{num_questions_total}, found {len(self.prepared_questions)}). Raw: '{raw_questions_text[:150]}...' Cleaned: '{cleaned_questions_text[:150]}...'")
                # Attempt to use whatever was parsed if > 0? Or fail? Let's fail for consistency.
                self._set_error_state(f"Could not parse the generated questions (expected ~{num_questions_total}, found {len(self.prepared_questions)}). Check LLM output/parsing logic.")
                return

            # Trim excess if LLM generated too many
            self.prepared_questions = self.prepared_questions[:num_questions_total]
            logger.info(f"[{self.interview_id}] Successfully generated and parsed {len(self.prepared_questions)} questions.")
            logger.debug(f"[{self.interview_id}] Prepared Questions: {self.prepared_questions}")

            self.state = "READY"
            logger.info(f"[{self.interview_id}] Interview session initialized and ready.")

        except Exception as e:
            logger.exception(f"[{self.interview_id}] Unexpected error during session initialization: {e}")
            self._set_error_state(f"An unexpected error occurred during interview setup: {e}")

    def get_greeting(self):
        """Returns the initial greeting message and transitions state."""
        if self.state != "READY":
            logger.warning(f"[{self.interview_id}] Attempted to get greeting but state is {self.state}")
            return self.last_ai_message or "Interview is not ready."

        greeting_text = f"Hello {config.CANDIDATE_NAME}. I'm {config.INTERVIEWER_AI_NAME}, and I'll be conducting your interview today for the {self.role_title} position at {config.COMPANY_NAME}. We'll go through about {len(self.prepared_questions)} questions covering technical concepts and your past experience. Please respond verbally when prompted. Are you ready to begin?"

        logger.info(f"[{self.interview_id}] Sending greeting to player and frontend.")
        if not send_text_to_player(greeting_text):
             # If sending fails, maybe don't proceed? Or log warning and proceed?
             logger.warning(f"[{self.interview_id}] Failed to send greeting to NeuroSync Player. Continuing frontend flow.")

        self.last_ai_message = greeting_text
        self.conversation_history.append({"speaker": config.INTERVIEWER_AI_NAME, "text": greeting_text})
        self.state = "AWAITING_RESPONSE" # Wait for user confirmation / first response
        self.current_turn_number = 0 # Turn 0 is greeting, turn 1 starts with first real question
        # No question context set yet for the greeting
        self.last_question_context = {
             "question": "Initial Greeting / Ready Check",
             "is_prepared": False,
             "prepared_index": None,
             "detection_method": "Greeting",
             "turn": 0
         }
        return greeting_text

    def get_next_ai_turn(self):
        """
        Generates the AI interviewer's next response or question.
        This should be called *after* processing the candidate's response (or initially after greeting confirmation).
        """
        if self.state not in ["ASKING", "IN_PROGRESS"]: # Should be triggered internally or after response
            # Allow calling if state is AWAITING_RESPONSE and history suggests user confirmed ready
             if self.state == "AWAITING_RESPONSE" and len(self.conversation_history) > 1 and self.conversation_history[-1]['speaker'] == config.CANDIDATE_NAME:
                 logger.info(f"[{self.interview_id}] Proceeding to first question after user confirmation.")
                 self.state = "ASKING" # Set state to indicate AI is about to ask
             else:
                 logger.warning(f"[{self.interview_id}] Attempted to get next AI turn but state is {self.state}. Expected ASKING or IN_PROGRESS.")
                 return self.last_ai_message or "Interview state invalid for generating next AI turn."

        turn = self.current_turn_number + 1 # The turn number AI is about to start
        logger.info(f"[{self.interview_id}] --- Starting AI Turn {turn} ---")
        self.state = "ASKING" # Ensure state reflects AI is thinking/asking

        # Check if we should conclude the interview
        # If all prepared questions asked AND it's beyond the expected number of turns
        asked_count = len(self.asked_questions_indices)
        if asked_count >= len(self.prepared_questions) and turn > len(self.prepared_questions):
             # Make sure the candidate actually responded to the last question
             if not self.conversation_history or self.conversation_history[-1]['speaker'] == config.CANDIDATE_NAME:
                  logger.info(f"[{self.interview_id}] All prepared questions asked ({asked_count}/{len(self.prepared_questions)}). Preparing closing remarks.")
                  closing_text = f"Alright, that concludes our planned questions. Thank you very much for your time and for sharing your experience, {config.CANDIDATE_NAME}. We'll evaluate the session and be in touch regarding the next steps."
                  send_text_to_player(closing_text)
                  self.last_ai_message = closing_text
                  self.conversation_history.append({"speaker": config.INTERVIEWER_AI_NAME, "text": closing_text})
                  self.state = "FINISHED" # Move to finished state, evaluation will follow
                  return closing_text
             else:
                  # AI spoke last, possibly a follow-up after the last question. Let's allow one more cycle or end here.
                  logger.info(f"[{self.interview_id}] All prepared questions asked, AI spoke last. Ending interview.")
                  # Use previous closing message if it exists, otherwise generate a short one.
                  if self.last_ai_message and ("concludes" in self.last_ai_message or "thank you" in self.last_ai_message.lower()):
                      # Re-send or just return existing message? Let's return it.
                      # send_text_to_player(self.last_ai_message) # Resend if needed
                      self.state = "FINISHED"
                      return self.last_ai_message
                  else:
                      closing_text = f"Thank you again, {config.CANDIDATE_NAME}. That's all the questions I have for now. We will be in touch."
                      send_text_to_player(closing_text)
                      self.last_ai_message = closing_text
                      self.conversation_history.append({"speaker": config.INTERVIEWER_AI_NAME, "text": closing_text})
                      self.state = "FINISHED"
                      return closing_text

        # --- Prepare Prompt for Conversational Turn ---
        # Format conversation history for the prompt
        history_str = self._format_conversation_history(max_turns=6) # Limit context window
        # Identify remaining prepared questions
        remaining_indices = [i for i in range(len(self.prepared_questions)) if i not in self.asked_questions_indices]
        asked_str = ", ".join(str(i+1) for i in sorted(list(self.asked_questions_indices))) or "None yet"
        remaining_str = ", ".join(str(i+1) for i in remaining_indices) or "None (proceed with follow-ups or conclude)"

        # Prepare prompt arguments
        conv_prompt_args = {
            "interviewer_name": config.INTERVIEWER_AI_NAME,
            "company_name": config.COMPANY_NAME,
            "role_title": self.role_title,
            "candidate_name": config.CANDIDATE_NAME,
            "resume_summary": self.resume_summary,
            "jd_summary": self.jd_summary,
            "project_details": self.project_details,
            "focus_topics_str": ', '.join(self.focus_topics),
            "prepared_questions_numbered": "\n".join(f"{i+1}. {q}" for i, q in enumerate(self.prepared_questions)),
            "asked_questions_str": asked_str,
            "remaining_questions_str": remaining_str,
            "conversation_history": history_str,
            "current_turn_number": turn,
            "total_questions_planned": len(self.prepared_questions)
        }
        try:
            interview_turn_prompt = prompt_templates.CONVERSATIONAL_INTERVIEW_PROMPT_TEMPLATE.format(**conv_prompt_args)
        except KeyError as fmt_err:
            self._set_error_state(f"Missing key in conversational prompt template: {fmt_err}")
            return self.last_ai_message # Return previous message or error

        # Call LLM for AI response
        logger.debug(f"[{self.interview_id}] Sending prompt to interviewer LLM (Turn {turn}). History length: {len(history_str)} chars.")
        ai_response_raw = llm_interface.query_llm(
            interview_turn_prompt, config.INTERVIEWER_LLM_MODEL_NAME,
            config.INTERVIEWER_MAX_TOKENS, config.INTERVIEWER_TEMPERATURE
        )
        ai_response = llm_interface.clean_llm_output(ai_response_raw)

        if ai_response is None or ai_response.startswith("Error:"):
            error_detail = ai_response if ai_response else "LLM call failed."
            # Don't set error state here, just return an apology message? Or should it halt?
            # Let's try to recover by returning an apology and potentially allowing retry?
            logger.error(f"[{self.interview_id}] Interviewer LLM failed on turn {turn}: {error_detail}")
            error_text = f"Apologies, I encountered a temporary issue generating my response. Could you perhaps repeat your last point or should we try the next question?"
            # Don't change main state, keep it as ASKING? Frontend might retry getAiMessage.
            # self.state = "ERROR" # Avoid halting unless it's persistent
            self.last_ai_message = error_text # Update message for frontend display
            send_text_to_player(error_text) # Send apology to player
            return error_text # Return apology to frontend

        # --- Detect if AI asked a Prepared Question ---
        identified_prepared_index = -1
        current_question_text_for_eval = ai_response # Default: use full AI response as context
        detected_method = "Follow-up or Transition"

        if remaining_indices:
            # Use a more robust matching (e.g., simple keyword overlap + structure)
            best_match_index, highest_overlap = self._find_best_question_match(ai_response, remaining_indices)

            if best_match_index != -1:
                 identified_prepared_index = best_match_index
                 # Use the canonical prepared question text for evaluation context
                 current_question_text_for_eval = self.prepared_questions[identified_prepared_index]
                 detected_method = f"Prepared Q Match (Overlap: {highest_overlap:.1%})"
                 logger.info(f"[{self.interview_id}] Detected prepared question {identified_prepared_index + 1}: '{current_question_text_for_eval[:50]}...'. Method: {detected_method}")
                 # Mark as asked *only when detected*
                 self.asked_questions_indices.add(identified_prepared_index)
            else:
                 logger.info(f"[{self.interview_id}] AI response didn't strongly match remaining prepared questions ({remaining_indices}). Assuming follow-up/transition.")
                 # If no match, the current_question_text_for_eval remains the full AI response
                 # Consider if we should try to extract *just* the question part from ai_response?
                 # Simple approach: if ends with '?', take the last sentence.
                 sentences = re.split(r'(?<=[.!?])\s+', ai_response.strip())
                 if sentences and sentences[-1].endswith('?') and len(sentences[-1]) > 15:
                      current_question_text_for_eval = sentences[-1]
                      logger.debug(f"[{self.interview_id}] Using last sentence as question context: '{current_question_text_for_eval[:60]}...'")

        else:
             logger.info(f"[{self.interview_id}] No prepared questions remaining. AI response is likely a follow-up or closing.")
             # Again, try to extract the question part if relevant
             sentences = re.split(r'(?<=[.!?])\s+', ai_response.strip())
             if sentences and sentences[-1].endswith('?') and len(sentences[-1]) > 15:
                  current_question_text_for_eval = sentences[-1]
                  logger.debug(f"[{self.interview_id}] Using last sentence as follow-up question context: '{current_question_text_for_eval[:60]}...'")

        # Store AI response in history
        self.conversation_history.append({"speaker": config.INTERVIEWER_AI_NAME, "text": ai_response})
        self.last_ai_message = ai_response # Store the actual AI message sent

        # Store context about the question that was just asked (for linking the candidate's *next* response)
        self._set_last_question_for_eval(current_question_text_for_eval, identified_prepared_index, detected_method, turn)

        # Send response to NeuroSync Player
        if not send_text_to_player(ai_response):
             logger.warning(f"[{self.interview_id}] Failed to send AI turn {turn} message to NeuroSync Player.")

        # Transition state to wait for the candidate's response
        self.state = "AWAITING_RESPONSE"
        logger.info(f"[{self.interview_id}] AI Turn {turn} complete. State -> AWAITING_RESPONSE.")
        return ai_response # Return the text to be displayed on the frontend

    def _find_best_question_match(self, ai_response, remaining_indices):
        """Helper to find the best matching prepared question in the AI response."""
        ai_response_lower = ai_response.lower()
        best_match_index = -1
        highest_overlap = 0.0
        # Use simple word overlap of non-stopwords (can be improved)
        try:
             from nltk.corpus import stopwords
             stop_words = set(stopwords.words('english'))
        except LookupError:
             logger.warning("NLTK stopwords not found. Download them ('nltk.download(\"stopwords\")'). Proceeding without stopword removal for matching.")
             stop_words = set()
        except ImportError:
             logger.warning("NLTK not installed. Proceeding without stopword removal for matching.")
             stop_words = set()

        # Consider only longer words after removing punctuation
        ai_words = set(w for w in re.findall(r'\b\w{3,}\b', ai_response_lower) if w not in stop_words)
        if not ai_words: return -1, 0.0 # Cannot match if AI response has no usable words

        for i in remaining_indices:
            q_text = self.prepared_questions[i]
            q_text_lower = q_text.lower()
            q_words = set(w for w in re.findall(r'\b\w{3,}\b', q_text_lower) if w not in stop_words)
            if not q_words: continue

            common_words = q_words.intersection(ai_words)
            # Calculate Jaccard index or simple overlap relative to question length
            # overlap_ratio = len(common_words) / len(q_words.union(ai_words)) # Jaccard
            overlap_ratio = len(common_words) / len(q_words) if len(q_words) > 0 else 0 # Simple overlap

            # Threshold and find best match
            # Requires a reasonably high overlap (e.g., > 50-60%) AND maybe keyword check?
            # Or check if AI response *contains* a large chunk of the question?
            # Let's stick to overlap ratio for now. Adjust threshold (0.55 - 0.65 might be reasonable)
            match_threshold = 0.60
            if overlap_ratio > highest_overlap and overlap_ratio >= match_threshold:
                highest_overlap = overlap_ratio
                best_match_index = i

        return best_match_index, highest_overlap

    def _set_last_question_for_eval(self, question_text, index, method, turn_asked):
         """Stores the context for the candidate's upcoming answer."""
         self.last_question_context = {
              "question": question_text,
              "is_prepared": index != -1,
              "prepared_index": index + 1 if index != -1 else None, # Use 1-based index for reporting
              "detection_method": method,
              "turn": turn_asked # The turn number when the AI *asked* this question
         }
         logger.debug(f"[{self.interview_id}] Set question context for upcoming response (AI Turn {turn_asked}): Prepared={self.last_question_context['is_prepared']}, Index={self.last_question_context['prepared_index']}, Text='{question_text[:60]}...'")


    def _format_conversation_history(self, max_turns=8):
        """Formats the recent history list into a string for the LLM prompt."""
        if not self.conversation_history: return "The conversation has not started yet."
        formatted = ""
        # Get the last N turns (each turn ideally has AI + Candidate = 2 entries, but handle variation)
        # Limit by number of entries to avoid overly long history context
        max_entries = max_turns * 2
        recent_history = self.conversation_history[-max_entries:]
        for entry in recent_history:
            speaker = entry.get('speaker', 'Unknown')
            text = entry.get('text', '[No text provided]')
            # Truncate long responses in history to keep prompt focused
            text_snippet = (text[:200] + '...') if len(text) > 200 else text
            formatted += f"**{speaker}:** {text_snippet}\n\n"
        return formatted.strip()

    def process_candidate_response(self, audio_file_path):
        """Processes the uploaded candidate audio response."""
        if self.state != "AWAITING_RESPONSE":
            # Allow processing if state is ERROR? Maybe not.
            logger.warning(f"[{self.interview_id}] Received candidate response but state is {self.state}. Expected AWAITING_RESPONSE.")
            return {"status": "error", "message": f"Cannot process response now, current state is {self.state}."}

        # This response corresponds to the question asked in the *previous* AI turn.
        # The turn number associated with this Q&A pair is the turn number when the question was asked.
        qna_turn_number = self.last_question_context.get('turn', self.current_turn_number) # Use context if available

        logger.info(f"[{self.interview_id}] Processing candidate response for Q asked in turn {qna_turn_number} from: {os.path.basename(audio_file_path)}")
        self.state = "IN_PROGRESS" # Indicate processing is happening

        # 1. Transcribe Audio using STT
        candidate_response_text, stt_error = audio_utils.transcribe_audio_file_google(audio_file_path)

        # Handle STT Outcomes
        if stt_error:
            logger.error(f"[{self.interview_id}] STT failed for turn {qna_turn_number}: {stt_error}")
            # Decide how to represent this - use error message or a placeholder?
            candidate_response_text = f"[STT Error: {stt_error}]"
            stt_success = False
        elif candidate_response_text is None:
             # This case should ideally not happen if transcribe_audio_file_google returns error message or "[No speech...]"
             logger.error(f"[{self.interview_id}] STT returned None unexpectedly for turn {qna_turn_number}")
             candidate_response_text = "[STT Error: Transcription failed silently]"
             stt_success = False
             stt_error = "Transcription returned None" # Synthesize error message
        elif candidate_response_text == "[Audio detected - No speech recognized]":
             logger.warning(f"[{self.interview_id}] No speech detected by STT for turn {qna_turn_number}.")
             stt_success = True # STT worked, just no speech
        else:
            logger.info(f"[{self.interview_id}] Turn {qna_turn_number} Transcription: '{candidate_response_text[:100]}...'")
            stt_success = True # Transcription successful

        # Add transcription to conversation history immediately
        self.conversation_history.append({"speaker": config.CANDIDATE_NAME, "text": candidate_response_text})

        # 2. Call Emotion Analysis API (if STT was successful and yielded speech)
        confidence_results = {'score': None, 'rating': "N/A", 'primary_emotion': "N/A", 'error': True, 'message': 'Analysis not performed'}
        if stt_success and candidate_response_text != "[Audio detected - No speech recognized]":
            logger.info(f"[{self.interview_id}] Calling Emotion Analysis API ({config.EMOTION_API_ENDPOINT}) for turn {qna_turn_number} audio: {os.path.basename(audio_file_path)}")
            abs_audio_path = os.path.abspath(audio_file_path) # Ensure absolute path
            api_payload = {'audio_path': abs_audio_path}
            try:
                # Increased timeout for potentially longer analysis
                api_response = requests.post(config.EMOTION_API_ENDPOINT, json=api_payload, timeout=60)
                api_response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
                response_data = api_response.json()
                # Check for application-level error within the JSON response
                if response_data.get('error'):
                    confidence_results['message'] = response_data.get('message', 'Emotion API reported an analysis error')
                    logger.warning(f"[{self.interview_id}] Emotion API Error (Turn {qna_turn_number}): {confidence_results['message']}")
                else:
                    confidence_results = response_data # Use the successful result
                    confidence_results['error'] = False # Explicitly mark as success
                    logger.info(f"[{self.interview_id}] Emotion API Analysis successful for turn {qna_turn_number}. Score: {confidence_results.get('score')}")
                # Ensure essential keys exist even on error reported by API
                confidence_results.setdefault('score', None)
                confidence_results.setdefault('rating', 'N/A')
                confidence_results.setdefault('primary_emotion', 'N/A')

            except requests.exceptions.ConnectionError as conn_err:
                confidence_results['message'] = f'Emotion API Connection Error: {conn_err}'
                logger.error(f"[{self.interview_id}] {confidence_results['message']}")
            except requests.exceptions.Timeout:
                confidence_results['message'] = 'Emotion API Timeout'
                logger.error(f"[{self.interview_id}] {confidence_results['message']}")
            except requests.exceptions.RequestException as req_err:
                 status_code = getattr(req_err.response, 'status_code', 'N/A')
                 response_text = getattr(req_err.response, 'text', 'N/A')[:200]
                 confidence_results['message'] = f'Emotion API Request Error: Status {status_code}. Response: {response_text}'
                 logger.error(f"[{self.interview_id}] {confidence_results['message']}", exc_info=True)
            except json.JSONDecodeError:
                 confidence_results['message'] = 'Emotion API Invalid JSON Response'
                 logger.error(f"[{self.interview_id}] {confidence_results['message']}")
            except Exception as api_call_err:
                 confidence_results['message'] = f'Unexpected error calling Emotion API: {api_call_err}'
                 logger.error(f"[{self.interview_id}] {confidence_results['message']}", exc_info=True)
        elif not stt_success:
             confidence_results['message'] = f'Skipped due to STT Error: {stt_error}'
             logger.info(f"[{self.interview_id}] Skipping emotion analysis for turn {qna_turn_number} due to STT error.")
        else: # No speech detected case
             confidence_results['message'] = 'Skipped (No speech detected)'
             confidence_results['error'] = False # Not an API error, just skipped
             logger.info(f"[{self.interview_id}] Skipping emotion analysis for turn {qna_turn_number} (No speech detected).")


        # 3. Store Turn Data for Evaluation and Report
        # Retrieve the question context saved when the AI asked the question
        last_q_context = self.last_question_context
        if not last_q_context or last_q_context.get('turn') != qna_turn_number:
             logger.warning(f"[{self.interview_id}] Mismatch between QnA turn ({qna_turn_number}) and last question context turn ({last_q_context.get('turn')}). Using fallback question context.")
             # Fallback: try to find the last message from the AI in history
             ai_messages = [h['text'] for h in self.conversation_history if h['speaker'] == config.INTERVIEWER_AI_NAME]
             question_for_qna = ai_messages[-1] if ai_messages else "Unknown Question (Context Mismatch)"
             is_prepared = False
             prep_q_idx = None
             detect_method = "Context Mismatch Fallback"
        else:
             question_for_qna = last_q_context['question']
             is_prepared = last_q_context['is_prepared']
             prep_q_idx = last_q_context['prepared_index']
             detect_method = last_q_context['detection_method']

        qna_data = {
            "question_turn": qna_turn_number,
            "question": question_for_qna,
            "response": candidate_response_text, # The transcribed text or error message
            "is_prepared_question": is_prepared,
            "prepared_question_index": prep_q_idx,
            "detection_method": detect_method,
            "stt_success": stt_success, # Boolean indicating if STT worked
            "stt_error_message": stt_error, # Specific error message if stt_success is False
            # --- Confidence Results ---
            "confidence_score": confidence_results.get('score'),
            "confidence_rating": confidence_results.get('rating', 'N/A'),
            "primary_emotion": confidence_results.get('primary_emotion', 'N/A'),
            "confidence_analysis_error": confidence_results.get('error', True), # True if API call failed OR API reported error
            "confidence_message": confidence_results.get('message', 'Analysis not performed'),
            # --- Evaluation Results (Filled later) ---
            "evaluation": None,
            "score": None,
            "score_justification": None,
        }
        self.interview_qna.append(qna_data)

        # Increment the main turn number counter AFTER processing the response
        self.current_turn_number = qna_turn_number # Align counter with the completed turn

        # Set state ready for the AI's next turn
        self.state = "ASKING" # Ready for get_next_ai_turn() to be called
        logger.info(f"[{self.interview_id}] Finished processing candidate response for QnA turn {qna_turn_number}. State -> ASKING.")
        return {"status": "success", "message": "Response processed."}

    def perform_final_evaluation(self):
        """Evaluates all recorded text responses using the evaluator LLM."""
        if self.state not in ["FINISHED", "EVALUATING"]: # Can only evaluate when interview flow is done
             logger.warning(f"[{self.interview_id}] Cannot evaluate, interview state is {self.state}. Must be FINISHED.")
             return False
        if self.evaluation_complete:
             logger.info(f"[{self.interview_id}] Evaluation already performed.")
             return True

        logger.info(f"[{self.interview_id}] Starting final evaluation of {len(self.interview_qna)} recorded QnA pairs...")
        self.state = "EVALUATING"
        evaluation_errors = 0

        for i, item in enumerate(self.interview_qna):
            q_text = item["question"]
            c_response_text = item["response"]
            turn = item["question_turn"]

            # Skip evaluation if STT failed or no meaningful response was captured
            if not item["stt_success"] or c_response_text == "[Audio detected - No speech recognized]":
                 skip_reason = item['stt_error_message'] or 'No speech detected'
                 logger.warning(f"[{self.interview_id}] Skipping text evaluation for turn {turn} due to: {skip_reason}")
                 item["evaluation"] = f"Evaluation skipped ({skip_reason})"
                 item["score"] = None
                 item["score_justification"] = "N/A"
                 continue # Move to the next item

            logger.info(f"[{self.interview_id}] Evaluating response text for turn {turn} ({i+1}/{len(self.interview_qna)})...")
            eval_prompt_args = {
                 "role_title": self.role_title,
                 "jd_summary": self.jd_summary,
                 "resume_summary": self.resume_summary,
                 "interview_question": q_text,
                 "candidate_response": c_response_text
            }
            try:
                evaluation_prompt = prompt_templates.EVALUATION_PROMPT_TEMPLATE.format(**eval_prompt_args)
            except KeyError as fmt_err:
                 logger.error(f"[{self.interview_id}] Skipping evaluation for turn {turn}: Missing key in evaluation prompt template: {fmt_err}")
                 item["evaluation"] = f"Evaluation Error: Prompt template key error ({fmt_err})"
                 item["score"] = None
                 item["score_justification"] = "N/A"
                 evaluation_errors += 1
                 continue

            evaluation_raw = llm_interface.query_llm(
                 evaluation_prompt, config.EVALUATOR_LLM_MODEL_NAME,
                 config.EVALUATOR_MAX_TOKENS, config.EVALUATOR_TEMPERATURE
            )
            evaluation = llm_interface.clean_llm_output(evaluation_raw, is_evaluation=True)

            if evaluation is None or evaluation.startswith("Error:"):
                 error_detail = evaluation if evaluation else "LLM call failed."
                 logger.error(f"[{self.interview_id}] Evaluator LLM failed for turn {turn}: {error_detail}")
                 item["evaluation"] = f"Evaluation Error: {error_detail}"
                 item["score"] = None
                 item["score_justification"] = "N/A"
                 evaluation_errors += 1
            else:
                 item["evaluation"] = evaluation
                 # Parse score and justification from the evaluation text
                 # Making regex more robust to variations (e.g., "Score: 4/5", "Score (1-5): 3")
                 score_match = re.search(r"Overall Score\s*(?:\(1-5\)|out of 5)?\s*[:\-]?\s*([1-5])(?:/\s*5)?", evaluation, re.IGNORECASE)
                 just_match = re.search(r"Justification\s*[:\-]?\s*(.*)", evaluation, re.IGNORECASE | re.DOTALL)

                 if score_match:
                      item["score"] = int(score_match.group(1))
                      logger.info(f"[{self.interview_id}] Parsed score for turn {turn}: {item['score']}")
                 else:
                      item["score"] = None
                      logger.warning(f"[{self.interview_id}] Could not parse score (1-5) for turn {turn}. Evaluation text: '{evaluation[:100]}...'")

                 if just_match:
                      # Clean up justification text: take everything after "Justification:" until the next potential section or end of string
                      just_text = just_match.group(1).strip()
                      # Stop justification if another common evaluation section header starts on a new line
                      # Be careful not to cut off multi-paragraph justifications
                      stop_patterns = [
                           r"\n\s*(?:Strengths|Areas for Improvement|Suggestions|Alignment|Technical Accuracy|Relevance|Overall Assessment)\s*:",
                           r"\n\s*[-*•\d]+\s+" # Stop if a new list item starts
                      ]
                      for pattern in stop_patterns:
                           match = re.search(pattern, just_text, re.IGNORECASE)
                           if match:
                                just_text = just_text[:match.start()].strip()
                      item["score_justification"] = just_text if just_text else "N/A"
                      logger.debug(f"[{self.interview_id}] Parsed justification for turn {turn}: {item['score_justification'][:60]}...")
                 else:
                      item["score_justification"] = "N/A"
                      logger.warning(f"[{self.interview_id}] Could not parse justification for turn {turn}. Evaluation text: '{evaluation[:100]}...'")

            # Optional delay to avoid hitting API rate limits
            time.sleep(0.5) # Adjust as needed

        self.evaluation_complete = True
        # Keep state as EVALUATING or FINISHED? Let's keep it FINISHED as evaluation is post-interview.
        self.state = "FINISHED"
        if evaluation_errors > 0:
             logger.warning(f"[{self.interview_id}] Evaluation phase completed with {evaluation_errors} errors.")
        else:
             logger.info(f"[{self.interview_id}] Evaluation phase completed successfully. Final state: {self.state}")
        return True

    def generate_report(self):
        """Generates the PDF report for this session."""
        if not self.evaluation_complete:
             logger.warning(f"[{self.interview_id}] Evaluation must be complete before generating report. Attempting evaluation now.")
             # Trigger evaluation if not done
             if not self.perform_final_evaluation():
                 logger.error(f"[{self.interview_id}] Evaluation failed, cannot generate report.")
                 self._set_error_state("Failed to perform final evaluation, report cannot be generated.")
                 return None # Indicate report cannot be generated

        if self.report_generated and self.report_path and os.path.exists(self.report_path):
             logger.info(f"[{self.interview_id}] Report already generated: {self.report_path}")
             return self.report_path

        logger.info(f"[{self.interview_id}] Generating PDF report...")
        try:
            # Ensure report directory exists
            os.makedirs(config.REPORT_FOLDER, exist_ok=True)
            # Sanitize interview ID for filename if needed, although UUIDs are usually safe
            safe_interview_id = re.sub(r'[^\w\-]+', '_', self.interview_id)
            report_filename = config.REPORT_FILENAME_TEMPLATE.format(interview_id=safe_interview_id)
            output_path = os.path.join(config.REPORT_FOLDER, report_filename)

            # Call the report generator function from the dedicated module
            report_generator.generate_pdf_report(
                evaluated_data=self.interview_qna,
                resume_text=self.resume_text_raw, # Pass raw texts for inclusion if needed
                jd_text=self.jd_text_raw,
                role_title=self.role_title,
                candidate_name=config.CANDIDATE_NAME, # Pass other relevant info
                interviewer_name=config.INTERVIEWER_AI_NAME,
                company_name=config.COMPANY_NAME,
                interview_id=self.interview_id,
                report_filename=output_path
            )
            self.report_generated = True
            self.report_path = output_path
            logger.info(f"[{self.interview_id}] PDF report generated successfully: {output_path}")
            return output_path
        except ImportError as imp_err:
             logger.error(f"[{self.interview_id}] Report generation library error (e.g., ReportLab): {imp_err}. Cannot generate PDF report.")
             self._set_error_state(f"Report generation library error: {imp_err}")
             return None
        except Exception as report_err:
             logger.error(f"[{self.interview_id}] Failed to generate PDF report: {report_err}", exc_info=True)
             self._set_error_state(f"Failed to generate PDF report: {report_err}")
             return None

    def get_state(self):
        """Returns the current state of the interview session."""
        # Return state and any error message if applicable
        return {"state": self.state, "error": self.error_message}

    def get_qna_data(self):
         """Returns the evaluated Q&A data."""
         if not self.evaluation_complete:
              logger.warning(f"[{self.interview_id}] Requesting QnA data before evaluation is complete.")
         return self.interview_qna

    def get_full_conversation(self):
         """Returns the full conversation history."""
         return self.conversation_history