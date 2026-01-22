from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
import smtplib


logger = logging.getLogger(__name__)


def send_email(
    subject: str,
    body: str,
    to: list[str],
) -> None:
    """
    Compile subject and body into an email, and send using the computer's SMTP server.
    """

    msg = MIMEMultipart("alternative")
    # Attach the HTML body
    html_part = MIMEText(body, "html", "utf-8")
    msg.attach(html_part)

    msg["Subject"] = subject
    msg["From"] = "svc_mpe@alleninstitute.org"
    msg["To"] = ", ".join(to)

    smtp_server =  "aidc-mx-1.corp.alleninstitute.org"

    # Send message
    try:
        
        with smtplib.SMTP(smtp_server) as s:
            s.send_message(msg)
            print(f"EMAILING {to}")
        logger.info(
            f"Sent email",
            extra={
            "subject":subject,
            "to":to,
            "body":body,}
        )
    except:
        logger.exception(
            "Failed to send email",
            extra={
            "subject":subject,
            "to":to,
            "body":body,}
        )

if __name__ == "__main__":
    header = f'<h2>Error occured durring run:</h2>'
    msg = f'<h3>Device error. Please check device.</h3>'
    send_email(subject="Test Email", body=header + msg, to=["micah.woodard@alleninstitute.org"])