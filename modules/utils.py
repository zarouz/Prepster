# modules/utils.py
import logging
import os
import re
import warnings
import sys # For NLTK download path check

# PDF Parsing
try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    logging.getLogger(__name__).warning("pdfplumber not found. PDF text extraction will fail. Install with: pip install pdfplumber")

# NLTK for text processing
try:
    import nltk
    # Define potential NLTK data paths
    # Common paths; adjust if your setup is different
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir) # Assumes modules is one level down
    nltk_data_paths = [
        os.path.join(project_root, 'nltk_data'), # Project-local data folder
        nltk.data.path[0] # Default NLTK path
    ]
    # Ensure the first path exists if we intend to use it
    # os.makedirs(nltk_data_paths[0], exist_ok=True)
    nltk.data.path = nltk_data_paths # Prepend our path

    from nltk.corpus import stopwords
    from nltk.tokenize import word_tokenize, sent_tokenize
    from nltk import pos_tag
    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False
    stopwords = None
    word_tokenize = None
    sent_tokenize = None
    pos_tag = None
    logging.getLogger(__name__).warning("NLTK not found. Text processing features may be limited. Install with: pip install nltk")

# RAG Dependencies
try:
    import psycopg2 # For PostgreSQL connection
    from sentence_transformers import SentenceTransformer # For embeddings
    RAG_DEPENDENCIES_AVAILABLE = True
except ImportError as e:
    RAG_DEPENDENCIES_AVAILABLE = False
    psycopg2 = None
    SentenceTransformer = None
    logging.getLogger(__name__).warning(f"RAG dependencies not fully met ({e}). RAG features might be disabled. Install: pip install psycopg2-binary sentence-transformers torch")

# Local Imports
import config # Import the updated config

logger = logging.getLogger(__name__)

# --- File Handling Utilities ---
def allowed_file(filename, allowed_extensions):
    """Checks if a filename has an allowed extension."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

# --- Global Variables for RAG ---
rag_db_connection = None # Use a distinct name for RAG connection
rag_db_cursor = None     # Use a distinct name
embedding_model = None
nltk_initialized = False

# --- NLTK Initialization ---
def initialize_nltk():
    """Downloads necessary NLTK data if not already present."""
    global nltk_initialized
    if not NLTK_AVAILABLE or nltk_initialized:
        return

    required_data = ["punkt", "stopwords", "averaged_perceptron_tagger"]
    logger.info(f"Checking NLTK data ({required_data}). Path: {nltk.data.path}")
    all_data_found = True
    for package in required_data:
         try:
             # More reliable check using find
             if package == "punkt": nltk.data.find('tokenizers/punkt')
             elif package == "stopwords": nltk.data.find('corpora/stopwords')
             elif package == "averaged_perceptron_tagger": nltk.data.find('taggers/averaged_perceptron_tagger')
             logger.debug(f"NLTK package '{package}' found.")
         except LookupError:
             logger.warning(f"NLTK package '{package}' not found. Attempting download...")
             all_data_found = False
             try:
                 nltk.download(package, quiet=True)
                 logger.info(f"NLTK package '{package}' downloaded successfully.")
             except Exception as e:
                 # This might happen due to network issues or permissions
                  logger.error(f"Failed to download NLTK data '{package}': {e}. Some text processing features might fail.", exc_info=True)
                  # Don't stop initialization, but log the error

    if all_data_found:
         logger.info("Required NLTK data packages are available.")
    nltk_initialized = True


# --- RAG Initialization ---
def initialize_rag():
    """Initializes embedding model and RAG database connection."""
    global embedding_model, rag_db_connection, rag_db_cursor # Use specific names

    # Check config flags first
    logger.info(f"RAG Check: config.RAG_ENABLED={config.RAG_ENABLED}, config.RETRIEVAL_TOP_K={config.RETRIEVAL_TOP_K}") # Changed to info log
    if not config.RAG_ENABLED or config.RETRIEVAL_TOP_K <= 0:
        logger.info("RAG is disabled by configuration (RAG_ENABLED=False or RETRIEVAL_TOP_K <= 0). Skipping RAG initialization.")
        return

    if not RAG_DEPENDENCIES_AVAILABLE:
        logger.warning("RAG dependencies (psycopg2, sentence-transformers) not met. RAG features disabled.")
        config.RAG_ENABLED = False # Ensure it's marked disabled
        return

    # 1. Initialize Embedding Model (only if not already loaded)
    if embedding_model is None:
        try:
            logger.info(f"Loading embedding model for RAG: {config.EMBEDDING_MODEL_NAME}")
            embedding_model = SentenceTransformer(config.EMBEDDING_MODEL_NAME)
            logger.info("RAG Embedding model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load RAG embedding model '{config.EMBEDDING_MODEL_NAME}': {e}", exc_info=True)
            embedding_model = None
            config.RAG_ENABLED = False # Disable RAG if model fails
            logger.warning("Disabling RAG due to embedding model failure.")
            return # Stop initialization here

    # 2. Initialize RAG Database Connection (only if not already connected)
    if rag_db_connection is None:
        # Check if RAG-specific config variables are present
        # Password can be empty string, so check user and host specifically
        if not all([config.RAG_DB_NAME, config.RAG_DB_USER, config.RAG_DB_HOST]):
             logger.error("RAG Database configuration (RAG_DB_NAME, RAG_DB_USER, RAG_DB_HOST) is incomplete.")
             config.RAG_ENABLED = False
             logger.warning("Disabling RAG due to incomplete RAG DB configuration.")
             return

        try:
            logger.info(f"Connecting to RAG database '{config.RAG_DB_NAME}' on {config.RAG_DB_HOST}:{config.RAG_DB_PORT} as user '{config.RAG_DB_USER}'...")
            rag_db_connection = psycopg2.connect(
                dbname=config.RAG_DB_NAME,
                user=config.RAG_DB_USER,
                password=config.RAG_DB_PASSWORD, # Handles empty string correctly
                host=config.RAG_DB_HOST,
                port=config.RAG_DB_PORT,
                connect_timeout=10
            )
            rag_db_cursor = rag_db_connection.cursor()
            # Test connection
            rag_db_cursor.execute("SELECT 1;") # Simple query to check connection
            rag_db_cursor.fetchone()
            logger.info("RAG Database connection successful.")
        except psycopg2.OperationalError as e:
            logger.error(f"Failed to connect to RAG database '{config.RAG_DB_NAME}' on {config.RAG_DB_HOST}: {e}", exc_info=False) # Less verbose log often
            rag_db_connection = None
            rag_db_cursor = None
            config.RAG_ENABLED = False
            logger.warning("Disabling RAG due to RAG database connection failure. Check credentials, host, port, and if DB exists.")
        except Exception as e:
             logger.error(f"An unexpected error occurred during RAG database connection: {e}", exc_info=True)
             rag_db_connection = None
             rag_db_cursor = None
             config.RAG_ENABLED = False
             logger.warning("Disabling RAG due to unexpected RAG database connection error.")


# --- PDF Text Extraction ---
def extract_text_from_pdf(pdf_path):
    if not PDFPLUMBER_AVAILABLE:
        logger.error("pdfplumber library is not available. Cannot extract text from PDF.")
        return None
    if not os.path.exists(pdf_path):
        logger.error(f"PDF file not found at path: {pdf_path}")
        return None
    logger.info(f"Extracting text from PDF: {os.path.basename(pdf_path)}")
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            logger.info(f"Successfully extracted {len(text)} characters from PDF.")
            return text.strip()
    except Exception as e:
        logger.error(f"Error extracting text from PDF '{os.path.basename(pdf_path)}': {e}", exc_info=True)
        return None

# --- Text Cleaning ---
def clean_text(text):
    if not isinstance(text, str): return ""
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\n+', '\n', text)
    return text.strip()

# --- NLTK Based Keyword Extraction ---
def extract_keywords(text, max_keywords=10):
    if not NLTK_AVAILABLE or not nltk_initialized:
        # logger.warning("NLTK not available/initialized. Skipping keyword extraction.")
        return []
    if not text: return []
    try:
        words = word_tokenize(text.lower())
        tagged_words = pos_tag(words)
        stop_words_list = stopwords.words('english')
        keywords = [word for word, tag in tagged_words if tag.startswith('NN') and word.isalnum() and word not in stop_words_list and len(word) > 2]
        freq_dist = nltk.FreqDist(keywords)
        return [kw for kw, freq in freq_dist.most_common(max_keywords)]
    except Exception as e:
        logger.error(f"Error during NLTK keyword extraction: {e}", exc_info=True)
        return []

# --- RAG Helper Functions ---
def generate_search_queries(resume_summary, jd_summary, num_queries=3):
    logger.debug("Generating RAG search queries...")
    if not NLTK_AVAILABLE or not nltk_initialized:
         logger.warning("NLTK unavailable, using basic combined text for RAG query.")
         combined_text = f"Job Description: {jd_summary} Candidate skills: {resume_summary}"
         return [clean_text(combined_text)[:500]]

    try:
        role_title_match = re.search(r"^(?:Job\s+)?Title\s*[:\-]?\s*(.*?)(\n|$)", jd_summary, re.IGNORECASE | re.MULTILINE)
        role_title = role_title_match.group(1).strip() if role_title_match else "Position"

        resume_keywords = extract_keywords(resume_summary, max_keywords=8)
        jd_keywords = extract_keywords(jd_summary, max_keywords=8)
        combined_keywords = list(set(resume_keywords + jd_keywords))
        overlap_keywords = list(set(resume_keywords) & set(jd_keywords))

        queries = []
        if combined_keywords:
            queries.append(clean_text(f"{role_title} technical concepts related to {', '.join(combined_keywords[:4])}"))
        if overlap_keywords:
            queries.append(clean_text(f"Explain {overlap_keywords[0]} and {overlap_keywords[1] if len(overlap_keywords)>1 else ''} for a {role_title}"))
        if jd_keywords:
            queries.append(clean_text(f"Common interview questions about {jd_keywords[0]} for {role_title}"))
        if not queries:
            queries.append(clean_text(f"{role_title}: {jd_summary} Candidate skills: {resume_summary}")[:500])

        final_queries = list(set(q for q in queries if q))[:num_queries]
        logger.info(f"Generated {len(final_queries)} RAG search queries.")
        return final_queries
    except Exception as e:
        logger.error(f"Error generating RAG search queries: {e}", exc_info=True)
        return [clean_text(f"Job Description: {jd_summary} Resume Summary: {resume_summary}")[:500]]


def retrieve_similar_documents(query, top_k=None, threshold=None):
    """Retrieves similar documents from the RAG database using vector similarity."""
    if not config.RAG_ENABLED or rag_db_cursor is None or embedding_model is None:
        # logger.debug("RAG retrieval skipped.")
        return []

    top_k = top_k if top_k is not None else config.RETRIEVAL_TOP_K
    threshold = threshold if threshold is not None else config.RETRIEVAL_SIMILARITY_THRESHOLD

    # No point querying if top_k is 0 or less
    if top_k <= 0:
        return []

    try:
        logger.debug(f"Generating RAG embedding for query: '{query[:50]}...'")
        query_embedding = embedding_model.encode(query)

        sql_query = """
            SELECT id, content, 1 - (embedding <=> %s) AS similarity
            FROM knowledge_documents -- Ensure table name is correct!
            WHERE 1 - (embedding <=> %s) >= %s
            ORDER BY similarity DESC
            LIMIT %s;
        """
        embedding_list = query_embedding.tolist()
        rag_db_cursor.execute(sql_query, (embedding_list, embedding_list, threshold, top_k)) # Use rag_db_cursor
        results = rag_db_cursor.fetchall()

        documents = [{"id": row[0], "content": row[1], "score": row[2]} for row in results]
        logger.info(f"Retrieved {len(documents)} documents from RAG DB for query '{query[:30]}...' (Threshold: {threshold}, TopK: {top_k})")
        return documents
    except psycopg2.Error as db_err:
         if "relation \"knowledge_documents\" does not exist" in str(db_err):
             logger.error("RAG DB Error: Table 'knowledge_documents' not found. Ensure it exists in the RAG database ('%s').", config.RAG_DB_NAME)
         elif "column \"embedding\" does not exist" in str(db_err):
              logger.error("RAG DB Error: Column 'embedding' not found in 'knowledge_documents'. Ensure schema is correct.")
         elif "operator does not exist: vector <=> vector" in str(db_err):
              logger.error("RAG DB Error: <=> operator not found. Ensure the 'pgvector' extension is installed and enabled in the RAG database ('%s'). Run: CREATE EXTENSION IF NOT EXISTS vector;", config.RAG_DB_NAME)
         else:
             logger.error(f"RAG Database error during retrieval: {db_err}", exc_info=True)
         return [] # Return empty list on DB errors
    except Exception as e:
        logger.error(f"Unexpected error during RAG document retrieval: {e}", exc_info=True)
        return []


def format_rag_context(documents, max_length=None):
    if not documents:
        return "No relevant context found in the knowledge base."
    max_length = max_length if max_length is not None else config.MAX_CONTEXT_LENGTH
    context_str = "--- Relevant Context from Knowledge Base ---\n\n"
    current_length = len(context_str)
    for doc in documents:
        doc_content = f"**Source ID {doc.get('id', 'N/A')} (Similarity: {doc.get('score', 0):.2f}):**\n{doc.get('content', '')}\n\n"
        if max_length is None or (current_length + len(doc_content) <= max_length):
            context_str += doc_content
            current_length += len(doc_content)
        else:
            logger.warning(f"RAG context truncated at {max_length} characters.")
            break
    return context_str.strip()

# --- Skill/Topic Extraction ---
def get_focus_topics(resume_text, jd_text, top_n=5):
    if not NLTK_AVAILABLE or not nltk_initialized:
        logger.warning("NLTK unavailable. Cannot determine focus topics accurately.")
        return ["General skills based on JD"]
    if not resume_text or not jd_text:
        return ["Review Resume/JD"]
    try:
        logger.debug("Extracting focus topics from resume and JD...")
        resume_keywords = set(extract_keywords(resume_text, max_keywords=20))
        jd_keywords = set(extract_keywords(jd_text, max_keywords=20))
        overlap = list(resume_keywords.intersection(jd_keywords))
        if len(overlap) < top_n:
             additional_topics = [kw for kw in jd_keywords if kw not in overlap]
             overlap.extend(additional_topics[:top_n - len(overlap)])
        focus_topics = overlap[:top_n] if overlap else list(jd_keywords)[:top_n]
        if not focus_topics: return ["General technical skills"]
        logger.info(f"Identified focus topics: {focus_topics}")
        return focus_topics
    except Exception as e:
        logger.error(f"Error extracting focus topics: {e}", exc_info=True)
        return ["General technical skills"]

# --- Project Details Extraction ---
def extract_project_details(resume_text, max_length=None):
    if not resume_text: return ""
    max_length = max_length if max_length is not None else config.MAX_PROJECT_SUMMARY_LENGTH
    project_headers = [
        "projects", "personal projects", "academic projects",
        "experience", "work experience", "professional experience",
        "relevant experience"
    ]
    end_headers = [
        "skills", "technical skills", "languages", "tools", "technologies",
        "education", "certifications", "awards", "publications", "references",
        "interests", "hobbies", "contact"
    ]
    lines = resume_text.split('\n')
    extracted_details = ""
    in_project_section = False
    current_length = 0
    header_pattern = re.compile(r'^[A-Z][A-Za-z\s/]+(?:[:\-—_])?\s*$') # Simple pattern for section headers

    for line in lines:
        line_strip = line.strip()
        if not line_strip: continue
        line_lower = line_strip.lower()

        is_end_header = any(line_lower.startswith(header) for header in end_headers) and header_pattern.match(line_strip)
        if is_end_header and in_project_section: # Only stop if currently in a project section
            in_project_section = False
            logger.debug(f"Detected end header: '{line_strip}', stopping project extraction.")
            break # Stop processing lines once education/skills etc. is found

        is_project_header = any(line_lower.startswith(header) for header in project_headers) and header_pattern.match(line_strip)
        if is_project_header:
            in_project_section = True
            logger.debug(f"Entering project/experience section: '{line_strip}'")
            continue # Skip the header line itself

        if in_project_section:
            line_to_add = line_strip + "\n"
            if max_length is None or (current_length + len(line_to_add) <= max_length):
                 extracted_details += line_to_add
                 current_length += len(line_to_add)
            else:
                 logger.debug("Project details reached max length, stopping extraction for this section.")
                 in_project_section = False # Stop adding from this section

    if not extracted_details:
         logger.warning("Could not definitively identify Project/Experience sections in resume using headers.")
         # Fallback: maybe return first N characters? Or based on keywords? For now, empty.
         return ""

    logger.info(f"Extracted {len(extracted_details)} characters of potential project/experience details.")
    return extracted_details.strip()


# --- Cleanup function ---
def close_resources():
    """Closes RAG database connection if open."""
    global rag_db_connection, rag_db_cursor # Use specific names
    if rag_db_cursor:
        try:
            rag_db_cursor.close()
            logger.info("RAG Database cursor closed.")
        except Exception as e:
            logger.error(f"Error closing RAG database cursor: {e}", exc_info=True)
        rag_db_cursor = None
    if rag_db_connection:
        try:
            rag_db_connection.close()
            logger.info("RAG Database connection closed.")
        except Exception as e:
            logger.error(f"Error closing RAG database connection: {e}", exc_info=True)
        rag_db_connection = None
    logger.info("Resource cleanup attempted.")
