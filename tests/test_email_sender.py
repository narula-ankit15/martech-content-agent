from unittest.mock import MagicMock, patch

from app.agents.email_sender import GmailSmtpSender


@patch("smtplib.SMTP")
def test_send_authenticates_and_sends_via_gmail_smtp(mock_smtp_class):
    mock_server = MagicMock()
    mock_smtp_class.return_value.__enter__.return_value = mock_server

    sender = GmailSmtpSender("me@gmail.com", "app-password-1234")
    sender.send(to="recipient@example.com", subject="Hello", html_body="<p>Hi there</p>")

    mock_smtp_class.assert_called_once_with("smtp.gmail.com", 587)
    mock_server.starttls.assert_called_once()
    mock_server.login.assert_called_once_with("me@gmail.com", "app-password-1234")

    assert mock_server.sendmail.call_count == 1
    from_addr, to_addrs, raw_message = mock_server.sendmail.call_args[0]
    assert from_addr == "me@gmail.com"
    assert to_addrs == ["recipient@example.com"]
    assert "Hello" in raw_message
    assert "Hi there" in raw_message


@patch("smtplib.SMTP")
def test_send_propagates_smtp_errors(mock_smtp_class):
    import smtplib

    mock_server = MagicMock()
    mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, b"bad credentials")
    mock_smtp_class.return_value.__enter__.return_value = mock_server

    sender = GmailSmtpSender("me@gmail.com", "wrong-password")
    try:
        sender.send(to="recipient@example.com", subject="Hi", html_body="<p>x</p>")
        assert False, "expected SMTPAuthenticationError to propagate"
    except smtplib.SMTPAuthenticationError:
        pass
