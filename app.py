# # app.py
# print("--- app.py: Starting script execution ---") # DEBUG
# import os
# import uuid
# import logging
# from threading import Lock
# import traceback # For detailed error logging
# import time # Import time for start_interview elapsed time

# print("--- app.py: Basic imports done ---") # DEBUG

# from flask import Flask, request, jsonify, render_template, send_file, session as flask_session
# from werkzeug.utils import secure_filename
# import werkzeug.exceptions # Import explicitly for error handling

# print("--- app.py: Flask imports done ---") # DEBUG

# # Local Imports - Use relative imports if running as a package,
# # or ensure modules directory is in PYTHONPATH if running app.py directly
# try:
#     print("--- app.py: Attempting local imports ---") # DEBUG
#     import config
#     print("--- app.py: Imported config ---") # DEBUG
#     from modules import utils
#     print("--- app.py: Imported modules.utils ---") # DEBUG
#     from modules import llm_interface
#     print("--- app.py: Imported modules.llm_interface ---") # DEBUG
#     from modules import audio_utils
#     print("--- app.py: Imported modules.audio_utils ---") # DEBUG
#     from modules import report_generator
#     print("--- app.py: Imported modules.report_generator ---") # DEBUG
#     from modules.interview_logic import InterviewSession
#     print("--- app.py: Imported modules.interview_logic.InterviewSession ---") # DEBUG
#     print("--- app.py: Local imports successful ---") # DEBUG
# except ImportError as e:
#      print(f"--- app.py: FATAL ERROR importing local modules: {e}. Make sure modules are in the correct path. ---") # DEBUG
#      raise # Re-raise the error if imports fail critically

# # --- Basic Logging Setup ---
# print("--- app.py: Setting up logging ---") # DEBUG
# log_level = getattr(logging, config.LOG_LEVEL, logging.INFO)
# logging.basicConfig(level=log_level,
#                     format='%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s')
# # Reduce verbosity of libraries if needed
# logging.getLogger("werkzeug").setLevel(logging.WARNING)
# logging.getLogger("google").setLevel(logging.WARNING) # Gemini/STT libs
# logging.getLogger("urllib3").setLevel(logging.WARNING) # Often noisy via requests
# logging.getLogger("pdfminer").setLevel(logging.WARNING)
# logging.getLogger("PIL").setLevel(logging.WARNING) # pdfplumber dependency

# logger = logging.getLogger(__name__) # Logger for this application
# print(f"--- app.py: Logger '{__name__}' configured ---") # DEBUG

# # --- Flask App Initialization ---
# print("--- app.py: Initializing Flask app ---") # DEBUG
# app = Flask(__name__)
# print(f"--- app.py: Flask app object created: {app} ---") # DEBUG
# app.config['SECRET_KEY'] = config.SECRET_KEY
# app.config['UPLOAD_FOLDER'] = config.UPLOAD_FOLDER
# app.config['REPORT_FOLDER'] = config.REPORT_FOLDER
# app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024 # 32 MB
# print("--- app.py: Flask app configured ---") # DEBUG

# # Ensure upload and report directories exist
# try:
#     print("--- app.py: Creating upload/report directories (if needed) ---") # DEBUG
#     os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
#     os.makedirs(app.config['REPORT_FOLDER'], exist_ok=True)
#     logger.info(f"Upload folder: {app.config['UPLOAD_FOLDER']}")
#     logger.info(f"Report folder: {app.config['REPORT_FOLDER']}")
#     print("--- app.py: Directories ensured ---") # DEBUG
# except OSError as e:
#      logger.error(f"Error creating directories: {e}. Check permissions.")
#      print(f"--- app.py: FATAL ERROR creating directories: {e} ---") # DEBUG
#      # Depending on severity, might want to exit
#      import sys; sys.exit(1) # Exit if dirs can't be created

# # --- In-Memory Session Storage ---
# print("--- app.py: Setting up session storage ---") # DEBUG
# interview_sessions = {}
# session_lock = Lock()
# print("--- app.py: Session storage ready ---") # DEBUG

# # --- Initialize External Clients & Resources ---
# # We move initialization here BEFORE app.run to catch errors earlier
# # The @app.before_request might not run if app.run fails to start.
# initialization_complete = False
# try:
#     print("--- app.py: Performing pre-run initializations... ---") # DEBUG
#     logger.info("Performing pre-run initializations...")

#     # Initialize NLTK data
#     print("--- app.py: Initializing NLTK... ---") # DEBUG
#     utils.initialize_nltk()
#     print("--- app.py: NLTK initialized (or skipped). ---") # DEBUG

#     # Initialize STT Client
#     print("--- app.py: Initializing STT Client... ---") # DEBUG
#     if not audio_utils.STT_CLIENT:
#          stt_initialized = audio_utils.initialize_stt_client()
#          if not stt_initialized:
#               # Log warning but don't necessarily stop server? Depends on if STT is critical path for *any* function.
#               logger.warning("STT Client failed to initialize during pre-run. Transcription will be unavailable.")
#          else:
#               logger.info("STT Client initialized successfully during pre-run.")
#     else:
#           logger.info("STT Client already initialized.")
#     print("--- app.py: STT Client initialization attempted. ---") # DEBUG

#     # Initialize RAG/Embedding Model
#     print("--- app.py: Initializing RAG... ---") # DEBUG
#     utils.initialize_rag() # This handles checks for enablement/dependencies internally
#     logger.info("RAG system initialization attempted during pre-run.")
#     print("--- app.py: RAG initialization attempted. ---") # DEBUG

#     # Initialize LLMs? Optional, they lazy load anyway.
#     # print("--- app.py: Initializing LLMs... ---") # DEBUG
#     # llm_interface.initialize_llms()
#     # print("--- app.py: LLMs initialization attempted. ---") # DEBUG

#     initialization_complete = True
#     print("--- app.py: Pre-run initializations complete. ---") # DEBUG

# except Exception as init_err:
#      logger.exception(f"FATAL ERROR during pre-run initialization: {init_err}")
#      print(f"--- app.py: FATAL ERROR during pre-run initialization: {init_err} ---") # DEBUG
#      # Exit if critical initializations fail
#      import sys; sys.exit(1)


# # --- Utility Functions ---
# def allowed_file(filename, allowed_extensions):
#     return '.' in filename and \
#            filename.rsplit('.', 1)[1].lower() in allowed_extensions

# def get_session(interview_id) -> InterviewSession | None:
#      with session_lock:
#           session = interview_sessions.get(interview_id)
#           # Reduced logging noise here
#           # if not session: logger.warning(f"Session {interview_id} not found in memory.")
#           return session

# def store_session(interview_id, session_obj):
#      with session_lock:
#           interview_sessions[interview_id] = session_obj
#           logger.info(f"Stored session {interview_id}. Active sessions: {len(interview_sessions)}")

# def remove_session(interview_id):
#      with session_lock:
#           if interview_id in interview_sessions:
#                del interview_sessions[interview_id]
#                logger.info(f"Removed session {interview_id}. Active sessions: {len(interview_sessions)}")
#           # else: logger.warning(f"Attempted to remove non-existent session {interview_id}.")
# print("--- app.py: Utility functions defined ---") # DEBUG

# # --- Routes ---
# @app.route('/')
# def index():
#     print("--- app.py: Route / accessed ---") # DEBUG
#     return render_template('index.html')

# @app.route('/start-interview', methods=['POST'])
# def start_interview():
#     start_time = time.time()
#     # ... (rest of the route function - keep as is) ...
#     # No changes needed inside the route for this debug step
#     logger.info("Received request to start new interview.")
#     try:
#         if 'resume' not in request.files:
#             logger.warning("Resume file part missing in request.")
#             return jsonify({"error": "Resume file is required."}), 400
#         resume_file = request.files['resume']
#         jd_text = request.form.get('job_description', '').strip()

#         if not resume_file or resume_file.filename == '':
#             logger.warning("No resume file selected.")
#             return jsonify({"error": "No resume file selected."}), 400
#         if not jd_text:
#             logger.warning("Job description text is empty.")
#             return jsonify({"error": "Job description cannot be empty."}), 400

#         if not allowed_file(resume_file.filename, {'pdf'}):
#             logger.warning(f"Invalid file type uploaded: {resume_file.filename}")
#             return jsonify({"error": "Invalid file type. Please upload a PDF resume."}), 400

#         temp_filename = f"{uuid.uuid4()}_{secure_filename(resume_file.filename)}"
#         temp_resume_path = os.path.join(app.config['UPLOAD_FOLDER'], temp_filename)

#         try:
#             logger.debug(f"Saving temporary resume to: {temp_resume_path}")
#             resume_file.save(temp_resume_path)
#             logger.debug("Extracting text from resume PDF...")
#             resume_text = utils.extract_text_from_pdf(temp_resume_path)
#             if resume_text is None or not resume_text.strip():
#                  logger.error(f"Failed to extract text from resume: {temp_resume_path}")
#                  if os.path.exists(temp_resume_path): os.remove(temp_resume_path)
#                  return jsonify({"error": "Failed to extract text from the uploaded resume PDF. It might be image-based or corrupted."}), 400
#             logger.info(f"Resume text extracted (length: {len(resume_text)} chars).")

#         except Exception as pdf_err:
#             logger.error(f"Error processing resume PDF: {pdf_err}", exc_info=True)
#             if os.path.exists(temp_resume_path): os.remove(temp_resume_path)
#             error_msg = f"Failed to process resume PDF: {pdf_err}"
#             if isinstance(pdf_err, ImportError):
#                  error_msg = "PDF processing library (pdfplumber) not installed or accessible."
#             return jsonify({"error": error_msg}), 500
#         finally:
#             if os.path.exists(temp_resume_path):
#                 try: os.remove(temp_resume_path)
#                 except OSError as e: logger.warning(f"Could not remove temp resume file {temp_resume_path}: {e}")

#         interview_id = str(uuid.uuid4())
#         logger.info(f"[{interview_id}] Generated new interview ID.")
#         old_interview_id = flask_session.pop('interview_id', None)
#         if old_interview_id: remove_session(old_interview_id)

#         logger.info(f"[{interview_id}] Creating InterviewSession object...")
#         session_obj = InterviewSession(interview_id, resume_text, jd_text)
#         init_state_info = session_obj.get_state()

#         if init_state_info["state"] == "ERROR":
#             logger.error(f"[{interview_id}] Session initialization failed. Error: {init_state_info['error']}")
#             return jsonify({"error": f"Interview initialization failed: {init_state_info['error']}"}), 500

#         store_session(interview_id, session_obj)
#         flask_session['interview_id'] = interview_id
#         logger.debug(f"Stored interview_id {interview_id} in Flask session.")
#         elapsed_time = time.time() - start_time
#         logger.info(f"[{interview_id}] Interview setup completed in {elapsed_time:.2f} seconds.")
#         return jsonify({"interview_id": interview_id,"message": "Interview initialized successfully. Ready for greeting."}), 200

#     except Exception as e:
#         logger.exception("Unexpected error in /start-interview")
#         if isinstance(e, werkzeug.exceptions.RequestEntityTooLarge):
#               return jsonify({"error": f"File upload failed. The resume file may be too large (limit: {app.config['MAX_CONTENT_LENGTH'] // 1024 // 1024} MB)."}), 413
#         return jsonify({"error": f"An unexpected server error occurred during setup: {e}"}), 500

# # ... (other routes: /get-ai-message, /submit-response, /get-report - keep as is) ...
# @app.route('/get-ai-message', methods=['GET'])
# def get_ai_message():
#     # ... route code ...
#     interview_id = flask_session.get('interview_id')
#     if not interview_id: return jsonify({"error": "No active interview session found. Please start a new interview."}), 400
#     logger.info(f"[{interview_id}] Received request for next AI message.")
#     session_obj = get_session(interview_id)
#     if not session_obj:
#         flask_session.pop('interview_id', None)
#         return jsonify({"error": "Interview session not found or expired. Please start again."}), 404
#     try:
#         state_info = session_obj.get_state()
#         current_state = state_info["state"]
#         logger.debug(f"[{interview_id}] Current session state: {current_state}")
#         ai_message = None
#         response_status = 200
#         if current_state == "READY": ai_message = session_obj.get_greeting()
#         elif current_state == "ASKING": ai_message = session_obj.get_next_ai_turn()
#         elif current_state == "AWAITING_RESPONSE": ai_message = session_obj.last_ai_message
#         elif current_state in ["FINISHED", "EVALUATING"]: ai_message = session_obj.last_ai_message or "The interview has concluded."
#         elif current_state == "ERROR":
#              ai_message = state_info["error"] or "An unspecified error occurred in the interview session."
#              response_status = 500
#         else: ai_message = "Interview is currently processing, please wait..."
#         final_state_info = session_obj.get_state()
#         if final_state_info["state"] == "ERROR":
#             ai_message = final_state_info["error"] or "An error occurred while generating the AI message."
#             response_status = 500
#         logger.info(f"[{interview_id}] Sending AI message. Final state: {final_state_info['state']}")
#         return jsonify({"ai_message": ai_message, "status": final_state_info["state"]}), response_status
#     except Exception as e:
#         logger.exception(f"[{interview_id}] Unexpected error in /get-ai-message")
#         if session_obj and session_obj.get_state()["state"] != "ERROR":
#              session_obj._set_error_state(f"Server error during AI turn generation: {e}")
#         return jsonify({"error": f"An unexpected server error occurred: {e}", "status": "ERROR"}), 500

# @app.route('/submit-response', methods=['POST'])
# def submit_response():
#     # ... route code ...
#     interview_id = flask_session.get('interview_id')
#     if not interview_id: return jsonify({"error": "No active interview session found. Please start a new interview."}), 400
#     logger.info(f"[{interview_id}] Received request to submit response.")
#     session_obj = get_session(interview_id)
#     if not session_obj:
#         flask_session.pop('interview_id', None)
#         return jsonify({"error": "Interview session not found or expired. Please start again."}), 404
#     current_state = session_obj.get_state()["state"]
#     if current_state != "AWAITING_RESPONSE":
#          return jsonify({"error": f"Cannot submit response now, the system is not awaiting your answer (state: {current_state})."}), 409
#     if 'audio_data' not in request.files: return jsonify({"error": "Audio data blob is required."}), 400
#     audio_file = request.files['audio_data']
#     if not audio_file or audio_file.filename == '': return jsonify({"error": "No audio file selected/uploaded."}), 400
#     file_ext = ".wav"
#     if '.' in audio_file.filename:
#         ext_candidate = audio_file.filename.rsplit('.', 1)[1].lower()
#         if ext_candidate in ['wav', 'webm', 'ogg', 'mp3', 'flac']: file_ext = f".{ext_candidate}"
#     qna_turn_number = session_obj.last_question_context.get('turn', session_obj.current_turn_number)
#     filename = secure_filename(f"{interview_id}_turn_{qna_turn_number}_response{file_ext}")
#     temp_audio_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
#     result = {"status": "error", "message": "Audio processing did not complete."}
#     response_status = 500 # Default error status
#     try:
#         logger.debug(f"[{interview_id}] Saving temporary audio response for QnA turn {qna_turn_number} to: {temp_audio_path}")
#         audio_file.save(temp_audio_path)
#         logger.info(f"[{interview_id}] Audio file saved successfully (Size: {os.path.getsize(temp_audio_path)} bytes).")
#         logger.info(f"[{interview_id}] Processing candidate response via InterviewSession...")
#         result = session_obj.process_candidate_response(temp_audio_path)
#         logger.info(f"[{interview_id}] Response processing result: {result}")
#         response_status = 200 if result.get("status") == "success" else 500
#     except werkzeug.exceptions.RequestEntityTooLarge:
#          logger.warning(f"[{interview_id}] Audio upload failed: File too large.")
#          result = {"status": "error", "message": f"Audio file is too large (limit: {app.config['MAX_CONTENT_LENGTH'] // 1024 // 1024} MB)."}
#          response_status = 413
#     except Exception as e:
#         logger.exception(f"[{interview_id}] Error saving or processing audio response")
#         result = {"status": "error", "message": f"Server error processing audio: {e}"}
#         if os.path.exists(temp_audio_path): os.remove(temp_audio_path)
#         response_status = 500
#     finally:
#         if os.path.exists(temp_audio_path):
#             try: os.remove(temp_audio_path)
#             except OSError as e: logger.warning(f"[{interview_id}] Could not remove temp audio file {temp_audio_path}: {e}")

#     if result.get("status") == "success":
#         return jsonify({"status": "OK", "message": "Response received and processed."}), response_status
#     else:
#         return jsonify({"error": result.get("message", "Failed to process response.")}), response_status


# @app.route('/get-report', methods=['GET'])
# def get_report():
#     # ... route code ...
#     interview_id = flask_session.get('interview_id')
#     if not interview_id: return jsonify({"error": "No active interview session found to generate report."}), 400
#     logger.info(f"[{interview_id}] Received request to get report.")
#     session_obj = get_session(interview_id)
#     if not session_obj:
#         flask_session.pop('interview_id', None)
#         return jsonify({"error": "Interview session not found or expired."}), 404
#     current_state = session_obj.get_state()["state"]
#     if current_state not in ["FINISHED", "EVALUATING", "ERROR"]:
#          return jsonify({"error": f"Cannot generate report yet. Interview status: {current_state}."}), 409
#     if not session_obj.evaluation_complete and current_state != "ERROR":
#          logger.info(f"[{interview_id}] Evaluation not complete. Performing final evaluation before report generation.")
#          eval_success = session_obj.perform_final_evaluation()
#          if not eval_success: logger.error(f"[{interview_id}] Final evaluation failed. Report may be incomplete.")
#          else: logger.info(f"[{interview_id}] Final evaluation completed.")
#     logger.info(f"[{interview_id}] Attempting to generate report...")
#     report_path = session_obj.generate_report()
#     if report_path and os.path.exists(report_path):
#         logger.info(f"[{interview_id}] Sending report file: {report_path}")
#         try:
#             return send_file(report_path, as_attachment=True, download_name=os.path.basename(report_path), mimetype='application/pdf')
#         except Exception as send_err:
#              logger.exception(f"[{interview_id}] Error sending report file {report_path}")
#              return jsonify({"error": f"Could not send report file: {send_err}"}), 500
#     else:
#         logger.error(f"[{interview_id}] Report generation failed or file not found. Report path: {report_path}")
#         error_msg = session_obj.get_state().get("error", "Failed to generate or find the interview report.")
#         return jsonify({"error": error_msg}), 500

# print("--- app.py: Routes defined ---") # DEBUG

# # --- Error Handling ---
# @app.errorhandler(404)
# def not_found_error(error):
#      logger.warning(f"404 Not Found: {request.url}")
#      return jsonify({"error": "Not Found", "message": "The requested URL was not found on the server."}), 404

# @app.errorhandler(400)
# def bad_request_error(error):
#      error_desc = error.description if hasattr(error, 'description') else 'No description provided.'
#      logger.warning(f"400 Bad Request: {request.url} - {error_desc}")
#      return jsonify({"error": "Bad Request", "message": error_desc}), 400

# @app.errorhandler(413)
# def request_entity_too_large_error(error):
#      logger.warning(f"413 Request Entity Too Large: {request.url} - Content Length: {request.content_length}")
#      limit_mb = app.config['MAX_CONTENT_LENGTH'] // 1024 // 1024
#      return jsonify({"error": "Request Entity Too Large", "message": f"The uploaded file exceeds the maximum allowed size of {limit_mb} MB."}), 413

# # Keep the generic exception handler
# @app.errorhandler(Exception)
# def handle_exception(e):
#     error_id = uuid.uuid4()
#     tb_str = traceback.format_exc()
#     logger.error(f"Unhandled Exception (ID: {error_id}): {e}\n--- Traceback ---\n{tb_str}--- End Traceback ---")
#     # Always return generic error in non-debug mode
#     return jsonify({"error": "An unexpected server error occurred. Please check server logs.",
#                      "error_id": str(error_id)}), 500

# print("--- app.py: Error handlers defined ---") # DEBUG


#flask run --host=0.0.0.0 --port=5050

#./SignallingWebServer/platform_scripts/bash/start.sh
#http://localhost:5050



# app.py
print("--- app.py: Starting script execution ---")
import os
import uuid
import logging
import sys # For exit on init failure
from threading import Lock
import traceback
import datetime # Added for cleanup command
from datetime import timedelta # Added for cleanup command
import time # Added for start_interview timing

print("--- app.py: Basic imports done ---")

from flask import (
    Flask, request, jsonify, render_template, send_file, session as flask_session,
    redirect, url_for, flash # Added redirect, url_for, flash
)
from werkzeug.utils import secure_filename
import werkzeug.exceptions
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy # Import SQLAlchemy directly if needed
from flask_bcrypt import Bcrypt # Import Bcrypt directly if needed
from flask_login import LoginManager, login_required, current_user, login_user, logout_user
from flask_mail import Mail, Message
from flask_migrate import Migrate # Added for database migrations
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature
from email_validator import validate_email, EmailNotValidError

print("--- app.py: Flask imports done ---")

# --- Load Config First ---
try:
    import config
    print("--- app.py: Imported config ---")
except ImportError as e:
    print(f"--- app.py: FATAL ERROR importing config: {e}. Make sure config.py exists. ---")
    sys.exit(1) # Exit if config is missing

# --- Basic Logging Setup ---
print("--- app.py: Setting up logging ---")
log_level = getattr(logging, config.LOG_LEVEL, logging.INFO)
logging.basicConfig(level=log_level,
                    format='%(asctime)s [%(levelname)-5s] %(name)s:%(lineno)d - %(message)s',
                    handlers=[logging.StreamHandler(sys.stdout)]) # Ensure logs go to stdout/stderr

# Reduce verbosity of libraries if needed
logging.getLogger("werkzeug").setLevel(logging.WARNING)
logging.getLogger("google").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("pdfminer").setLevel(logging.WARNING)
logging.getLogger("PIL").setLevel(logging.WARNING)
logging.getLogger("matplotlib").setLevel(logging.WARNING) # Often noisy
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)


logger = logging.getLogger(__name__) # Logger for this application
print(f"--- app.py: Logger '{__name__}' configured ---")

# --- Local Module Imports (AFTER config and logging) ---
try:
    print("--- app.py: Attempting local module imports ---")
    from modules import utils, llm_interface, audio_utils, report_generator, prompt_templates # Combined imports
    from modules.interview_logic import InterviewSession
    from models import db, bcrypt, User, Report, PasswordReset # Import db, bcrypt and models
    from auth import auth_bp # Import the authentication blueprint
    print("--- app.py: Local module imports successful ---")
except ImportError as e:
     # Use logger now that it's configured
     logger.critical(f"FATAL ERROR importing local modules: {e}. Check paths and dependencies.", exc_info=True)
     sys.exit(1)

# --- Flask App Initialization & Config ---
print("--- app.py: Initializing Flask app ---")
app = Flask(__name__)
app.config.from_object('config') # Load config from config.py object
logger.info(f"Flask app created. Debug mode: {app.config.get('DEBUG')}")

# --- CORS Configuration ---
print("--- app.py: Configuring CORS ---")
CORS(app, supports_credentials=True, resources={
    # Adjust origins based on your frontend setup
    r"/*": {
        # Example: Allow frontend dev server and potentially deployed frontend
        "origins": ["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8080", "http://127.0.0.1:8080"]
    }
})
logger.info(f"CORS configured for specified origins.")

# --- Initialize Extensions ---
print("--- app.py: Initializing Flask extensions ---")
try:
    # Initialize DB with app context
    if not app.config.get('SQLALCHEMY_DATABASE_URI'):
        logger.critical("SQLALCHEMY_DATABASE_URI not set in config. Cannot initialize database.")
        sys.exit(1)
    db.init_app(app)
    bcrypt.init_app(app) # Initialize bcrypt
    migrate = Migrate(app, db) # Initialize Flask-Migrate
    mail = Mail(app)
    login_manager = LoginManager(app)
    login_manager.login_view = 'auth.login' # Route name for login page (blueprint.view_func)
    login_manager.login_message_category = 'info' # Flash message category

    print("--- app.py: Flask extensions initialized ---")
except Exception as ext_err:
    logger.critical(f"FATAL ERROR initializing Flask extensions: {ext_err}", exc_info=True)
    sys.exit(1)

# --- Flask-Login User Loader ---
@login_manager.user_loader
def load_user(user_id):
    """Loads user object for Flask-Login session management."""
    try:
        user = User.query.get(int(user_id))
        # logger.debug(f"Flask-Login loaded user: {user}")
        return user
    except Exception as e:
        logger.error(f"Error loading user {user_id} for Flask-Login: {e}", exc_info=True)
        return None

# --- Register Blueprints ---
app.register_blueprint(auth_bp, url_prefix='/auth')
logger.info("Registered 'auth' blueprint at /auth")


# --- Pre-run Initializations (Moved outside request context) ---
initialization_complete = False
try:
    logger.info("Performing pre-run initializations...")

    # Create upload/report directories
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['REPORT_FOLDER'], exist_ok=True)
    logger.info(f"Upload folder ensured: {app.config['UPLOAD_FOLDER']}")
    logger.info(f"Report folder ensured: {app.config['REPORT_FOLDER']}")

    # Initialize NLTK data (can take time on first run)
    logger.info("Initializing NLTK...")
    utils.initialize_nltk()
    logger.info("NLTK initialization attempted.")

    # Initialize Google STT Client
    logger.info("Initializing STT Client...")
    stt_initialized = audio_utils.initialize_stt_client()
    if not stt_initialized:
         logger.warning("STT Client failed to initialize. Transcription will be unavailable.")
    else:
         logger.info("STT Client initialized successfully.")

    # Initialize RAG (DB connection + Embedding Model)
    logger.info("Initializing RAG components...")
    utils.initialize_rag() # Handles checks for enablement/dependencies internally
    logger.info("RAG initialization attempted.")

    # Initialize LLMs (Optional - they lazy load)
    # logger.info("Initializing LLMs...")
    # llm_interface.initialize_llms()
    # logger.info("LLMs initialization attempted.")

    initialization_complete = True
    logger.info("Pre-run initializations complete.")

except Exception as init_err:
     logger.critical(f"FATAL ERROR during pre-run initialization: {init_err}", exc_info=True)
     sys.exit(1) # Exit if critical initializations fail

# --- In-Memory Session Storage (for interviews) ---
interview_sessions = {} # Stores active InterviewSession objects
session_lock = Lock() # Protects access to interview_sessions dict
logger.info("In-memory interview session storage ready.")

# --- Utility Functions for Interview Sessions ---
def get_session(interview_id) -> InterviewSession | None:
     with session_lock:
          return interview_sessions.get(interview_id)

def store_session(interview_id, session_obj):
     with session_lock:
          interview_sessions[interview_id] = session_obj
          logger.info(f"Stored interview session {interview_id}. Active sessions: {len(interview_sessions)}")

def remove_session(interview_id):
     with session_lock:
          if interview_id in interview_sessions:
               del interview_sessions[interview_id]
               logger.info(f"Removed interview session {interview_id}. Active sessions: {len(interview_sessions)}")

# --- Routes ---

# Redirect base URL to login or interview page
@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('interview_page'))
    else:
        return redirect(url_for('auth.login'))

# Main Interview Page (Protected)
@app.route('/interview')
@login_required
def interview_page():
    logger.info(f"User {current_user.username} accessed interview page.")
    # Pass username to template if needed
    return render_template('index.html', username=current_user.username)

# Start Interview (Protected)
@app.route('/start-interview', methods=['POST'])
@login_required
def start_interview():
    start_time = time.time()
    user_id = current_user.id
    logger.info(f"User {user_id} requested to start new interview.")

    try:
        if 'resume' not in request.files:
            logger.warning(f"User {user_id}: Resume file part missing.")
            return jsonify({"error": "Resume file is required."}), 400
        resume_file = request.files['resume']
        jd_text = request.form.get('job_description', '').strip()

        # Basic input validation
        if not resume_file or resume_file.filename == '':
            logger.warning(f"User {user_id}: No resume file selected.")
            return jsonify({"error": "No resume file selected."}), 400
        if not jd_text:
            logger.warning(f"User {user_id}: Job description empty.")
            return jsonify({"error": "Job description cannot be empty."}), 400
        if not utils.allowed_file(resume_file.filename, {'pdf'}):
            logger.warning(f"User {user_id}: Invalid file type: {resume_file.filename}")
            return jsonify({"error": "Invalid file type. Please upload a PDF resume."}), 400

        # Secure filename and create temp path
        temp_filename = f"{uuid.uuid4()}_{secure_filename(resume_file.filename)}"
        temp_resume_path = os.path.join(app.config['UPLOAD_FOLDER'], temp_filename)

        resume_text = None
        try:
            logger.debug(f"User {user_id}: Saving temporary resume to: {temp_resume_path}")
            resume_file.save(temp_resume_path)
            logger.debug(f"User {user_id}: Extracting text from resume PDF...")
            resume_text = utils.extract_text_from_pdf(temp_resume_path)

            if resume_text is None or not resume_text.strip():
                 logger.error(f"User {user_id}: Failed to extract text from resume: {temp_resume_path}")
                 return jsonify({"error": "Failed to extract text from the resume PDF. It might be image-based or corrupted."}), 400
            logger.info(f"User {user_id}: Resume text extracted (length: {len(resume_text)} chars).")

        except Exception as pdf_err:
            logger.error(f"User {user_id}: Error processing resume PDF: {pdf_err}", exc_info=True)
            error_msg = "Failed to process resume PDF."
            if isinstance(pdf_err, ImportError):
                 error_msg = "PDF processing library not installed or accessible."
            return jsonify({"error": error_msg}), 500
        finally:
            # Ensure temp file is always removed
            if os.path.exists(temp_resume_path):
                try: os.remove(temp_resume_path)
                except OSError as e: logger.warning(f"Could not remove temp resume file {temp_resume_path}: {e}")

        # Generate Interview ID and Session
        interview_id = str(uuid.uuid4())
        logger.info(f"[{interview_id}] Generated new interview ID for user {user_id}.")

        # Clean up old interview session data from Flask session if any
        old_interview_id = flask_session.pop('interview_id', None)
        if old_interview_id:
            remove_session(old_interview_id) # Remove from in-memory store

        logger.info(f"[{interview_id}] Creating InterviewSession object...")
        # Pass user_id to InterviewSession if needed for associating reports later
        session_obj = InterviewSession(interview_id, resume_text, jd_text) # Pass user_id if needed
        init_state_info = session_obj.get_state()

        if init_state_info["state"] == "ERROR":
            logger.error(f"[{interview_id}] Session initialization failed for user {user_id}. Error: {init_state_info['error']}")
            return jsonify({"error": f"Interview initialization failed: {init_state_info['error']}"}), 500

        store_session(interview_id, session_obj) # Store in memory
        flask_session['interview_id'] = interview_id # Store reference in Flask session
        logger.debug(f"Stored interview_id {interview_id} in Flask session for user {user_id}.")

        elapsed_time = time.time() - start_time
        logger.info(f"[{interview_id}] Interview setup completed in {elapsed_time:.2f} seconds for user {user_id}.")
        return jsonify({"interview_id": interview_id,"message": "Interview initialized successfully. Ready for greeting."}), 200

    except werkzeug.exceptions.RequestEntityTooLarge:
         logger.warning(f"User {user_id}: Resume upload failed - File too large.")
         return jsonify({"error": f"File upload failed. The resume file may be too large (limit: {app.config.get('MAX_CONTENT_LENGTH', 16*1024*1024) // 1024 // 1024} MB)."}), 413
    except Exception as e:
        logger.exception(f"Unexpected error in /start-interview for user {user_id}")
        return jsonify({"error": f"An unexpected server error occurred during setup."}), 500


# Get AI Message (Protected)
@app.route('/get-ai-message', methods=['GET'])
@login_required
def get_ai_message():
    interview_id = flask_session.get('interview_id')
    if not interview_id:
        logger.warning(f"User {current_user.id}: No active interview ID in session.")
        return jsonify({"error": "No active interview session found. Please start a new interview."}), 400

    logger.info(f"[{interview_id}] User {current_user.id} requested next AI message.")
    session_obj = get_session(interview_id)

    if not session_obj:
        logger.warning(f"User {current_user.id}: Interview session {interview_id} not found in memory.")
        flask_session.pop('interview_id', None) # Clean up stale session ID
        return jsonify({"error": "Interview session not found or expired. Please start again."}), 404

    # Optional: Add check here to ensure session_obj belongs to current_user if needed
    # if session_obj.user_id != current_user.id: # Assumes InterviewSession stores user_id
    #    logger.error(f"SECURITY: User {current_user.id} attempted to access session {interview_id} of another user.")
    #    return jsonify({"error": "Permission denied."}), 403

    try:
        state_info = session_obj.get_state()
        current_state = state_info["state"]
        logger.debug(f"[{interview_id}] Current session state: {current_state}")

        ai_message = None
        response_status = 200

        # Determine AI message based on state
        if current_state == "READY": ai_message = session_obj.get_greeting()
        elif current_state == "ASKING": ai_message = session_obj.get_next_ai_turn()
        elif current_state == "AWAITING_RESPONSE": ai_message = session_obj.last_ai_message
        elif current_state in ["FINISHED", "EVALUATING"]: ai_message = session_obj.last_ai_message or "The interview has concluded."
        elif current_state == "ERROR":
             ai_message = state_info.get("error", "An unspecified error occurred.")
             response_status = 500 # Internal Server Error likely
        else: # e.g., INITIALIZING, IN_PROGRESS
             ai_message = "Interview is currently processing, please wait..."
             response_status = 202 # Accepted, still processing

        # Re-check state after potential action (get_greeting/get_next_ai_turn might change state or error out)
        final_state_info = session_obj.get_state()
        if final_state_info["state"] == "ERROR" and response_status != 500: # If error occurred during processing
            ai_message = final_state_info.get("error", "An error occurred generating the AI message.")
            response_status = 500

        logger.info(f"[{interview_id}] Sending AI message to user {current_user.id}. Final state: {final_state_info['state']}")
        return jsonify({"ai_message": ai_message, "status": final_state_info["state"]}), response_status

    except Exception as e:
        logger.exception(f"[{interview_id}] Unexpected error in /get-ai-message for user {current_user.id}")
        if session_obj and session_obj.get_state()["state"] != "ERROR":
             session_obj._set_error_state(f"Server error during AI turn generation: {e}")
        return jsonify({"error": f"An unexpected server error occurred.", "status": "ERROR"}), 500


# Submit Audio Response (Protected)
@app.route('/submit-response', methods=['POST'])
@login_required
def submit_response():
    interview_id = flask_session.get('interview_id')
    if not interview_id:
        logger.warning(f"User {current_user.id}: No active interview ID in session for submit.")
        return jsonify({"error": "No active interview session found. Please start a new interview."}), 400

    logger.info(f"[{interview_id}] User {current_user.id} attempting to submit response.")
    session_obj = get_session(interview_id)

    if not session_obj:
        logger.warning(f"User {current_user.id}: Interview session {interview_id} not found in memory for submit.")
        flask_session.pop('interview_id', None)
        return jsonify({"error": "Interview session not found or expired. Please start again."}), 404

    # Optional: Ownership check
    # if session_obj.user_id != current_user.id: ... return 403 ...

    current_state = session_obj.get_state()["state"]
    if current_state != "AWAITING_RESPONSE":
         logger.warning(f"[{interview_id}] Response submitted by user {current_user.id} while not awaiting. State: {current_state}")
         return jsonify({"error": f"Cannot submit response now (state: {current_state})."}), 409 # Conflict

    if 'audio_data' not in request.files:
        logger.warning(f"[{interview_id}] User {current_user.id}: No 'audio_data' in files.")
        return jsonify({"error": "Audio data blob is required."}), 400
    audio_file = request.files['audio_data']

    if not audio_file or audio_file.filename == '':
        logger.warning(f"[{interview_id}] User {current_user.id}: Empty audio filename.")
        return jsonify({"error": "No audio file selected/uploaded."}), 400

    # Process filename and path
    file_ext = ".bin" # Default extension
    if '.' in audio_file.filename:
        ext_candidate = audio_file.filename.rsplit('.', 1)[1].lower()
        if ext_candidate in ['wav', 'webm', 'ogg', 'mp3', 'flac', 'm4a', 'opus']: # Allowed extensions
             file_ext = f".{ext_candidate}"
        else:
             logger.warning(f"[{interview_id}] User {current_user.id}: Received audio with potentially unsupported extension: {ext_candidate}. Using '.bin'")

    qna_turn_number = session_obj.current_turn_number # Turn number for context
    filename = secure_filename(f"{interview_id}_user_{current_user.id}_turn_{qna_turn_number}_response{file_ext}")
    temp_audio_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    result = {"status": "error", "message": "Audio processing did not complete."}
    response_status = 500

    try:
        logger.debug(f"[{interview_id}] Saving temporary audio for user {current_user.id}, turn {qna_turn_number} to: {temp_audio_path}")
        audio_file.save(temp_audio_path)
        audio_size = os.path.getsize(temp_audio_path)
        logger.info(f"[{interview_id}] Audio file saved (User: {current_user.id}, Size: {audio_size} bytes).")

        if audio_size == 0:
             logger.warning(f"[{interview_id}] User {current_user.id} uploaded empty audio file.")
             raise ValueError("Received empty audio file.")

        logger.info(f"[{interview_id}] Processing candidate response via InterviewSession...")
        # Pass user_id to process_candidate_response if it needs it
        result = session_obj.process_candidate_response(temp_audio_path) # Pass user_id if needed
        logger.info(f"[{interview_id}] Response processing result for user {current_user.id}: {result}")

        # Check status based on result and session state
        final_state_info = session_obj.get_state()
        if final_state_info["state"] == "ERROR":
             result = {"status": "error", "message": final_state_info.get("error", "Error processing response.")}
             response_status = 500
        elif result.get("status") == "success":
             response_status = 200 # OK
        else:
             # Processing failed but session might be recoverable (e.g., STT error)
             response_status = 400 # Bad request or processing error

    except werkzeug.exceptions.RequestEntityTooLarge:
         logger.warning(f"[{interview_id}] Audio upload failed for user {current_user.id}: File too large.")
         result = {"status": "error", "message": f"Audio file is too large (limit: {app.config.get('MAX_CONTENT_LENGTH', 16*1024*1024) // 1024 // 1024} MB)."}
         response_status = 413
    except ValueError as ve:
         logger.error(f"[{interview_id}] Value error processing audio for user {current_user.id}: {ve}")
         result = {"status": "error", "message": str(ve)}
         response_status = 400
    except Exception as e:
        logger.exception(f"[{interview_id}] Error saving or processing audio response for user {current_user.id}")
        result = {"status": "error", "message": f"Server error processing audio."}
        if session_obj and session_obj.get_state()["state"] != "ERROR":
             session_obj._set_error_state(f"Server error processing audio: {e}")
        response_status = 500
    finally:
        if os.path.exists(temp_audio_path):
            try: os.remove(temp_audio_path)
            except OSError as e: logger.warning(f"[{interview_id}] Could not remove temp audio file {temp_audio_path}: {e}")

    # Return final status
    if response_status == 200:
        return jsonify({"status": "OK", "message": "Response received and processed."}), 200
    else:
        return jsonify({"error": result.get("message", "Failed to process response.")}), response_status


# Get Report (Protected)
@app.route('/get-report', methods=['GET'])
@login_required
def get_report():
    interview_id = flask_session.get('interview_id')
    if not interview_id:
        logger.warning(f"User {current_user.id}: No active interview ID in session for get-report.")
        return jsonify({"error": "No active interview session found to generate report."}), 400

    logger.info(f"[{interview_id}] User {current_user.id} requested report.")
    session_obj = get_session(interview_id)

    if not session_obj:
        logger.warning(f"User {current_user.id}: Interview session {interview_id} not found in memory for get-report.")
        flask_session.pop('interview_id', None)
        return jsonify({"error": "Interview session not found or expired."}), 404

    # --- Ownership/Permission Check ---
    # Find the Report record in the database associated with this interview
    # This assumes the report file path includes the interview_id or can be linked
    # If `generate_report` already creates the DB record, we can query it.
    # Modify this query based on how reports are stored/linked.
    # Example: Assuming report_path is stored and unique or title/user_id can find it
    # We might need to add the report saving logic to InterviewSession or here.
    # For now, let's assume the report needs generation first.

    current_state = session_obj.get_state()["state"]
    if current_state not in ["FINISHED", "EVALUATING", "ERROR"]:
         logger.warning(f"[{interview_id}] Report requested by user {current_user.id} before interview finished. State: {current_state}")
         return jsonify({"error": f"Cannot generate report yet. Interview status: {current_state}."}), 409

    # Trigger final evaluation if needed
    if current_state != "ERROR" and not session_obj.evaluation_complete:
         logger.info(f"[{interview_id}] Performing final evaluation for user {current_user.id} before report.")
         try:
              eval_success = session_obj.perform_final_evaluation() # Pass user if needed
              if not eval_success:
                   logger.error(f"[{interview_id}] Final evaluation failed for user {current_user.id}. Report generation stopped.")
                   # Return error if evaluation is critical
                   return jsonify({"error": "Failed to perform final evaluation needed for the report."}), 500
              else:
                   logger.info(f"[{interview_id}] Final evaluation completed.")
         except Exception as eval_err:
              logger.exception(f"[{interview_id}] Error during final evaluation for user {current_user.id}")
              return jsonify({"error": f"Error during final report evaluation: {eval_err}"}), 500

    logger.info(f"[{interview_id}] Attempting to generate report for user {current_user.id}...")
    try:
        # Generate the report PDF file
        # Pass current_user.name or id if needed for the report content/DB record
        # Modification: Ensure generate_report links the created report to the user
        report_path = session_obj.generate_report() # Pass current_user if needed

        if report_path and os.path.exists(report_path):
            # --- Add Report record to DB ---
            # Best practice: The generate_report function or InterviewSession should handle
            # creating the Report DB record and associating it with the user.
            # If not, do it here:
            try:
                 # Check if report record already exists (maybe by file path)
                 report_entry = Report.query.filter_by(file_path=report_path).first()
                 if not report_entry:
                     # Create DB entry for the report
                     report_title = f"Interview Report - {session_obj.role_title} ({interview_id[-8:]})" # Example title
                     new_report_entry = Report(
                         user_id=current_user.id,
                         title=report_title,
                         file_path=report_path # Store the generated path
                     )
                     db.session.add(new_report_entry)
                     db.session.commit()
                     logger.info(f"[{interview_id}] Report DB record created for user {current_user.id}, path: {report_path}")
                     report_entry = new_report_entry # Use the newly created entry
                 # --- Final Permission Check ---
                 if report_entry.user_id != current_user.id:
                      logger.critical(f"SECURITY ALERT: User {current_user.id} attempted to access report {report_entry.id} belonging to user {report_entry.user_id}.")
                      # Do not send the file!
                      return jsonify({"error": "Permission denied to access this report."}), 403

                 # Permission OK, send file
                 logger.info(f"[{interview_id}] Sending report file: {report_path} to user {current_user.id}")
                 return send_file(report_path, as_attachment=True, download_name=os.path.basename(report_path), mimetype='application/pdf')

            except Exception as db_err:
                 db.session.rollback()
                 logger.exception(f"[{interview_id}] Error saving/verifying report record in DB for user {current_user.id}")
                 return jsonify({"error": "Error processing report data."}), 500

        else:
            logger.error(f"[{interview_id}] Report generation failed or file not found for user {current_user.id}. Path: {report_path}")
            error_msg = session_obj.get_state().get("error", "Failed to generate or find the interview report.")
            return jsonify({"error": error_msg}), 500

    except Exception as report_err:
        logger.exception(f"[{interview_id}] Unexpected error during report generation/sending for user {current_user.id}")
        return jsonify({"error": f"An unexpected server error occurred while generating the report: {report_err}"}), 500


# --- Error Handlers ---
@app.errorhandler(400)
def handle_400(error):
    desc = getattr(error, 'description', 'No description provided.')
    logger.warning(f"400 Bad Request: {request.url} - {desc}")
    return jsonify(error="Bad Request", message=desc), 400

@app.errorhandler(401) # Unauthorized (Flask-Login uses this)
def handle_401(error):
    logger.warning(f"401 Unauthorized: Access denied for {request.url}. User not logged in.")
    # Optionally redirect to login page for browser requests, return JSON for API requests
    if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
        return jsonify(error="Unauthorized", message="Authentication required."), 401
    else:
        flash("Please log in to access this page.", "warning")
        return redirect(url_for('auth.login', next=request.url))

@app.errorhandler(403) # Forbidden
def handle_403(error):
    desc = getattr(error, 'description', 'Permission denied.')
    user_info = f"User: {current_user.id}" if current_user.is_authenticated else "User: Anonymous"
    logger.warning(f"403 Forbidden: {user_info} attempted action on {request.url}. Reason: {desc}")
    return jsonify(error="Forbidden", message=desc), 403

@app.errorhandler(404)
def handle_404(error):
    logger.warning(f"404 Not Found: {request.url}")
    return jsonify(error="Not Found", message="The requested resource was not found."), 404

@app.errorhandler(405)
def handle_405(error):
    logger.warning(f"405 Method Not Allowed: {request.method} for {request.url}")
    return jsonify(error="Method Not Allowed", message="The method is not allowed for the requested URL."), 405

@app.errorhandler(413)
def handle_413(error):
    logger.warning(f"413 Request Entity Too Large: {request.url} - Content Length: {request.content_length}")
    limit_mb = app.config.get('MAX_CONTENT_LENGTH', 16*1024*1024) // 1024 // 1024
    return jsonify(error="Request Entity Too Large", message=f"The uploaded file exceeds the maximum allowed size of {limit_mb} MB."), 413

@app.errorhandler(500)
def handle_500(error):
    # Log the original exception if available
    original_exception = getattr(error, 'original_exception', None)
    error_id = uuid.uuid4()
    tb_str = traceback.format_exc() # Get traceback string
    logger.error(f"500 Internal Server Error (ID: {error_id}): {original_exception or error}\n--- Traceback ---\n{tb_str}--- End Traceback ---")
    return jsonify(error="Internal Server Error", message="An unexpected error occurred on the server.", error_id=str(error_id)), 500

@app.errorhandler(Exception) # Catch-all for non-HTTP exceptions
def handle_generic_exception(e):
     # Log the full traceback for internal debugging
    error_id = uuid.uuid4()
    tb_str = traceback.format_exc()
    logger.error(f"Unhandled Non-HTTP Exception (ID: {error_id}): {e}\n--- Traceback ---\n{tb_str}--- End Traceback ---")
    # Always return a generic 500 response
    return jsonify(error="Internal Server Error",
                    message="An unexpected server error occurred.",
                    error_id=str(error_id)), 500

logger.info("Error handlers defined.")


# --- Flask CLI Commands ---
@app.cli.command('create-db')
def create_db_command():
    """Creates the database tables based on models.py."""
    with app.app_context(): # Ensure we are in app context
        try:
            logger.info("Attempting to create database tables...")
            # Check connection URI
            db_uri = app.config.get('SQLALCHEMY_DATABASE_URI')
            if not db_uri:
                logger.error("Cannot create tables: SQLALCHEMY_DATABASE_URI is not configured.")
                print("Error: SQLALCHEMY_DATABASE_URI is not configured in config.py or .env.")
                return

            print(f"Using Database URI: {db_uri.split('@')[1] if '@' in db_uri else db_uri}") # Mask credentials
            db.create_all()
            logger.info("Database tables created successfully (or already exist).")
            print("Database tables created successfully (or already exist).")
        except Exception as e:
            logger.error(f"Error creating database tables: {e}", exc_info=True)
            print(f"\nError creating database tables: {e}")
            print("Please ensure the database server is running, the specified database exists,")
            print("and the connection details (user, password, host, port, dbname) in config.py/.env are correct.")
            print(f"Using connection string: {app.config.get('SQLALCHEMY_DATABASE_URI')}")

@app.cli.command('cleanup-unconfirmed-users')
def cleanup_unconfirmed_users_command():
    """Deletes unconfirmed user accounts older than 3 minutes."""
    with app.app_context():
        try:
            # Calculate the time threshold (3 minutes ago)
            # Ensure timezone awareness matches the database (assuming UTC)
            threshold = datetime.datetime.now(datetime.timezone.utc) - timedelta(minutes=3)
            logger.info(f"Starting cleanup of unconfirmed users created before {threshold.isoformat()}...")

            # Query for users to delete
            users_to_delete = User.query.filter(
                User.is_confirmed == False,
                User.created_at < threshold
            ).all()

            count = len(users_to_delete)
            if count > 0:
                logger.info(f"Found {count} unconfirmed user(s) older than 3 minutes to delete.")
                for user in users_to_delete:
                    logger.debug(f"Deleting user: ID={user.id}, Email={user.email}, Created={user.created_at}")
                    db.session.delete(user)

                # Commit the changes
                db.session.commit()
                logger.info(f"Successfully deleted {count} unconfirmed user(s).")
                print(f"Successfully deleted {count} unconfirmed user(s).")
            else:
                logger.info("No old unconfirmed users found to delete.")
                print("No old unconfirmed users found to delete.")

        except Exception as e:
            db.session.rollback() # Rollback in case of error during deletion
            logger.error(f"Error during cleanup of unconfirmed users: {e}", exc_info=True)
            print(f"Error during cleanup: {e}")

# --- Main Execution Block ---
if __name__ == '__main__':
    logger.info("Running in __main__ block (direct execution)")
    # Check if initialization was successful before running
    if not initialization_complete:
         logger.critical("Initialization did not complete successfully. Exiting.")
         sys.exit(1)

    # Get host and port from config
    host = os.environ.get('FLASK_RUN_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_RUN_PORT', 5050))
    debug_mode = app.config.get('DEBUG', True)

    logger.info(f"Starting Flask development server on http://{host}:{port}/ (Debug: {debug_mode})")
    # Note: Use `flask run` command for development usually.
    # app.run() is mainly for direct script execution or specific deployment scenarios.
    try:
        app.run(host=host, port=port, debug=debug_mode)
    except Exception as run_err:
         logger.critical(f"Failed to start Flask server: {run_err}", exc_info=True)
         sys.exit(1)
else:
    logger.info("App initialized for WSGI server (e.g., gunicorn, flask run).")

print("--- app.py: Reached end of script definition ---")

#flask run --host=0.0.0.0 --port=5050
