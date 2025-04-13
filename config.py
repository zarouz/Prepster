# # config.py
# import os
# from dotenv import load_dotenv
# import warnings
# import logging # Added for logging within config checks

# load_dotenv()
# logger = logging.getLogger(__name__) # Logger for config issues

# # --- General ---
# NUM_QUESTIONS = 6

# # --- File Paths ---
# # NOTE: These defaults are less relevant in Flask but can be fallbacks or examples.
# #       Actual paths will be handled dynamically or configured for uploads.
# DEFAULT_RESUME_PATH = os.getenv("DEFAULT_RESUME_PATH", "example_resume.pdf") # Example placeholder
# DEFAULT_JD_PATH = os.getenv("DEFAULT_JD_PATH", "example_jd.txt")           # Example placeholder

# # --- Directory Paths for Flask App ---
# # Make sure these directories exist or are created by app.py
# UPLOAD_FOLDER = os.path.abspath(os.getenv("UPLOAD_FOLDER", "temp_uploads"))
# REPORT_FOLDER = os.path.abspath(os.getenv("REPORT_FOLDER", "reports"))
# REPORT_FILENAME_TEMPLATE = "{interview_id}_interview_report.pdf" # Template for report names

# # --- Database ---
# DB_NAME = os.getenv("DB_NAME", "KnowledgeBase")
# DB_USER = os.getenv("DB_USER", "karthikyadav")
# DB_PASSWORD = os.getenv("DB_PASSWORD", "")
# DB_HOST = "localhost"
# DB_PORT = os.getenv("DB_PORT", "5432")

# # --- Google Cloud ---
# GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
# GOOGLE_CLOUD_PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT_ID") # Needed for STT

# # --- ElevenLabs (Relevant if NeuroSync Player uses it) ---
# ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
# ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM") # Example: Rachel

# # --- TTS Provider Selection (Relevant for NeuroSync Player configuration hint) ---
# # This setting doesn't directly affect Flask app logic now, but indicates NeuroSync's expected behavior
# TTS_PROVIDER_HINT = os.getenv("TTS_PROVIDER", "google").lower() # Default to google, ensure lowercase

# # --- RAG Configuration ---
# EMBEDDING_MODEL_NAME = 'sentence-transformers/all-mpnet-base-v2'
# MAX_CONTEXT_LENGTH = 10000
# RETRIEVAL_TOP_K = 6
# RETRIEVAL_SIMILARITY_THRESHOLD = 0.58

# # --- LLM Configuration (Google Gemini) ---
# INTERVIEWER_LLM_MODEL_NAME = "gemini-1.5-flash-latest"
# EVALUATOR_LLM_MODEL_NAME = "gemini-1.5-pro-latest"

# # --- LLM Generation Parameters ---
# INTERVIEWER_MAX_TOKENS = 500
# INTERVIEWER_TEMPERATURE = 0.65
# EVALUATOR_MAX_TOKENS = 700
# EVALUATOR_TEMPERATURE = 0.5

# # --- Prompting Constants ---
# MAX_SUMMARY_LENGTH = 1200
# MAX_PROJECT_SUMMARY_LENGTH = 800
# MAX_TOTAL_PROMPT_CHARS = 100000 # Check actual model limits

# # --- Simulation Details (Defaults for report/prompts if needed) ---
# CANDIDATE_NAME = "Candidate" # Can be overridden later if user accounts are added
# INTERVIEWER_AI_NAME = "Alexi"
# COMPANY_NAME = "SecureData Financial Corp." # Example

# # --- Audio Configuration ---
# DEFAULT_AUDIO_SAMPLERATE = 16000 # Important for Google STT

# # --- Google STT Configuration ---
# GOOGLE_STT_LANGUAGE_CODE = "en-US" # Consistent language code

# # --- Emotion Analysis API ---
# EMOTION_API_ENDPOINT = os.environ.get("EMOTION_API_ENDPOINT", "http://127.0.0.1:5003/analyze")

# # --- NeuroSync Player Network Configuration ---
# NEUROSYNC_PLAYER_HOST = os.environ.get("NEUROSYNC_PLAYER_HOST", '127.0.0.1')
# NEUROSYNC_PLAYER_PORT = int(os.environ.get("NEUROSYNC_PLAYER_PORT", 5678)) # Ensure it's an int

# # --- Logging ---
# LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

# # --- Flask Specific ---
# SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "a_default_development_secret_key") # CHANGE FOR PRODUCTION
# if SECRET_KEY == "a_default_development_secret_key":
#     logger.warning("Using default Flask SECRET_KEY. Set a strong FLASK_SECRET_KEY environment variable for production.")

# # --- Final Checks ---
# # Check essential configurations needed by the Flask app
# if not GOOGLE_API_KEY:
#     warnings.warn("Configuration Warning: GOOGLE_API_KEY is not set. LLM interactions will fail.")
#     logger.warning("GOOGLE_API_KEY is not set.")

# if not GOOGLE_CLOUD_PROJECT_ID:
#      warnings.warn("Configuration Warning: GOOGLE_CLOUD_PROJECT_ID is not set. Google STT will fail.")
#      logger.warning("GOOGLE_CLOUD_PROJECT_ID is not set.")

# # Check RAG DB config only if RAG is intended to be active (e.g., based on RETRIEVAL_TOP_K > 0)
# if RETRIEVAL_TOP_K > 0 and not all([DB_NAME, DB_USER, DB_HOST]):
#      warnings.warn("Configuration Warning: RAG retrieval seems enabled (RETRIEVAL_TOP_K > 0), but DB_NAME, DB_USER, or DB_HOST is missing.")
#      logger.warning("RAG DB connection details may be incomplete.")

# logger.info("Configuration loaded.")
# logger.info(f"Upload folder: {UPLOAD_FOLDER}")
# logger.info(f"Report folder: {REPORT_FOLDER}")
# logger.info(f"Emotion API endpoint: {EMOTION_API_ENDPOINT}")
# logger.info(f"NeuroSync Player: {NEUROSYNC_PLAYER_HOST}:{NEUROSYNC_PLAYER_PORT}")

# config.py
import os
from dotenv import load_dotenv
import warnings
import logging

load_dotenv() # Loads variables from .env file into environment
print(f"DEBUG: FLASK_DEBUG from os.environ is: '{os.environ.get('FLASK_DEBUG')}'") 
logger = logging.getLogger(__name__) # Logger for config issues

# --- General ---
NUM_QUESTIONS = 6
# Load FLASK_DEBUG carefully, default to False
raw_debug = os.environ.get("FLASK_DEBUG", "False")
DEBUG = raw_debug.lower() in ("true", "1", "t", "yes")

# --- File Paths ---
UPLOAD_FOLDER = os.path.abspath(os.getenv("UPLOAD_FOLDER", "temp_uploads"))
REPORT_FOLDER = os.path.abspath(os.getenv("REPORT_FOLDER", "reports"))
REPORT_FILENAME_TEMPLATE = "{interview_id}_interview_report.pdf"

# --- SQLAlchemy Database (Users, Reports, Auth Data) ---
SQLALCHEMY_DB_NAME = os.getenv("SQLALCHEMY_DB_NAME", "users")
SQLALCHEMY_DB_USER = os.getenv("SQLALCHEMY_DB_USER") # Load from .env
SQLALCHEMY_DB_PASSWORD = os.getenv("SQLALCHEMY_DB_PASSWORD", "") # Load from .env, default empty
SQLALCHEMY_DB_HOST = os.getenv("SQLALCHEMY_DB_HOST", "localhost")
SQLALCHEMY_DB_PORT = os.getenv("SQLALCHEMY_DB_PORT", "5432")

# --- SQLAlchemy Configuration ---
if not SQLALCHEMY_DB_USER: # Password can be empty, but user is required
    logger.warning("SQLALCHEMY_DB_USER not set in environment. Database features will fail.")
    SQLALCHEMY_DATABASE_URI = None
else:
    SQLALCHEMY_DATABASE_URI = f"postgresql://{SQLALCHEMY_DB_USER}:{SQLALCHEMY_DB_PASSWORD}@{SQLALCHEMY_DB_HOST}:{SQLALCHEMY_DB_PORT}/{SQLALCHEMY_DB_NAME}"
SQLALCHEMY_TRACK_MODIFICATIONS = False

# --- RAG Database (Knowledge Base - Accessed via psycopg2) ---
RAG_ENABLED = os.environ.get("RAG_ENABLED", "True").lower() == "true"
RAG_DB_NAME = os.getenv("RAG_DB_NAME", "knowledgebase") # Use "KnowledgeBase" from .env
RAG_DB_USER = os.getenv("RAG_DB_USER") # Load from .env
RAG_DB_PASSWORD = os.getenv("RAG_DB_PASSWORD", "") # Load from .env, default empty
RAG_DB_HOST = os.getenv("RAG_DB_HOST", "localhost")
RAG_DB_PORT = os.getenv("RAG_DB_PORT", "5432")

# --- RAG Configuration ---
EMBEDDING_MODEL_NAME = 'sentence-transformers/all-mpnet-base-v2'
MAX_CONTEXT_LENGTH = 10000
RETRIEVAL_TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "6"))
RETRIEVAL_SIMILARITY_THRESHOLD = float(os.getenv("RETRIEVAL_SIMILARITY_THRESHOLD", "0.58"))

if not RAG_ENABLED:
    RETRIEVAL_TOP_K = 0
    logger.info("RAG feature is disabled via RAG_ENABLED=False.")

# --- Google Cloud ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CLOUD_PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS") # Load credentials path

# Set environment variable if path is provided in config (for libraries that auto-detect)
if GOOGLE_APPLICATION_CREDENTIALS and os.path.exists(GOOGLE_APPLICATION_CREDENTIALS):
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = GOOGLE_APPLICATION_CREDENTIALS
    logger.info(f"Using Google Application Credentials from: {GOOGLE_APPLICATION_CREDENTIALS}")
elif GOOGLE_APPLICATION_CREDENTIALS:
    logger.warning(f"GOOGLE_APPLICATION_CREDENTIALS path specified but not found: {GOOGLE_APPLICATION_CREDENTIALS}")

# --- LLM Configuration (Google Gemini) ---
INTERVIEWER_LLM_MODEL_NAME = "gemini-1.5-flash-latest"
EVALUATOR_LLM_MODEL_NAME = "gemini-1.5-pro-latest" # Consider using flash here too for cost/speed if acceptable

# --- LLM Generation Parameters ---
INTERVIEWER_MAX_TOKENS = 500
INTERVIEWER_TEMPERATURE = 0.65
EVALUATOR_MAX_TOKENS = 700
EVALUATOR_TEMPERATURE = 0.5

# --- Prompting Constants ---
MAX_SUMMARY_LENGTH = 1200
MAX_PROJECT_SUMMARY_LENGTH = 800
MAX_TOTAL_PROMPT_CHARS = 100000 # Check actual model limits

# --- Simulation Details (Defaults for report/prompts if needed) ---
CANDIDATE_NAME = "Candidate"
INTERVIEWER_AI_NAME = "Alexi"
COMPANY_NAME = "SecureData Financial Corp."

# --- Audio Configuration ---
DEFAULT_AUDIO_SAMPLERATE = 16000
GOOGLE_STT_LANGUAGE_CODE = "en-US"

# --- External Service Endpoints ---
EMOTION_API_ENDPOINT = os.environ.get("EMOTION_API_ENDPOINT", "http://127.0.0.1:5003/analyze")
NEUROSYNC_PLAYER_HOST = os.environ.get("NEUROSYNC_PLAYER_HOST", '127.0.0.1')
NEUROSYNC_PLAYER_PORT = int(os.environ.get("NEUROSYNC_PLAYER_PORT", 5678))

# --- Logging ---
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

# --- Flask Specific ---
SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "a_very_insecure_default_dev_key_change_me")
if SECRET_KEY == "a_very_insecure_default_dev_key_change_me" or "please_change" in SECRET_KEY:
    logger.critical("SECURITY WARNING: Using default or placeholder Flask SECRET_KEY. Generate and set a strong FLASK_SECRET_KEY environment variable for production.")

# --- Flask-Mail Configuration ---
MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.googlemail.com')
MAIL_PORT = int(os.getenv('MAIL_PORT', '587'))
MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'true').lower() == 'true'
MAIL_USE_SSL = os.getenv('MAIL_USE_SSL', 'false').lower() == 'true'
MAIL_USERNAME = os.getenv('MAIL_USERNAME')
MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', MAIL_USERNAME)
MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
print(f"DEBUG config.py: MAIL_USERNAME='{MAIL_USERNAME}', MAIL_PASSWORD_IS_SET={'Yes' if MAIL_PASSWORD else 'No'}")

# --- Token Generation (itsdangerous) ---
SECURITY_PASSWORD_SALT = os.getenv('SECURITY_PASSWORD_SALT', 'password_salt_change_me')
EMAIL_CONFIRMATION_SALT = os.getenv('EMAIL_CONFIRMATION_SALT', 'email_salt_change_me')
if "change_me" in SECURITY_PASSWORD_SALT or "change_me" in EMAIL_CONFIRMATION_SALT:
     logger.critical("SECURITY WARNING: Using default or placeholder SECURITY_PASSWORD_SALT or EMAIL_CONFIRMATION_SALT. Generate and set strong unique salts in environment variables.")

EMAIL_TOKEN_EXPIRATION = 3600
PASSWORD_RESET_TOKEN_EXPIRATION = 1800

# --- Login Configuration ---
FAILED_LOGIN_ATTEMPTS_LOCKOUT = 5


# --- Final Checks (Log warnings for missing critical components) ---
if not GOOGLE_API_KEY:
    logger.warning("GOOGLE_API_KEY is not set in environment. Gemini LLM interactions might fail if Application Default Credentials don't cover generative models.")

if not GOOGLE_CLOUD_PROJECT_ID:
     logger.warning("GOOGLE_CLOUD_PROJECT_ID is not set. Google STT might fail.")

if not SQLALCHEMY_DATABASE_URI:
    logger.error("SQLALCHEMY_DATABASE_URI is not configured (likely missing SQLALCHEMY_DB_USER in .env). App database features WILL fail.")

if RAG_ENABLED and RETRIEVAL_TOP_K > 0:
    if not all([RAG_DB_NAME, RAG_DB_USER, RAG_DB_HOST]): # Password can be empty
         logger.warning("RAG is enabled, but RAG database connection details (RAG_DB_NAME, RAG_DB_USER, RAG_DB_HOST) are incomplete. RAG retrieval will fail.")
else:
     logger.info("RAG retrieval is disabled (RAG_ENABLED=False or RETRIEVAL_TOP_K=0).")

if MAIL_USERNAME and MAIL_USERNAME == 'your_email_address@gmail.com':
     logger.warning("Using placeholder MAIL_USERNAME. Email sending will not work until configured.")
elif MAIL_USERNAME and not MAIL_PASSWORD:
     logger.warning("MAIL_USERNAME is set, but MAIL_PASSWORD is missing. Email sending will likely fail.")


logger.info("-" * 20 + " Configuration Loaded " + "-" * 20)
logger.info(f"Debug Mode: {DEBUG}")
if SQLALCHEMY_DATABASE_URI:
    logger.info(f"App DB (SQLAlchemy): postgresql://{SQLALCHEMY_DB_USER}:***@{SQLALCHEMY_DB_HOST}:{SQLALCHEMY_DB_PORT}/{SQLALCHEMY_DB_NAME}")
else:
    logger.error("App DB (SQLAlchemy): NOT CONFIGURED")
if RAG_ENABLED and RETRIEVAL_TOP_K > 0 and all([RAG_DB_NAME, RAG_DB_USER, RAG_DB_HOST]):
    logger.info(f"RAG DB (psycopg2): postgresql://{RAG_DB_USER}:***@{RAG_DB_HOST}:{RAG_DB_PORT}/{RAG_DB_NAME}")
elif RAG_ENABLED:
    logger.warning("RAG DB (psycopg2): Enabled but configuration incomplete.")
else:
    logger.info("RAG DB (psycopg2): Disabled.")
logger.info(f"Mail Server: {MAIL_SERVER}:{MAIL_PORT} (Username: {MAIL_USERNAME})")
logger.info(f"Upload Folder: {UPLOAD_FOLDER}")
logger.info(f"Report Folder: {REPORT_FOLDER}")
logger.info(f"Google Project ID: {GOOGLE_CLOUD_PROJECT_ID}")
logger.info(f"Google API Key Set: {'Yes' if GOOGLE_API_KEY else 'No'}")
logger.info(f"Google Credentials File Set: {'Yes - ' + GOOGLE_APPLICATION_CREDENTIALS if GOOGLE_APPLICATION_CREDENTIALS else 'No'}")
logger.info(f"Emotion API Endpoint: {EMOTION_API_ENDPOINT}")
logger.info(f"NeuroSync Player: {NEUROSYNC_PLAYER_HOST}:{NEUROSYNC_PLAYER_PORT}")
logger.info("-" * 58)