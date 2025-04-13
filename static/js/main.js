// --- Global Variables (Keep existing ones like mediaRecorder, audioChunks, etc.) ---
let mediaRecorder;
let audioChunks = [];
let interviewId = null;
let audioBlob = null; // To store the final Blob

// --- DOM Element References (Update these!) ---
// Get references to the elements using their IDs from the updated HTML
const startForm = document.getElementById('startForm'); // This ID should exist in the HTML
const interviewControlsDiv = document.getElementById('interviewControls'); // The div holding controls/text
const aiMessageTextElement = document.getElementById('aiMessageText');
const recordButton = document.getElementById('recordButton');
const stopButton = document.getElementById('stopButton');
const getReportButton = document.getElementById('getReportButton');
const statusElement = document.getElementById('status');
const errorDisplayElement = document.getElementById('errorDisplay');
const audioPlaybackElement = document.getElementById('audioPlayback');
// Input fields (if needed directly)
const resumeInput = document.getElementById('resume');
const jdInput = document.getElementById('job_description');

// --- Utility Functions (Keep existing ones like displayError, updateStatus) ---
function displayError(message) {
    if (errorDisplayElement) {
        errorDisplayElement.textContent = message;
        errorDisplayElement.style.display = 'block'; // Show error area
    } else {
        console.error("Error display element not found!");
    }
    console.error("Error:", message); // Also log to console
}

function clearError() {
    if (errorDisplayElement) {
        errorDisplayElement.textContent = '';
        errorDisplayElement.style.display = 'none'; // Hide error area
    }
}

function updateStatus(message) {
    if (statusElement) {
        statusElement.textContent = `Status: ${message}`;
    } else {
        console.warn("Status element not found!");
    }
}

// --- Core Interview Logic Functions ---

// Function to handle the submission of the initial setup form
async function handleStartInterview(event) {
    event.preventDefault(); // Prevent default form submission (page reload)
    clearError();
    updateStatus("Initializing interview...");

    // Disable form temporarily
    const submitButton = startForm ? startForm.querySelector('button[type="submit"]') : null;
    if (submitButton) submitButton.disabled = true;


    // Validate inputs (basic)
    if (!resumeInput || !resumeInput.files || resumeInput.files.length === 0) {
        displayError("Please select a resume file (PDF).");
        if (submitButton) submitButton.disabled = false;
        updateStatus("Initialization failed.");
        return;
    }
     if (!jdInput || !jdInput.value.trim()) {
        displayError("Please paste the job description.");
        if (submitButton) submitButton.disabled = false;
        updateStatus("Initialization failed.");
        return;
    }

    const formData = new FormData(startForm); // Get form data

    try {
        const response = await fetch('/start-interview', {
            method: 'POST',
            body: formData, // Send form data including the file
        });

        const data = await response.json();

        if (!response.ok) {
             // Handle specific errors like 400, 413, 500
            throw new Error(data.error || `HTTP error! status: ${response.status}`);
        }

        // --- SUCCESS ---
        interviewId = data.interview_id;
        updateStatus("Interview initialized. Waiting for greeting...");
        console.log("Interview started with ID:", interviewId);

        // Hide the setup form and show the interview controls
        if (startForm) startForm.style.display = 'none';
        if (interviewControlsDiv) interviewControlsDiv.style.display = 'block';

        // Automatically fetch the first AI message (greeting)
        fetchAiMessage();

    } catch (error) {
        displayError(`Initialization failed: ${error.message}`);
        updateStatus("Initialization failed.");
        // Re-enable form on error
         if (submitButton) submitButton.disabled = false;
    }
}

// Function to fetch the next AI message
async function fetchAiMessage() {
    if (!interviewId) {
        displayError("No active interview ID.");
        return;
    }
    updateStatus("Getting AI message...");
    clearError(); // Clear previous errors

    try {
        const response = await fetch('/get-ai-message');
        const data = await response.json();

        if (!response.ok || data.error) {
             throw new Error(data.error || `HTTP error! status: ${response.status}`);
        }

        // Display AI message
        if (aiMessageTextElement) {
            aiMessageTextElement.textContent = `AI: ${data.ai_message}`;
        } else {
            console.error("AI message text element not found!");
        }

        // Update UI based on interview state
        updateInterviewUI(data.status); // Pass the state received from backend

    } catch (error) {
        displayError(`Error fetching AI message: ${error.message}`);
        updateStatus("Error getting message.");
        // Decide how to handle UI on error (e.g., disable recording?)
        updateInterviewUI('ERROR'); // Assume error state for UI
    }
}

// --- Audio Recording Functions (Keep existing startRecording, stopRecording) ---
async function startRecording() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        displayError("Microphone access (getUserMedia) not supported by your browser.");
        return;
    }
    clearError();
    audioChunks = []; // Reset chunks

    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        // Determine mimeType - Check browser support
        const options = { mimeType: 'audio/webm;codecs=opus' }; // Prefer webm/opus
         if (!MediaRecorder.isTypeSupported(options.mimeType)) {
            console.warn(`${options.mimeType} not supported, trying audio/ogg...`);
            options.mimeType = 'audio/ogg;codecs=opus';
            if (!MediaRecorder.isTypeSupported(options.mimeType)) {
                 console.warn(`${options.mimeType} not supported, trying default...`);
                 delete options.mimeType; // Use browser default
            }
        }

        mediaRecorder = new MediaRecorder(stream, options);

        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                audioChunks.push(event.data);
            }
        };

        mediaRecorder.onstop = async () => {
            audioBlob = new Blob(audioChunks, { type: mediaRecorder.mimeType || 'audio/webm' }); // Use recorded mimeType or default
             console.log("Recording stopped. Blob size:", audioBlob.size, "Type:", audioBlob.type);
            // Optional: Provide playback
            if (audioPlaybackElement) {
                const audioUrl = URL.createObjectURL(audioBlob);
                audioPlaybackElement.src = audioUrl;
                audioPlaybackElement.style.display = 'block';
            }
            // Automatically submit after stopping
            await submitAudioResponse();

            // Stop microphone tracks
            stream.getTracks().forEach(track => track.stop());
        };

        mediaRecorder.onerror = (event) => {
            displayError(`Recorder Error: ${event.error.name} - ${event.error.message}`);
            updateStatus("Recording error.");
            // Update UI state if needed
            if (recordButton) recordButton.disabled = true;
            if (stopButton) stopButton.disabled = true;
        };

        mediaRecorder.start();
        updateStatus("Recording...");
        if (recordButton) recordButton.disabled = true;
        if (stopButton) stopButton.disabled = false; // Enable stop button

    } catch (err) {
        displayError(`Microphone Error: ${err.name} - ${err.message}. Please ensure microphone access is granted.`);
        updateStatus("Mic error.");
    }
}

function stopRecording() {
    if (mediaRecorder && mediaRecorder.state === "recording") {
        mediaRecorder.stop(); // This will trigger the 'onstop' event
        updateStatus("Processing recording...");
        if (stopButton) stopButton.disabled = true; // Disable stop button immediately
        // Record button remains disabled until next AI turn makes state AWAITING_RESPONSE
    } else {
        console.warn("Stop recording called but recorder not active.");
    }
}


// Function to submit the recorded audio
async function submitAudioResponse() {
    if (!audioBlob || audioBlob.size === 0) {
        displayError("No audio recorded or recording is empty.");
        updateStatus("Submission failed.");
        // Consider re-enabling record button if appropriate for the flow
        // updateInterviewUI('AWAITING_RESPONSE'); // Or based on actual state
        return;
    }
    if (!interviewId) {
         displayError("No active interview ID for submission.");
         updateStatus("Submission failed.");
         return;
    }

    updateStatus("Submitting response...");
    clearError();

    const formData = new FormData();
    // Use a filename that the backend might expect or find useful
    const filename = `interview_${interviewId}_response.webm`; // Example filename
    formData.append('audio_data', audioBlob, filename);

    try {
        const response = await fetch('/submit-response', {
            method: 'POST',
            body: formData,
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || `HTTP error! status: ${response.status}`);
        }

        // --- SUCCESS ---
        updateStatus("Response submitted. Waiting for next AI message...");
        console.log("Audio submitted successfully.");
        if (audioPlaybackElement) audioPlaybackElement.style.display = 'none'; // Hide player after successful submit
        audioBlob = null; // Clear blob after submission

        // Fetch the next AI message automatically
        fetchAiMessage();

    } catch (error) {
        displayError(`Submission failed: ${error.message}`);
        updateStatus("Submission failed.");
        // Decide how to handle UI - maybe allow recording again?
        // This depends on whether backend state changed despite error
        // Best might be to fetch status again or rely on next fetchAiMessage
         updateInterviewUI('AWAITING_RESPONSE'); // Tentatively allow retry
    }
}

// --- Report Function (Keep existing getReport) ---
async function getReport() {
    if (!interviewId) {
        displayError("No active interview ID to get report for.");
        return;
    }
    updateStatus("Generating report...");
    clearError();
    if (getReportButton) getReportButton.disabled = true; // Disable while fetching

    try {
        const response = await fetch('/get-report');

        if (!response.ok) {
             // Try to get error message from JSON response if available
             let errorMsg = `Report generation failed with status: ${response.status}`;
             try {
                const data = await response.json();
                errorMsg = data.error || errorMsg;
             } catch(jsonError) {
                 // Ignore if response wasn't JSON
             }
            throw new Error(errorMsg);
        }

        // Handle PDF download
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        // Extract filename from Content-Disposition header if possible, otherwise use default
        const disposition = response.headers.get('Content-Disposition');
        let filename = `interview_report_${interviewId}.pdf`; // Default
        if (disposition && disposition.indexOf('attachment') !== -1) {
            const filenameRegex = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/;
            const matches = filenameRegex.exec(disposition);
            if (matches != null && matches[1]) {
            filename = matches[1].replace(/['"]/g, '');
            }
        }
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);

        updateStatus("Report downloaded.");


    } catch (error) {
        displayError(`Failed to get report: ${error.message}`);
        updateStatus("Report generation failed.");
    } finally {
         // Re-enable button only if state allows (e.g., FINISHED)
         // We need to know the state again. Let's assume it's still FINISHED
         // A better approach might be to fetch state again after report attempt.
         updateInterviewUI('FINISHED');
    }
}


// --- UI State Management ---
function updateInterviewUI(state) {
     console.log("Updating UI for state:", state); // Log current state
     updateStatus(state); // Update the status text

    // Ensure elements exist before trying to set properties
    const controlsExist = recordButton && stopButton && getReportButton;
    if (!controlsExist) {
        console.warn("One or more control buttons not found. Cannot update UI.");
        return;
    }

    switch (state) {
        case 'INITIALIZING':
        case 'READY': // After initialization, before greeting
            recordButton.disabled = true;
            stopButton.disabled = true;
            getReportButton.disabled = true;
            if (startForm) startForm.style.display = 'none'; // Hide form
             if (interviewControlsDiv) interviewControlsDiv.style.display = 'block'; // Show controls
            break;
        case 'AWAITING_RESPONSE': // AI has asked a question, waiting for user
            recordButton.disabled = false; // Enable recording
            stopButton.disabled = true;
            getReportButton.disabled = true;
            if (startForm) startForm.style.display = 'none';
             if (interviewControlsDiv) interviewControlsDiv.style.display = 'block';
            break;
        case 'IN_PROGRESS': // User has recorded, backend is processing
        case 'ASKING': // Backend is generating AI response
        case 'EVALUATING': // Backend is evaluating after finish
            recordButton.disabled = true;
            stopButton.disabled = true;
            getReportButton.disabled = true;
             if (startForm) startForm.style.display = 'none';
             if (interviewControlsDiv) interviewControlsDiv.style.display = 'block';
            break;
         case 'RECORDING': // Custom state used only by frontend during recording
             recordButton.disabled = true;
             stopButton.disabled = false; // Stop should be enabled
             getReportButton.disabled = true;
             if (startForm) startForm.style.display = 'none';
             if (interviewControlsDiv) interviewControlsDiv.style.display = 'block';
            break;
        case 'FINISHED': // Interview complete, evaluation may or may not be done
            recordButton.disabled = true;
            stopButton.disabled = true;
            getReportButton.disabled = false; // Enable report download
            if (startForm) startForm.style.display = 'none';
             if (interviewControlsDiv) interviewControlsDiv.style.display = 'block';
            break;
        case 'ERROR':
             // Decide how to handle errors - often disable most actions
             recordButton.disabled = true;
             stopButton.disabled = true;
             getReportButton.disabled = true; // Or maybe allow report if finished before error?
             if (startForm) startForm.style.display = 'block'; // Show form again? Or keep controls visible?
             if (interviewControlsDiv) interviewControlsDiv.style.display = 'block'; // Keep controls visible to show error context
            break;
        default: // Initial page load state before interaction
            recordButton.disabled = true;
            stopButton.disabled = true;
            getReportButton.disabled = true;
             if (startForm) startForm.style.display = 'block'; // Show form initially
            if (interviewControlsDiv) interviewControlsDiv.style.display = 'none'; // Hide controls initially
            updateStatus("Idle"); // Set initial status text
    }
}


// --- Event Listeners ---
document.addEventListener('DOMContentLoaded', () => {
    console.log("DOM fully loaded and parsed");

    // Check if elements exist right away
    if (!startForm) {
        console.error("Setup form ('startForm') not found on DOM load!");
    }
     if (!interviewControlsDiv) {
        console.error("Interview controls container ('interviewControls') not found on DOM load!");
     }
    if (!aiMessageTextElement || !recordButton || !stopButton || !getReportButton || !statusElement || !errorDisplayElement || !audioPlaybackElement) {
         console.error("One or more essential interview control elements are missing!");
    }

    // Attach event listener to the form
    if (startForm) {
        startForm.addEventListener('submit', handleStartInterview);
        console.log("Event listener attached to startForm.");
    } else {
        // Logged error above is sufficient
    }

    // Attach listeners to buttons (ensure they exist first)
    if (recordButton) {
        recordButton.addEventListener('click', startRecording);
    }
    if (stopButton) {
        stopButton.addEventListener('click', stopRecording);
    }
    if (getReportButton) {
        getReportButton.addEventListener('click', getReport);
    }

    // Set initial UI state
    updateInterviewUI('INITIAL'); // Or whatever your very first state is called

}); // End DOMContentLoaded

console.log("main.js script loaded"); // Log script load