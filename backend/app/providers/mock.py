from app import db


class MockMailProvider:
    """Gerçekten göndermez; yapılacak işi giden kutusuna (outbox tablosu) yazar."""

    def send_email(self, to: list[str], subject: str, body: str) -> None:
        db.add_outbox("EMAIL", {"to": to, "subject": subject, "body": body})

    def create_meeting(self, title: str, description: str, attendees: list[str]) -> None:
        db.add_outbox("MEETING", {"title": title, "description": description, "attendees": attendees})
