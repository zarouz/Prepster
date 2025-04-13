# modules/audio_utils.py
import os
import io
import warnings
import logging
import soundfile as sf

# Local configuration import
import config

# Google Cloud STT
try:
    from google.cloud import speech as google_speech
    from google.api_core import exceptions as google_exceptions # Import exceptions
    GOOGLE_CLOUD_AVAILABLE = True
except ImportError:
    GOOGLE_CLOUD_AVAILABLE = False
    google_speech = None
    google_exceptions = None
    logging.getLogger(__name__).warning("Google Cloud Speech library not found (google-cloud-speech). STT features disabled.")

logger = logging.getLogger(__name__)

# --- Global STT Client ---
STT_CLIENT = None

# --- Initialization Function ---
def initialize_stt_client():
    """Initializes Google Cloud STT client if available."""
    global STT_CLIENT, GOOGLE_CLOUD_AVAILABLE

    if not GOOGLE_CLOUD_AVAILABLE:
        logger.warning("Google Cloud library not available. Cannot initialize STT client.")
        return False

    if STT_CLIENT is None:
        logger.info("Initializing Google STT Client...")
        if not config.GOOGLE_CLOUD_PROJECT_ID:
             logger.error("GOOGLE_CLOUD_PROJECT_ID not configured. Cannot initialize STT client.")
             STT_CLIENT = None
             GOOGLE_CLOUD_AVAILABLE = False
             return False

        # Check if GOOGLE_APPLICATION_CREDENTIALS is set and use it implicitly
        credentials_path = config.GOOGLE_APPLICATION_CREDENTIALS
        if credentials_path and os.path.exists(credentials_path):
             logger.info(f"Using GOOGLE_APPLICATION_CREDENTIALS from: {credentials_path}")
             # SpeechClient() will pick this up automatically from the environment variable set in config.py
             client_args = {}
        elif credentials_path:
             logger.warning(f"GOOGLE_APPLICATION_CREDENTIALS path specified but not found: {credentials_path}. Attempting default authentication.")
             client_args = {}
        else:
             logger.info("GOOGLE_APPLICATION_CREDENTIALS not set. Attempting default authentication (e.g., gcloud login, metadata server).")
             client_args = {}

        try:
            STT_CLIENT = google_speech.SpeechClient(**client_args)
            # Optional: Test connection with a lightweight call
            try:
                # Example: list custom classes (might require specific permissions)
                # Replace with a simpler call if needed, e.g., get project settings if API exists
                iterator = STT_CLIENT.list_custom_classes(parent=f"projects/{config.GOOGLE_CLOUD_PROJECT_ID}/locations/global")
                _ = list(iterator) # Consume iterator to trigger API call
                logger.info("STT client connection test successful.")
            except google_exceptions.PermissionDenied:
                 logger.warning("STT client connection test failed: Permission Denied. Check IAM roles for the credentials.")
                 # Continue initialization, but warn user.
            except google_exceptions.NotFound:
                 logger.info("STT client connection test endpoint (list_custom_classes) not found or project ID invalid? Continuing init.")
                 # Continue, maybe the main STT call will work.
            except Exception as test_err:
                 logger.error(f"STT client connection test failed: {test_err}. Check project ID, API status, network, and credentials.")
                 # Potentially critical, maybe mark as failed?
                 # STT_CLIENT = None
                 # GOOGLE_CLOUD_AVAILABLE = False
                 # return False
                 logger.warning("Continuing STT client initialization despite connection test failure.")


            logger.info("Google Speech-to-Text client initialized.")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Google STT client: {e}", exc_info=True)
            warnings.warn(f"Could not initialize Google STT Client: {e}. STT features may fail.")
            STT_CLIENT = None
            GOOGLE_CLOUD_AVAILABLE = False # Mark as unavailable on init failure
            return False
    return True # Already initialized

# --- File-Based STT Function ---
# (Keep transcribe_audio_file_google function exactly as it was in your provided code)
def transcribe_audio_file_google(audio_path):
    """
    Transcribes an audio file using Google Cloud Speech-to-Text.

    Args:
        audio_path (str): The path to the audio file.

    Returns:
        tuple: (transcript_text, error_message)
               transcript_text (str): The transcribed text, or message like "[No speech recognized]", or None if a critical error occurred.
               error_message (str): An error message if transcription failed critically, None otherwise.
    """
    global STT_CLIENT
    if not GOOGLE_CLOUD_AVAILABLE or STT_CLIENT is None:
        err = "STT client not available or not initialized."
        logger.error(err)
        return None, err

    if not audio_path or not os.path.exists(audio_path):
        err = f"Audio file not found: '{audio_path}'"
        logger.error(err)
        return None, err

    logger.info(f"Transcribing audio file via Google STT: {os.path.basename(audio_path)}")
    try:
        # Get audio file information (samplerate)
        try:
            info = sf.info(audio_path)
            file_samplerate = info.samplerate
            file_channels = info.channels
            file_format = info.format.lower()
            subtype = info.subtype.lower()
            encoding = google_speech.RecognitionConfig.AudioEncoding.ENCODING_UNSPECIFIED # Default

            # Simplified encoding detection (add more as needed)
            if 'wav' in file_format:
                if 'pcm_16' in subtype or 'linear16' in subtype:
                    encoding = google_speech.RecognitionConfig.AudioEncoding.LINEAR16
                elif 'pcm_u8' in subtype or 'ulaw' in subtype:
                    encoding = google_speech.RecognitionConfig.AudioEncoding.MULAW
            elif 'flac' in file_format:
                 encoding = google_speech.RecognitionConfig.AudioEncoding.FLAC
            elif 'opus' in subtype:
                 if 'ogg' in file_format:
                      encoding = google_speech.RecognitionConfig.AudioEncoding.OGG_OPUS
                 elif 'webm' in file_format:
                      encoding = google_speech.RecognitionConfig.AudioEncoding.WEBM_OPUS # Use specific WEBM if available
                      # Fallback if WEBM_OPUS isn't recognized by the library version
                      # encoding = google_speech.RecognitionConfig.AudioEncoding.OGG_OPUS
                      # logger.info("Detected WEBM/Opus, using OGG_OPUS encoding for STT.")
                 else:
                      logger.warning(f"Opus subtype in unknown container: {file_format}. Using OGG_OPUS.")
                      encoding = google_speech.RecognitionConfig.AudioEncoding.OGG_OPUS # Fallback
            # Add MP3, AMR etc. if required

            logger.debug(f"Audio Info - SR: {file_samplerate}Hz, Ch: {file_channels}, Format: {file_format}/{subtype}, Encoding: {encoding} for {os.path.basename(audio_path)}")

            if file_channels > 1:
                 logger.warning(f"Audio file has {file_channels} channels. STT prefers mono. Results may vary.")

            # Check sample rate (optional, API often handles resampling)
            # if file_samplerate not in [8000, 16000, 44100, 48000] and encoding not in [google_speech.RecognitionConfig.AudioEncoding.OGG_OPUS, google_speech.RecognitionConfig.AudioEncoding.WEBM_OPUS]:
            #     logger.warning(f"Audio sample rate ({file_samplerate}Hz) might not be optimal. Consider resampling to {config.DEFAULT_AUDIO_SAMPLERATE}Hz.")

        except Exception as sf_err:
            # Fallback if soundfile fails
            file_samplerate = config.DEFAULT_AUDIO_SAMPLERATE
            encoding = google_speech.RecognitionConfig.AudioEncoding.ENCODING_UNSPECIFIED
            logger.warning(f"Cannot read audio info from '{os.path.basename(audio_path)}': {sf_err}. Using default SR {file_samplerate}Hz and unspecified encoding.")

        # Read audio content
        with io.open(audio_path, "rb") as audio_file:
            content = audio_file.read()
        if not content:
            err = f"Audio file is empty: '{os.path.basename(audio_path)}'"
            logger.error(err)
            return None, err

        audio = google_speech.RecognitionAudio(content=content)

        # Configure recognition settings
        recognition_config_args = {
            "language_code": config.GOOGLE_STT_LANGUAGE_CODE,
            "sample_rate_hertz": file_samplerate,
            "enable_automatic_punctuation": True,
            # "model": "telephony", # Example model selection
            # "audio_channel_count": 1, # Explicitly state mono if converted
        }
        if encoding != google_speech.RecognitionConfig.AudioEncoding.ENCODING_UNSPECIFIED:
            recognition_config_args["encoding"] = encoding
        recognition_config = google_speech.RecognitionConfig(**recognition_config_args)

        logger.info(f"Sending STT request for {os.path.basename(audio_path)} (Size: {len(content)} bytes, Config: {recognition_config_args})...")
        response = STT_CLIENT.recognize(config=recognition_config, audio=audio)
        logger.info(f"Received STT response for {os.path.basename(audio_path)}.")

        # Process response
        if not response.results or not response.results[0].alternatives:
            msg = "[Audio detected - No speech recognized]"
            logger.warning(f"STT: {msg} for file {os.path.basename(audio_path)}")
            return msg, None # Indicate no speech recognized

        # Get the most likely transcript
        transcript = response.results[0].alternatives[0].transcript.strip()
        confidence = response.results[0].alternatives[0].confidence

        if not transcript:
            msg = "[Audio detected - Empty transcript]" # Different from no speech
            logger.warning(f"STT: {msg} for {os.path.basename(audio_path)}")
            return msg, None

        logger.info(f"STT successful (Conf: {confidence:.2f}): '{transcript[:80]}...'")
        return transcript, None

    except google_exceptions.PermissionDenied as perm_err:
        err = f"STT Permission Denied: {perm_err}. Check credentials/API permissions."
        logger.error(err)
        return None, err
    except google_exceptions.InvalidArgument as arg_err:
         err = f"STT Invalid Argument: {arg_err}. Check sample rate ({file_samplerate}), encoding ({encoding}), or audio format."
         logger.error(err)
         return None, err
    except google_exceptions.GoogleAPICallError as api_err:
         err = f"STT API Call Error: {api_err}. Check quota, network, or API status."
         logger.error(err)
         return None, err
    except AttributeError as attr_err:
        # Handle potential issues if google_speech components are missing
        err = f"Google Speech library components unavailable or STT client issue: {attr_err}"
        logger.error(err, exc_info=True)
        return None, err
    except Exception as e:
        err = f"Unexpected error during STT for {os.path.basename(audio_path)}: {e}"
        logger.error(err, exc_info=True)
        return None, err