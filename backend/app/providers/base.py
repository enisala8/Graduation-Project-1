from typing import Protocol


class MailProviderError(Exception):
    """Gönderme / toplantı oluşturma başarısız."""


class MailProvider(Protocol):
    """Gmail, Outlook veya mock: geri kalan kod hangisi olduğunu bilmez."""

    def send_email(self, to: list[str], subject: str, body: str) -> None: ...

    def create_meeting(self, title: str, description: str, attendees: list[str]) -> None: ...
