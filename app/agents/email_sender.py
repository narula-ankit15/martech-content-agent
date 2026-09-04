import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Protocol


class EmailSender(Protocol):
    def send(self, *, to: str, subject: str, html_body: str) -> None:
        ...


class GmailSmtpSender:
    """Sends over Gmail's own SMTP server, authenticated as a real Gmail
    address via an App Password (never the account's login password) -- so
    the email genuinely comes from that address and shows up in its own
    Sent folder, not from some anonymous relay.
    """

    def __init__(self, address: str, app_password: str):
        self._address = address
        self._app_password = app_password

    def send(self, *, to: str, subject: str, html_body: str) -> None:
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = self._address
        message["To"] = to
        message.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(self._address, self._app_password)
            server.sendmail(self._address, [to], message.as_string())
