# AI Interview Simulator - Backend

## Overview

This project is the backend Flask application for an AI-powered interview simulator. It allows users to register, log in, and participate in simulated job interviews tailored to a specific role based on their resume and a provided job description. The AI interviewer asks questions, processes the candidate's audio responses, evaluates them, and generates a comprehensive feedback report.

## Utility Services

- [KnowledgeBase](https://github.com/zarouz/KnowledgeBase.git): Setting up Postgress DB for RAG
- [EmotionalAnalysis_API](https://github.com/zarouz/EmotionalAnalysis_API.git): ML Service to gauge user's emotions based on audio
- [NeuroSync](https://github.com/AnimaVR/NeuroSync_Player.git): Connecting to 3-D avatar

## Features

- **User Authentication:** Secure registration, login, logout, email confirmation, and password reset functionality using Flask-Login, Flask-Bcrypt, and Flask-Mail.
- **Interview Session Management:**
  - Starts interviews based on uploaded PDF resume and job description text.
  - Summarizes inputs and extracts key details (projects, experience).
  - Identifies the target role and relevant focus topics using NLTK.
- **AI-Powered Interviewer:**
  - Generates relevant interview questions (technical, scenario-based, project-specific) using configured Google Gemini LLMs.
  - Conducts a conversational interview flow, asking prepared questions and dynamic, relevant follow-up questions based on the candidate's responses.
  - Integrates with RAG (Retrieval-Augmented Generation) using a PostgreSQL/pgvector knowledge base for context-aware questions (optional, configurable). 
- **Audio Processing:**
  - Accepts audio responses (e.g., WAV, WebM, Ogg) from the candidate via file upload.
  - Transcribes audio using Google Cloud Speech-to-Text, handling various encodings.
  - Analyzes speech emotion/confidence using an external API (endpoint configurable via environment variable).
- **Response Evaluation:** Evaluates transcribed candidate responses using a configured Google Gemini LLM based on relevance, technical accuracy, clarity, and alignment with the role.
- **PDF Report Generation:** Creates a detailed PDF report summarizing the interview performance, including Q&A transcripts, evaluations, scores, confidence analysis, and overall feedback using ReportLab.
- **Database Integration:** Uses PostgreSQL via SQLAlchemy for user data, reports, and authentication tokens. Supports database schema migrations using Flask-Migrate. Optionally uses a separate PostgreSQL database for the RAG knowledge base.
- **Configuration:** Uses environment variables (loaded from a `.env` file) for flexible configuration of database connections, API keys, model names, external services, and other parameters.

## Technology Stack

- **Backend Framework:** Flask
- **Database:** PostgreSQL
- **ORM:** SQLAlchemy
- **Database Migrations:** Flask-Migrate
- **Authentication:** Flask-Login, Flask-Bcrypt, itsdangerous (for tokens)
- **Email:** Flask-Mail
- **LLMs:** Google Gemini (via `google-generativeai`)
- **Speech-to-Text:** Google Cloud Speech-to-Text
- **Audio Processing:** soundfile (for format detection), potentially librosa (indirectly or future use)
- **Text Processing:** NLTK (tokenization, POS tagging, stopwords)
- **RAG Embeddings:** sentence-transformers
- **RAG Vector DB:** PostgreSQL with pgvector extension
- **PDF Generation:** ReportLab
- **PDF Parsing:** pdfplumber
- **Dependencies:** See `requirements.txt` for the full list.

## Setup and Installation

1.  **Clone the Repository:**

    ```bash
    git clone <repository-url>
    cd Backend # Navigate to the backend directory
    ```

2.  **Create and Activate a Virtual Environment:**

    ```bash
    python -m venv venv
    source venv/bin/activate # On Linux/macOS
    # venv\Scripts\activate # On Windows
    ```

3.  **Install Dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Environment Variables:**

    - Create a `.env` file in the `Backend` root directory.
    - Populate it with the necessary variables. Refer to `config.py` for all possible variables. Key variables include:

      ```dotenv
      # Flask Core
      FLASK_APP=app.py
      FLASK_DEBUG=True # Set to False for production
      FLASK_SECRET_KEY='your_strong_random_secret_key' # CHANGE THIS!

      # SQLAlchemy Database (User/App Data)
      SQLALCHEMY_DB_NAME=ai_interview_users
      SQLALCHEMY_DB_USER=your_db_user
      SQLALCHEMY_DB_PASSWORD=your_db_password
      SQLALCHEMY_DB_HOST=localhost # Or your DB host
      SQLALCHEMY_DB_PORT=5432

      # RAG Database (Knowledge Base - Optional)
      RAG_ENABLED=True # Set to False to disable RAG
      RAG_DB_NAME=ai_interview_knowledge
      RAG_DB_USER=your_rag_db_user
      RAG_DB_PASSWORD=your_rag_db_password
      RAG_DB_HOST=localhost
      RAG_DB_PORT=5432
      # RAG_EMBEDDING_MODEL_NAME='sentence-transformers/all-mpnet-base-v2' # Default
      # RETRIEVAL_TOP_K=6
      # RETRIEVAL_SIMILARITY_THRESHOLD=0.58

      # Google Cloud
      GOOGLE_API_KEY='your_google_api_key_for_gemini' # Ensure this key has access to Gemini API
      GOOGLE_CLOUD_PROJECT_ID='your_google_cloud_project_id'
      # Option 1: Set path to service account key file (recommended for servers)
      GOOGLE_APPLICATION_CREDENTIALS='/path/to/your/google_credentials.json'
      # Option 2: Use Application Default Credentials (good for local dev, run `gcloud auth application-default login`)

      # Flask-Mail (e.g., using Gmail)
      MAIL_SERVER=smtp.googlemail.com
      MAIL_PORT=587
      MAIL_USE_TLS=True
      MAIL_USERNAME='your_email@gmail.com'
      MAIL_PASSWORD='your_gmail_app_password' # Use App Password if 2FA enabled
      MAIL_DEFAULT_SENDER='your_email@gmail.com'

      # Security Salts (Generate unique random strings using e.g., `openssl rand -hex 32`)
      SECURITY_PASSWORD_SALT='your_unique_password_salt_here' # CHANGE THIS!
      EMAIL_CONFIRMATION_SALT='your_unique_email_salt_here' # CHANGE THIS!

      # External Services (Optional)
      EMOTION_API_ENDPOINT='http://127.0.0.1:5003/analyze' # URL of your emotion analysis service
      NEUROSYNC_PLAYER_HOST='127.0.0.1' # Host for the NeuroSync text player
      NEUROSYNC_PLAYER_PORT=5678      # Port for the NeuroSync text player

      # Other Config
      # LOG_LEVEL=INFO
      # UPLOAD_FOLDER=temp_uploads
      # REPORT_FOLDER=reports
      ```

    - **Important:** Replace placeholder values with your actual credentials and settings. Generate strong, unique secret keys and salts. Do not commit the `.env` file to version control.

5.  **Setup Databases:**

    - Ensure your PostgreSQL server is running.
    - Create the two databases specified in your `.env` file (e.g., `ai_interview_users` and `ai_interview_knowledge`).
    - **RAG Database Only:** If RAG is enabled (`RAG_ENABLED=True`), connect to your RAG database (e.g., `ai_interview_knowledge`) using `psql` or a GUI tool and enable the `pgvector` extension:
      ```sql
      CREATE EXTENSION IF NOT EXISTS vector;
      ```
      You will also need to create the `knowledge_documents` table (schema likely includes `id SERIAL PRIMARY KEY`, `content TEXT`, `embedding VECTOR(768)`) and populate it with your knowledge base data and corresponding embeddings generated using the model specified in `RAG_EMBEDDING_MODEL_NAME`. (The exact table schema and population method depend on your specific RAG setup).

6.  **Initialize Application Database Schema:**

    - Run the Flask database migration commands to create the necessary tables (`users`, `reports`, `password_reset`) in your application database (e.g., `ai_interview_users`):
      ```bash
      # Ensure FLASK_APP=app.py is set in your environment or .env file
      flask db init # Run only once if the 'migrations' folder doesn't exist
      flask db migrate -m "Initial database schema" # Create the first migration script
      flask db upgrade # Apply the migration to the database
      ```
    - If you make changes to `models.py` later, run `flask db migrate -m "Description of changes"` and `flask db upgrade` again.

7.  **Download NLTK Data:**

    - The application attempts to download necessary NLTK data (`punkt`, `stopwords`, `averaged_perceptron_tagger`) on first run if missing. Ensure you have internet connectivity during the first startup. It tries to store downloaded data in a project-local `nltk_data` directory or use the default NLTK path.

8.  **Google Cloud Authentication & APIs:**
    - Ensure your environment is authenticated to Google Cloud, either via `GOOGLE_APPLICATION_CREDENTIALS` pointing to a service account key file or by using Application Default Credentials (ADC) (e.g., run `gcloud auth application-default login`).
    - The authenticated principal (user or service account) needs permissions for:
      - Google Gemini (Vertex AI API or Generative Language API, depending on the key used).
      - Google Cloud Speech-to-Text API.
    - Make sure these APIs are enabled in your Google Cloud project.

## Running the Application

1.  **Activate Virtual Environment:**

    ```bash
    source venv/bin/activate # Linux/macOS
    # venv\Scripts\activate # Windows
    ```

2.  **Run the Flask Development Server:**
    ```bash
    # Ensure FLASK_APP=app.py is set
    flask run --host=0.0.0.0 --port=5050
    ```
    - The application will start, typically listening on `http://0.0.0.0:5050/`. Access it via `http://localhost:5050` or `http://<your-machine-ip>:5050`.
    - Check the terminal output for initialization logs and any potential errors.

## Project Structure

```
Backend/
├── .env                # Local environment variables (MUST BE CREATED)
├── .gitignore          # Git ignore rules
├── app.py              # Main Flask application: routing, initialization, error handling
├── auth.py             # Authentication blueprint (login, register, reset password, etc.)
├── config.py           # Configuration loading from environment variables
├── generate_secrets.py # Utility script to generate secret keys/salts (optional helper)
├── Job_description.txt # Example job description (likely for testing)
├── models.py           # SQLAlchemy database models (User, Report, PasswordReset)
├── README.md           # This file
├── requirements.txt    # Python dependencies
├── temp. text          # Temporary file? (Should likely be removed or gitignored)
├── migrations/         # Flask-Migrate migration files
│   ├── alembic.ini     # Migration config
│   ├── env.py          # Migration environment setup
│   ├── README          # Info about migrations
│   ├── script.py.mako  # Migration script template
│   └── versions/       # Directory containing individual migration scripts
├── modules/            # Core application logic modules
│   ├── __init__.py
│   ├── audio_utils.py  # Speech-to-Text (Google STT) logic and client initialization
│   ├── interview_logic.py # Core InterviewSession class, state management, flow control
│   ├── llm_interface.py # Interaction with Google Gemini LLMs (querying, cleaning)
│   ├── prompt_templates.py # Stores the detailed prompt templates for LLM interactions
│   ├── report_generator.py # PDF report generation using ReportLab
│   └── utils.py        # Utility functions (PDF parsing, NLTK init/processing, RAG helpers, text cleaning)
├── reports/            # Default directory for generated PDF reports (configurable)
├── static/             # Static files (CSS, JS) served for frontend templates
│   ├── css/
│   └── js/
├── temp_uploads/       # Default directory for temporary file uploads (resumes, audio) (configurable)
└── templates/          # HTML templates rendered by Flask (using Jinja2)
    ├── index.html      # Main interview page template
    ├── auth/           # Authentication-related templates (login.html, register.html, etc.)
    └── email/          # Email templates (confirm_email.html, reset_password.html)
```

## Configuration

Configuration is managed via environment variables loaded from a `.env` file in the project root using `python-dotenv`. `config.py` defines how these variables are loaded and provides defaults where applicable.

Key configurable areas include:

- Flask settings (`SECRET_KEY`, `DEBUG`)
- Database URIs (SQLAlchemy App DB, RAG DB)
- Google Cloud credentials and project ID (`GOOGLE_API_KEY`, `GOOGLE_CLOUD_PROJECT_ID`, `GOOGLE_APPLICATION_CREDENTIALS`)
- LLM model names (`INTERVIEWER_LLM_MODEL_NAME`, `EVALUATOR_LLM_MODEL_NAME`) and generation parameters (max tokens, temperature)
- RAG settings (`RAG_ENABLED`, embedding model name, retrieval parameters `RETRIEVAL_TOP_K`, `RETRIEVAL_SIMILARITY_THRESHOLD`)
- Flask-Mail settings for sending emails
- Security salts for token generation
- File paths (`UPLOAD_FOLDER`, `REPORT_FOLDER`)
- External service endpoints (Emotion Analysis API, NeuroSync Player)
- Logging level (`LOG_LEVEL`)

Refer to `config.py` and the Setup section for a comprehensive list and descriptions.

## API Endpoints

The main API endpoints defined in `app.py` (excluding static file routes) are:

- `/` : (GET) Redirects to `/auth/login` or `/interview` based on authentication state.
- `/interview`: (GET, Protected) Renders the main interview interface (`templates/index.html`).
- `/auth/`: Routes handled by the `auth.py` blueprint:
  - `/register`: (GET, POST) User registration page and processing.
  - `/login`: (GET, POST) User login page and processing.
  - `/logout`: (GET, Protected) Logs the user out.
  - `/confirm/<token>`: (GET) Handles email confirmation links.
  - `/reset_password_request`: (GET, POST) Page to request a password reset email.
  - `/reset_password/<token>`: (GET, POST) Page to set a new password using a reset token.
  - `/resend_confirmation`: (POST) Endpoint to trigger resending the confirmation email.
- `/start-interview`: (POST, Protected) Initializes a new interview session. Expects `resume` (file) and `job_description` (form data). Returns `interview_id`.
- `/get-ai-message`: (GET, Protected) Fetches the next message/question from the AI interviewer for the active session.
- `/submit-response`: (POST, Protected) Submits the candidate's audio response (`audio_data` file) for the current question.
- `/get-report`: (GET, Protected) Generates and triggers the download of the final interview report PDF for the completed session.

Error handlers for common HTTP status codes (400, 401, 403, 404, 405, 413, 500) are also defined in `app.py`.

## Modules Overview

- **`interview_logic.py`**: Contains the `InterviewSession` class, which encapsulates the state and logic for a single interview from start to finish, including interaction with other modules.
- **`llm_interface.py`**: Provides functions (`query_llm`, `clean_llm_output`) to interact with the configured Google Gemini models, handling API calls, retries, and basic response processing.
- **`audio_utils.py`**: Handles audio transcription by initializing the Google Cloud Speech-to-Text client and providing the `transcribe_audio_file_google` function.
- **`utils.py`**: A collection of helper functions for tasks like PDF text extraction (`extract_text_from_pdf`), NLTK initialization and processing (`initialize_nltk`, `extract_keywords`, `get_focus_topics`), RAG database interaction (`initialize_rag`, `retrieve_similar_documents`, `format_rag_context`), text cleaning, and resource cleanup.
- **`prompt_templates.py`**: Centralizes the detailed prompt templates used to instruct the LLMs for question generation, conversational turns, and evaluation.
- **`report_generator.py`**: Uses the ReportLab library to construct and save the final interview feedback as a structured PDF file.

## Database Migrations

Database schema changes are managed using Flask-Migrate, which uses Alembic internally.

- **Initialize (only once per project):**
  ```bash
  flask db init
  ```
- **Create a new migration script after changing models in `models.py`:**
  ```bash
  flask db migrate -m "Short description of schema changes"
  ```
  (Review the generated script in `migrations/versions/`)
- **Apply the latest migration(s) to the database:**
  ```bash
  flask db upgrade
  ```
- **Revert the last applied migration:**
  ```bash
  flask db downgrade
  ```

## Potential Future Enhancements

- More sophisticated RAG chunking, indexing, and retrieval strategies.
- Support for alternative LLM providers (e.g., OpenAI, Anthropic).
- Improved frontend interface (potentially as a separate SPA).
- Real-time audio streaming for transcription and analysis.
- More granular feedback in the report (e.g., topic coverage analysis, sentiment trends).
- Admin interface for user management, knowledge base curation, and viewing reports.
- Integration with Applicant Tracking Systems (ATS).
- Containerization using Docker.
