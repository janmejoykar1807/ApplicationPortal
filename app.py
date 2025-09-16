# app.py
import os
import re
import csv
import time
import pathlib
import smtplib
from datetime import datetime
from email.message import EmailMessage
from typing import Optional

import streamlit as st

# -----------------------------
# Configuration & Secrets
# -----------------------------
def get_secret(key: str, default: Optional[str] = None) -> Optional[str]:
    # Prefer Streamlit Secrets, then Env Vars, then default
    try:
        return st.secrets.get(key, os.getenv(key, default))
    except Exception:
        return os.getenv(key, default)

APP_TITLE = get_secret("APP_TITLE", "Job Application Portal")
HR_EMAIL = get_secret("HR_EMAIL", "hr@example.com")  # <- change or set in secrets
SMTP_HOST = get_secret("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(get_secret("SMTP_PORT", "465"))  # SSL port
SMTP_USER = get_secret("SMTP_USER", "your_smtp_username@example.com")
SMTP_PASS = get_secret("SMTP_PASS", "your_smtp_password_or_app_password")
FROM_NAME = get_secret("FROM_NAME", "Recruiting Team")
FROM_EMAIL = get_secret("FROM_EMAIL", SMTP_USER or "no-reply@example.com")

SAVE_DIR = pathlib.Path(get_secret("SAVE_DIR", "submissions"))
SAVE_DIR.mkdir(parents=True, exist_ok=True)
CSV_PATH = SAVE_DIR / "applications.csv"

# -----------------------------
# Utilities
# -----------------------------
EMAIL_REGEX = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

def is_email(s: str) -> bool:
    return bool(EMAIL_REGEX.match((s or "").strip()))

def sanitize_filename(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", s.strip())[:80]

def create_app_id() -> str:
    return f"APP-{int(time.time())}"

def write_csv_header_if_needed(path: pathlib.Path):
    if not path.exists():
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "app_id", "timestamp_iso", "full_name", "email", "phone",
                "position", "years_experience", "expected_salary", "location",
                "linkedin", "cover_letter",
                "referred", "ref_name", "ref_emp_id", "ref_email",
                "resume_filename"
            ])

def append_application_row(**kwargs):
    write_csv_header_if_needed(CSV_PATH)
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            kwargs.get("app_id"),
            kwargs.get("timestamp_iso"),
            kwargs.get("full_name"),
            kwargs.get("email"),
            kwargs.get("phone"),
            kwargs.get("position"),
            kwargs.get("years_experience"),
            kwargs.get("expected_salary"),
            kwargs.get("location"),
            kwargs.get("linkedin"),
            kwargs.get("cover_letter"),
            kwargs.get("referred"),
            kwargs.get("ref_name"),
            kwargs.get("ref_emp_id"),
            kwargs.get("ref_email"),
            kwargs.get("resume_filename"),
        ])

def send_email(subject: str, body: str, to_email: str, attachment: Optional[bytes] = None, attachment_name: Optional[str] = None):
    if not (SMTP_HOST and SMTP_PORT and SMTP_USER and SMTP_PASS and FROM_EMAIL):
        raise RuntimeError("SMTP is not configured. Set SMTP_* and FROM_EMAIL in Streamlit secrets or environment variables.")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{FROM_NAME} <{FROM_EMAIL}>"
    msg["To"] = to_email
    msg.set_content(body)

    if attachment and attachment_name:
        # Attach PDF resume
        msg.add_attachment(attachment, maintype="application", subtype="pdf", filename=attachment_name)

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.login(SMTP_USER, SMTP_PASS)
        smtp.send_message(msg)

# -----------------------------
# UI
# -----------------------------
st.set_page_config(page_title=APP_TITLE, page_icon="📝", layout="centered")
st.title(APP_TITLE)
st.caption("Submit your application below. Fields marked with * are required.")

with st.form("job_application_form", clear_on_submit=False):
    st.subheader("Applicant Details")
    col1, col2 = st.columns(2)
    with col1:
        full_name = st.text_input("Full Name *")
        email = st.text_input("Email *")
        phone = st.text_input("Phone *")
        position = st.text_input("Position Applying For *")
        years_experience = st.number_input("Years of Experience *", min_value=0.0, step=0.5)
    with col2:
        expected_salary = st.text_input("Expected Salary (e.g., 120000 or 12 LPA)")
        location = st.text_input("Current Location")
        linkedin = st.text_input("LinkedIn URL")
        cover_letter = st.text_area("Cover Letter / Notes")

    st.subheader("Resume")
    resume_file = st.file_uploader("Upload Resume (PDF only) *", type=["pdf"])

    st.subheader("Referral")
    referred = st.checkbox("I was referred by an employee")
    ref_name = ref_emp_id = ref_email = ""
    if referred:
        ref_name = st.text_input("Referrer Name *")
        ref_emp_id = st.text_input("Referrer Employee ID *")
        ref_email = st.text_input("Referrer Email *")

    st.divider()
    consent = st.checkbox("I consent to the processing of my data for recruitment purposes. *")

    submitted = st.form_submit_button("Submit Application")

if submitted:
    errors = []

    # Required fields
    if not full_name.strip():
        errors.append("Full Name is required.")
    if not is_email(email):
        errors.append("Valid Email is required.")
    if not position.strip():
        errors.append("Position is required.")
    if years_experience is None:
        errors.append("Years of Experience is required.")
    if not resume_file:
        errors.append("Resume PDF is required.")
    if not consent:
        errors.append("Consent is required to submit the application.")

    if referred:
        if not ref_name.strip():
            errors.append("Referrer Name is required.")
        if not ref_emp_id.strip():
            errors.append("Referrer Employee ID is required.")
        if not is_email(ref_email):
            errors.append("Valid Referrer Email is required.")

    # Validate PDF
    if resume_file and resume_file.type != "application/pdf":
        errors.append("Resume must be a PDF file.")

    if errors:
        for e in errors:
            st.error(e)
        st.stop()

    # Persist files and data
    timestamp = datetime.utcnow()
    app_id = create_app_id()
    safe_name = sanitize_filename(full_name or "applicant")
    resume_name = f"{app_id}_{safe_name}.pdf"
    resume_path = SAVE_DIR / resume_name

    try:
        resume_bytes = resume_file.read()
        with open(resume_path, "wb") as f:
            f.write(resume_bytes)
    except Exception as ex:
        st.error(f"Failed to save resume: {ex}")
        st.stop()

    record = {
        "app_id": app_id,
        "timestamp_iso": timestamp.isoformat() + "Z",
        "full_name": full_name.strip(),
        "email": email.strip(),
        "phone": phone.strip(),
        "position": position.strip(),
        "years_experience": years_experience,
        "expected_salary": (expected_salary or "").strip(),
        "location": (location or "").strip(),
        "linkedin": (linkedin or "").strip(),
        "cover_letter": (cover_letter or "").strip(),
        "referred": "Yes" if referred else "No",
        "ref_name": ref_name.strip(),
        "ref_emp_id": ref_emp_id.strip(),
        "ref_email": ref_email.strip(),
        "resume_filename": resume_name,
    }

    try:
        append_application_row(**record)
    except Exception as ex:
        st.error(f"Failed to save application record: {ex}")
        st.stop()

    # Prepare email bodies
    applicant_subject = f"Application Submitted Successfully — {app_id}"
    applicant_body = (
        f"Hi {full_name},\n\n"
        f"Thanks for applying for the {position} role. We’ve received your application (ID: {app_id}).\n"
        f"Our team will review it and get back to you.\n\n"
        f"Best,\n{FROM_NAME}"
    )

    hr_subject = f"[New Application] {full_name} — {position} — {app_id}"
    hr_body_lines = [
        f"Application ID: {app_id}",
        f"Submitted (UTC): {record['timestamp_iso']}",
        f"Name: {full_name}",
        f"Email: {email}",
        f"Phone: {phone}",
        f"Position: {position}",
        f"Experience (yrs): {years_experience}",
        f"Expected Salary: {expected_salary}",
        f"Location: {location}",
        f"LinkedIn: {linkedin}",
        f"Referred: {'Yes' if referred else 'No'}",
    ]
    if referred:
        hr_body_lines += [
            f"Referrer Name: {ref_name}",
            f"Referrer Emp ID: {ref_emp_id}",
            f"Referrer Email: {ref_email}",
        ]
    if cover_letter:
        hr_body_lines += ["", "Cover Letter:", cover_letter]
    hr_body = "\n".join(hr_body_lines)

    ref_subject = f"You Referred an Applicant — {full_name} for {position} ({app_id})"
    ref_body = (
        f"Hello {ref_name},\n\n"
        f"This is to notify you that {full_name} has submitted an application for the {position} role and listed you as a referrer.\n"
        f"Application ID: {app_id}\n\n"
        f"Best,\n{FROM_NAME}"
    )

    # Send emails
    try:
        # Applicant (no attachment)
        send_email(applicant_subject, applicant_body, email)

        # HR (attach resume)
        send_email(hr_subject, hr_body, HR_EMAIL, attachment=resume_bytes, attachment_name=resume_name)

        # Referrer (optional)
        if referred and ref_email:
            send_email(ref_subject, ref_body, ref_email)

        st.success(f"Application submitted! Your ID is **{app_id}**.")
        st.info("A confirmation email has been sent to you. HR has also been notified."
                + (" The referring employee was notified as well." if referred else ""))

        # Offer a quick link to the stored resume (local only)
        st.download_button("Download the saved resume copy", data=resume_bytes, file_name=resume_name, mime="application/pdf")

        # Show a brief receipt
        with st.expander("View submission receipt"):
            st.json({k: v for k, v in record.items() if k != "resume_filename"})

    except Exception as ex:
        st.error(f"Emails could not be sent: {ex}")
        st.stop()

st.caption("© " + str(datetime.now().year) + " — " + (FROM_NAME or "Recruiting Team"))
