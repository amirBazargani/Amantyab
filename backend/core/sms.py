"""SMS backend system with pluggable console and in-memory providers."""

from django.conf import settings
from django.utils.module_loading import import_string

# In-memory storage for test inspection, similar to django.core.mail.outbox
outbox = []


class BaseSMSBackend:
    """Base class for SMS backends."""

    def send_sms(self, phone, message):
        """Send an SMS message to a phone number. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement send_sms().")


class ConsoleBackend(BaseSMSBackend):
    """SMS backend that prints messages to stdout/console."""

    def send_sms(self, phone, message):
        """Print the SMS message directly to console."""
        print(f"----------------------------------------")
        print(f"[SMS CONSOLE BACKEND]")
        print(f"Recipient: {phone}")
        print(f"Message: {message}")
        print(f"----------------------------------------")
        return True


class LocmemBackend(BaseSMSBackend):
    """SMS backend that records messages in memory for test verification."""

    def send_sms(self, phone, message):
        """Store the SMS message in module outbox list."""
        outbox.append(
            {
                "phone": phone,
                "message": message,
            }
        )
        return True


def get_sms_backend(backend_path=None):
    """Return an instance of the configured SMS backend."""
    backend_name = backend_path or getattr(settings, "SMS_BACKEND", "console")

    alias_map = {
        "console": "core.sms.ConsoleBackend",
        "locmem": "core.sms.LocmemBackend",
    }

    dotted_path = alias_map.get(backend_name, backend_name)
    try:
        backend_cls = import_string(dotted_path)
    except ImportError as exc:
        raise ImportError(f"Could not import SMS backend '{dotted_path}': {exc}") from exc

    return backend_cls()
