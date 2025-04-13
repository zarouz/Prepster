# modules/report_generator.py
import logging
import os
from datetime import datetime
import re
# Attempt to import ReportLab
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT, TA_CENTER, TA_RIGHT
    from reportlab.lib.units import inch
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    logging.getLogger(__name__).error("ReportLab library not found. Please install it (`pip install reportlab`) to generate PDF reports.")
    # Define dummy classes/functions if ReportLab is not available to avoid NameErrors later
    # Although the generate_pdf_report function will check REPORTLAB_AVAILABLE first.
    letter = None
    SimpleDocTemplate = None
    Paragraph = None
    Spacer = None
    Table = None
    TableStyle = None
    PageBreak = None
    getSampleStyleSheet = None
    ParagraphStyle = None
    colors = None
    TA_JUSTIFY = TA_LEFT = TA_CENTER = TA_RIGHT = None
    inch = None

# Local Imports
import config

logger = logging.getLogger(__name__)

# --- Report Generation ---

def generate_pdf_report(evaluated_data, resume_text, jd_text, role_title,
                        candidate_name, interviewer_name, company_name, interview_id,
                        report_filename):
    """
    Generates a PDF interview report using ReportLab.

    Args:
        evaluated_data (list): List of dictionaries, where each dict represents
                               a Q&A turn with evaluation results. Expected keys:
                               'question_turn', 'question', 'response',
                               'evaluation', 'score', 'score_justification',
                               'confidence_score', 'confidence_rating',
                               'primary_emotion', 'confidence_analysis_error',
                               'confidence_message', 'stt_success', 'stt_error_message'.
        resume_text (str): Raw text extracted from the candidate's resume.
        jd_text (str): Raw text from the job description.
        role_title (str): The job title for the interview.
        candidate_name (str): Name of the candidate.
        interviewer_name (str): Name of the AI interviewer.
        company_name (str): Name of the company.
        interview_id (str): Unique ID for the interview session.
        report_filename (str): The full path where the PDF report should be saved.

    Returns:
        bool: True if the report was generated successfully, False otherwise.
    """
    if not REPORTLAB_AVAILABLE:
        logger.error("ReportLab not installed. Cannot generate PDF report.")
        return False

    logger.info(f"Generating PDF report for Interview ID {interview_id} to {report_filename}...")

    try:
        doc = SimpleDocTemplate(report_filename, pagesize=letter,
                                topMargin=0.75 * inch, bottomMargin=0.75 * inch,
                                leftMargin=0.75 * inch, rightMargin=0.75 * inch)
        styles = getSampleStyleSheet()
        story = []

        # --- Custom Styles ---
        # Title Style
        title_style = ParagraphStyle(name='TitleStyle', parent=styles['h1'], alignment=TA_CENTER, spaceAfter=20, fontSize=18)
        # Subtitle Style
        subtitle_style = ParagraphStyle(name='SubtitleStyle', parent=styles['h2'], alignment=TA_CENTER, spaceAfter=12, fontSize=14, textColor=colors.darkblue)
        # Section Header Style
        section_header_style = ParagraphStyle(name='SectionHeader', parent=styles['h2'], spaceBefore=18, spaceAfter=10, fontSize=13, textColor=colors.darkslategray)
        # Normal Text Style (Justified)
        normal_justified = ParagraphStyle(name='NormalJustified', parent=styles['Normal'], alignment=TA_JUSTIFY, spaceAfter=6)
         # Code/Preformatted Text Style
        code_style = ParagraphStyle(name='CodeStyle', parent=styles['Code'], fontSize=9, leading=11, spaceAfter=10, leftIndent=10, rightIndent=10, backColor=colors.whitesmoke, borderPadding=5)
        # Question/Answer Labels
        q_style = ParagraphStyle(name='QuestionLabel', parent=styles['Normal'], spaceAfter=2, textColor=colors.darkred, fontName='Helvetica-Bold')
        a_style = ParagraphStyle(name='AnswerLabel', parent=styles['Normal'], spaceAfter=2, textColor=colors.darkgreen, fontName='Helvetica-Bold')
        eval_style = ParagraphStyle(name='EvalLabel', parent=styles['Normal'], spaceAfter=2, textColor=colors.darkblue, fontName='Helvetica-Bold')
        # Confidence Labels
        conf_style = ParagraphStyle(name='ConfLabel', parent=styles['Italic'], spaceAfter=2, textColor=colors.dimgray, fontSize=9)


        # --- Report Header ---
        story.append(Paragraph(f"{company_name} - Interview Report", title_style))
        story.append(Paragraph(f"Role: {role_title}", subtitle_style))
        story.append(Spacer(1, 0.2 * inch))
        header_data = [
            ['Candidate:', candidate_name, 'Date:', datetime.now().strftime("%Y-%m-%d %H:%M")],
            ['Interviewer:', interviewer_name, 'Interview ID:', interview_id[-12:]], # Show last part of ID
        ]
        header_table = Table(header_data, colWidths=[1.2 * inch, 3 * inch, 1 * inch, 2 * inch])
        header_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('ALIGN', (3, 0), (3, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 0.3 * inch))

        # --- Overall Summary Section (Calculate from evaluated data) ---
        story.append(Paragraph("Overall Performance Summary", section_header_style))
        total_score = 0
        valid_scores = 0
        valid_confidence = 0
        total_confidence = 0.0
        key_strengths = []
        key_areas_for_improvement = []

        for item in evaluated_data:
            if item.get("score") is not None:
                total_score += item["score"]
                valid_scores += 1
            if item.get("confidence_score") is not None and not item.get("confidence_analysis_error"):
                 total_confidence += item["confidence_score"]
                 valid_confidence += 1
            # Simple aggregation of strengths/weaknesses (can be improved with LLM summary later)
            eval_text = item.get("evaluation", "")
            if eval_text:
                strengths_match = re.search(r"Strengths:\s*(.*?)(?:Areas for Improvement:|Overall Score:|\Z)", eval_text, re.DOTALL | re.IGNORECASE)
                if strengths_match: key_strengths.extend(s.strip() for s in strengths_match.group(1).strip().split('*') if s.strip())
                areas_match = re.search(r"Areas for Improvement:\s*(.*?)(?:Overall Score:|\Z)", eval_text, re.DOTALL | re.IGNORECASE)
                if areas_match: key_areas_for_improvement.extend(a.strip() for a in areas_match.group(1).strip().split('*') if a.strip())

        # Deduplicate and limit summary points
        key_strengths = list(set(s for s in key_strengths if len(s) > 5))[:3]
        key_areas_for_improvement = list(set(a for a in key_areas_for_improvement if len(a) > 5))[:3]


        avg_score = total_score / valid_scores if valid_scores > 0 else "N/A"
        avg_conf = (total_confidence / valid_confidence * 100) if valid_confidence > 0 else "N/A" # Assuming score is 0-1 scale

        summary_text = f"Average Score: {avg_score:.2f}/5.0 (based on {valid_scores} evaluated responses)<br/>" if isinstance(avg_score, float) else f"Average Score: {avg_score} (no valid scores)<br/>"
        summary_text += f"Average Confidence: {avg_conf:.1f}% (based on {valid_confidence} analyzed responses)<br/>" if isinstance(avg_conf, float) else f"Average Confidence: {avg_conf} (no valid analyses)<br/>"

        if key_strengths:
             summary_text += "<br/><b>Potential Strengths Observed:</b><br/>" + "<br/>".join(f"- {s}" for s in key_strengths)
        if key_areas_for_improvement:
             summary_text += "<br/><br/><b>Potential Areas for Development:</b><br/>" + "<br/>".join(f"- {s}" for s in key_areas_for_improvement)

        story.append(Paragraph(summary_text, normal_justified))
        story.append(Spacer(1, 0.3 * inch))


        # --- Detailed Q&A Section ---
        story.append(Paragraph("Detailed Question & Answer Evaluation", section_header_style))

        for i, item in enumerate(evaluated_data):
            turn = item.get("question_turn", i + 1)
            question = item.get("question", "N/A")
            response = item.get("response", "N/A")
            evaluation = item.get("evaluation", "N/A")
            score = item.get("score", "N/A")
            justification = item.get("score_justification", "N/A")

            # Confidence/Emotion data
            conf_score = item.get('confidence_score')
            conf_rating = item.get('confidence_rating', 'N/A')
            conf_emotion = item.get('primary_emotion', 'N/A')
            conf_error = item.get('confidence_analysis_error', False)
            conf_message = item.get('confidence_message', '')

            stt_success = item.get('stt_success', True) # Assume success if key missing (legacy)
            stt_error_msg = item.get('stt_error_message', None)

            # Format confidence string
            conf_str = ""
            if not conf_error and conf_score is not None:
                conf_str = f"Confidence: {conf_score*100:.1f}% ({conf_rating}), Primary Emotion: {conf_emotion}"
            elif conf_error:
                conf_str = f"Confidence Analysis Note: {conf_message}"
            elif not stt_success:
                 conf_str = f"Confidence Analysis Skipped: {stt_error_msg or 'STT Failed'}"
            elif response == "[Audio detected - No speech recognized]":
                 conf_str = f"Confidence Analysis Skipped: No speech detected"


            story.append(Paragraph(f"<u>Turn {turn}: Question</u>", q_style))
            story.append(Paragraph(question, normal_justified))
            story.append(Spacer(1, 0.05 * inch))

            story.append(Paragraph("Candidate Response:", a_style))
            # Handle STT errors explicitly in the report
            if not stt_success:
                 story.append(Paragraph(f"<i>[STT Error: {stt_error_msg}]</i>", ParagraphStyle(name='ErrorStyle', parent=styles['Italic'], textColor=colors.red)))
            elif response == "[Audio detected - No speech recognized]":
                 story.append(Paragraph("<i>[No speech recognized in audio]</i>", styles['Italic']))
            else:
                 story.append(Paragraph(response, normal_justified))

            # Add confidence info if available
            if conf_str:
                 story.append(Paragraph(conf_str, conf_style))

            story.append(Spacer(1, 0.1 * inch))

            # Add Evaluation if STT was successful and speech was present
            if stt_success and response != "[Audio detected - No speech recognized]":
                story.append(Paragraph("Evaluation:", eval_style))
                # Check if evaluation itself had an error
                if evaluation.startswith("Evaluation Error:") or evaluation.startswith("Evaluation skipped"):
                     story.append(Paragraph(f"<i>[{evaluation}]</i>", ParagraphStyle(name='EvalErrorStyle', parent=styles['Italic'], textColor=colors.orange)))
                else:
                     # Display full evaluation, preserving line breaks from LLM output
                     eval_paragraph = Paragraph(evaluation.replace('\n', '<br/>'), normal_justified)
                     story.append(eval_paragraph)
                     # story.append(Paragraph(f"<b>Score (1-5): {score}</b>", normal_justified))
                     # story.append(Paragraph(f"Justification: {justification}", normal_justified))
            else:
                 # If STT failed or no speech, indicate no text evaluation performed
                 story.append(Paragraph("Evaluation:", eval_style))
                 reason = stt_error_msg or "No speech detected"
                 story.append(Paragraph(f"<i>[Text evaluation skipped due to: {reason}]</i>", styles['Italic']))


            story.append(Spacer(1, 0.25 * inch)) # Space between Q&A blocks

        # --- Appendix: Resume and JD Text (Optional) ---
        add_appendix = True # Control whether to add this section
        if add_appendix:
            story.append(PageBreak())
            story.append(Paragraph("Appendix A: Candidate Resume Text", section_header_style))
            # Use code style for better readability of potentially messy text
            resume_paragraph = Paragraph(resume_text.replace('\n', '<br/>'), code_style)
            story.append(resume_paragraph)

            story.append(PageBreak())
            story.append(Paragraph("Appendix B: Job Description Text", section_header_style))
            jd_paragraph = Paragraph(jd_text.replace('\n', '<br/>'), code_style)
            story.append(jd_paragraph)

        # --- Build the PDF ---
        doc.build(story)
        logger.info(f"PDF report saved successfully to {report_filename}")
        return True

    except ImportError:
        logger.error("ReportLab Error: Could not generate report due to missing library.", exc_info=True)
        return False # Should have been caught earlier, but double-check
    except Exception as e:
        logger.error(f"Failed to generate PDF report {report_filename}: {e}", exc_info=True)
        return False

# --- Regex Helper ---
# Moved the regex logic to the summary calculation part above
# import re # Already imported if needed elsewhere