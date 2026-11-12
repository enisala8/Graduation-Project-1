from app.config import settings
from app.providers.base import MailProvider, MailProviderError


def get_mail_provider() -> MailProvider:
    if settings.mail_provider == "mock":
        from app.providers.mock import MockMailProvider

        return MockMailProvider()
    raise MailProviderError(f"Desteklenmeyen MAIL_PROVIDER: {settings.mail_provider} (Gmail Aşama 5'te)")
