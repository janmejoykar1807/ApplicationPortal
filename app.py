# app.py — Email-only storage (resume + optional cover letter attachments)
import os
import re
import time
import smtplib
import mimetypes
from datetime import datetime
from email.message import EmailMessage
from typing import Optional, List, Tuple

import streamlit as st

# =============================
# Config & Secrets
# =============================
def get_secret(key: str, default: Optional[str] = None) -> Optional[str]:
    try:
        val = st.secrets.get(key, None)
    except Exception:
        val = None
    return val if val is not None else os.getenv(key, default)

APP_TITLE = get_secret("APP_TITLE", "Job Application Portal")
HR_EMAIL  = get_secret("HR_EMAIL", "hr@example.com")

SMTP_HOST = get_secret("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(get_secret("SMTP_PORT", "465"))  # SSL by default
SMTP_USER = get_secret("SMTP_USER", "")
SMTP_PASS = get_secret("SMTP_PASS", "")

FROM_NAME  = get_secret("FROM_NAME", "Recruiting Team")
FROM_EMAIL = get_secret("FROM_EMAIL", SMTP_USER or "no-reply@example.com")

# =============================
# Utilities
# =============================
EMAIL_REGEX = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

def is_email(s: str) -> bool:
    return bool(EMAIL_REGEX.match((s or "").strip()))

def create_app_id() -> str:
    return f"APP-{int(time.time())}"

def _mime_from_filename(filename: str) -> Tuple[str, str]:
    """Return (maintype, subtype) guessed from filename."""
    guessed, _ = mimetypes.guess_type(filename)
    if not guessed:
        return ("application", "octet-stream")
    maintype, subtype = guessed.split("/", 1)
    return maintype, subtype

def send_email(subject: str,
               body: str,
               to_email: str,
               attachments: Optional[List[Tuple[bytes, str]]] = None,  # list of (data, filename)
               reply_to: Optional[str] = None):
    """Send an email with optional multiple attachments."""
    if not (SMTP_HOST and SMTP_PORT and SMTP_USER and SMTP_PASS and FROM_EMAIL):
        raise RuntimeError("SMTP not configured. Set SMTP_* and FROM_EMAIL in Secrets/env.")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{FROM_NAME} <{FROM_EMAIL}>"
    msg["To"] = to_email
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(body)

    if attachments:
        for data, fname in attachments:
            maintype, subtype = _mime_from_filename(fname)
            msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=fname)

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.login(SMTP_USER, SMTP_PASS)
        smtp.send_message(msg)

# =============================
# UI
# =============================
st.set_page_config(page_title=APP_TITLE, page_icon="📝", layout="centered")
st.title(APP_TITLE)
st.caption("Submit your application below. Fields marked with * are required.")

# Referral toggle OUTSIDE the form for instant show/hide
st.subheader("Referral")
st.checkbox("I was referred by an employee", key="referred_toggle")

with st.form("job_application_form", clear_on_submit=False):
    st.subheader("Applicant Details")
    col1, col2 = st.columns(2)
    with col1:
        full_name = st.text_input("Full Name *", key="full_name")
        email = st.text_input("Email *", key="email")
        phone = st.text_input("Phone *", key="phone")
        position = st.text_input("Position Applying For *", key="position")
        years_experience = st.number_input(
            "Years of Experience *",
            min_value=0.0,
            value=0.0,
            step=0.1,
            format="%g",          # shows 0 (not 0.0); 1.5 shows as 1.5
            key="years_experience"
        )
    with col2:
        expected_salary = st.text_input("Expected Salary (e.g., 120000 or 12 LPA)", key="expected_salary")
        location = st.text_input("Current Location", key="location")
        linkedin = st.text_input("LinkedIn URL", key="linkedin")
        notes = st.text_area("Notes", key="notes")

    st.subheader("Resume (PDF) *")
    resume_file = st.file_uploader("Upload Resume (PDF only) *", type=["pdf"], key="resume_file")

    st.subheader("Cover Letter (optional)")
    cover_letter_file = st.file_uploader(
        "Upload Cover Letter (PDF, DOC, or DOCX)",
        type=["pdf", "doc", "docx"],
        key="cover_letter_file"
    )

    referred = st.session_state.get("referred_toggle", False)
    ref_name = ref_emp_id = ref_email = ""
    if referred:
        st.markdown("**Referrer details**")
        ref_name   = st.text_input("Referrer Name *", key="ref_name")
        ref_emp_id = st.text_input("Referrer Employee ID *", key="ref_emp_id")
        ref_email  = st.text_input("Referrer Email *", key="ref_email")

    st.divider()
    consent = st.checkbox("I consent to the processing of my data for recruitment purposes. *", key="consent")

    submitted = st.form_submit_button("Submit Application")

# =============================
# Submission
# =============================
if submitted:
    errors = []

    # Read inputs
    full_name = (st.session_state.get("full_name") or "").strip()
    email = (st.session_state.get("email") or "").strip()
    phone = (st.session_state.get("phone") or "").strip()
    position = (st.session_state.get("position") or "").strip()

    years_experience = float(st.session_state.get("years_experience", 0.0))
    years_experience = max(0.0, round(years_experience, 1))  # normalize to 1 decimal

    expected_salary = (st.session_state.get("expected_salary") or "").strip()
    location = (st.session_state.get("location") or "").strip()
    linkedin = (st.session_state.get("linkedin") or "").strip()
    notes = (st.session_state.get("notes") or "").strip()
    consent = bool(st.session_state.get("consent", False))

    referred = bool(st.session_state.get("referred_toggle", False))
    ref_name = (st.session_state.get("ref_name") or "").strip() if referred else ""
    ref_emp_id = (st.session_state.get("ref_emp_id") or "").strip() if referred else ""
    ref_email = (st.session_state.get("ref_email") or "").strip() if referred else ""

    # Validate requireds
    if not full_name:
        errors.append("Full Name is required.")
    if not is_email(email):
        errors.append("Valid Email is required.")
    if not position:
        errors.append("Position is required.")
    if resume_file is None:
        errors.append("Resume PDF is required.")
    if not consent:
        errors.append("Consent is required to submit the application.")

    # File validations
    if resume_file and resume_file.type != "application/pdf":
        errors.append("Resume must be a PDF file.")
    if cover_letter_file:
        # basic extension check (Streamlit already restricts types)
        cl_name = cover_letter_file.name.lower()
        if not (cl_name.endswith(".pdf") or cl_name.endswith(".doc") or cl_name.endswith(".docx")):
            errors.append("Cover Letter must be a PDF, DOC, or DOCX file.")

    # Referral validations
    if referred:
        if not ref_name:
            errors.append("Referrer Name is required.")
        if not ref_emp_id:
            errors.append("Referrer Employee ID is required.")
        if not is_email(ref_email):
            errors.append("Valid Referrer Email is required.")

    if errors:
        for e in errors:
            st.error(e)
        st.stop()

    # Build IDs and read files (no saving to disk)
    app_id = create_app_id()
    resume_bytes = resume_file.read()
    resume_name = f"{app_id}_resume.pdf"

    cover_bytes = None
    cover_name = None
    if cover_letter_file:
        cover_bytes = cover_letter_file.read()
        # Keep original extension for correct MIME
        ext = os.path.splitext(cover_letter_file.name)[1].lower() or ".pdf"
        cover_name = f"{app_id}_cover_letter{ext}"

    # Email texts
    applicant_subject = f"Application Submitted Successfully — {app_id}"
    applicant_body = (
        f"Hi {full_name},\n\n"
        f"Thanks for applying for the {position} role. We’ve received your application (ID: {app_id}).\n"
        f"Our team will review it and get back to you.\n\n"
        f"Best,\n{FROM_NAME}"
    )

    hr_lines = [
        f"Application ID: {app_id}",
        f"Submitted (UTC): {datetime.utcnow().isoformat()}Z",
        f"Name: {full_name}",
        f"Email: {email}",
        f"Phone: {phone}",
        f"Position: {position}",
        f"Experience (yrs): {years_experience}",
        f"Expected Salary: {expected_salary}",
        f"Location: {location}",
        f"LinkedIn: {linkedin}",
        f"Referred: {'Yes' if referred else 'No'}",
        f"Cover Letter Uploaded: {'Yes' if cover_bytes else 'No'}",
    ]
    if referred:
        hr_lines += [
            f"Referrer Name: {ref_name}",
            f"Referrer Emp ID: {ref_emp_id}",
            f"Referrer Email: {ref_email}",
        ]
    if notes:
        hr_lines += ["", "Notes:", notes]

    hr_subject = f"[New Application] {full_name} — {position} — {app_id}"
    hr_body = "\n".join(hr_lines)

    ref_subject = f"You Referred an Applicant — {full_name} for {position} ({app_id})"
    ref_body = (
        f"Hello {ref_name},\n\n"
        f"This is to notify you that {full_name} has submitted an application for the {position} role and listed you as a referrer.\n"
        f"Application ID: {app_id}\n\n"
        f"Best,\n{FROM_NAME}"
    )

    # Send emails (HR gets resume + optional cover letter attachments)
    try:
        # Applicant confirmation
        send_email(applicant_subject, applicant_body, email, reply_to=HR_EMAIL)

        # Build HR attachments
        hr_attachments: List[Tuple[bytes, str]] = [(resume_bytes, resume_name)]
        if cover_bytes and cover_name:
            hr_attachments.append((cover_bytes, cover_name))

        # HR notification
        send_email(hr_subject, hr_body, HR_EMAIL, attachments=hr_attachments)

        # Referrer (optional)
        if referred and ref_email:
            send_email(ref_subject, ref_body, ref_email)

        st.success(f"Application submitted! Your ID is **{app_id}**.")
        st.info("A confirmation email has been sent to you. HR has also been notified."
                + (" The referring employee was notified as well." if referred else ""))

        with st.expander("View submission summary"):
            st.json({
                "app_id": app_id,
                "full_name": full_name,
                "email": email,
                "phone": phone,
                "position": position,
                "years_experience": years_experience,
                "expected_salary": expected_salary,
                "location": location,
                "linkedin": linkedin,
                "referred": "Yes" if referred else "No",
                "ref_name": ref_name,
                "ref_emp_id": ref_emp_id,
                "ref_email": ref_email,
                "cover_letter_uploaded": "Yes" if cover_bytes else "No",
                "notes_present": "Yes" if notes else "No"
            })

    except Exception as ex:
        st.error(f"Emails could not be sent: {ex}")
        st.stop()

st.caption(f"© {datetime.now().year} — {FROM_NAME or 'Recruiting Team'}")
