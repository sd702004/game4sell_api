import logging
import requests

from django.conf import settings
from restapi.base.runtime_config import RuntimeConfig


class TelegramLogger(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self)
        self._token = settings.TELEGRAM_BOT_TOKEN
        self._chatId = settings.TELEGRAM_CHAT_ID

    def emit(self, record):
        if settings.DEBUG:
            print("[MESSENGER LOG]\n" + self.format(record))
            return

        prefix = ""

        match record.levelname:
            case "WARNING":
                prefix = "⚠️[WARNING]⚠️\n"
            case "ERROR":
                prefix = "❗️[ERROR]❗️\n"
            case "CRITICAl":
                prefix = "☠️[CRITICAL]☠️\n"

        url = f"https://api.telegram.org/bot{self._token}/sendMessage"

        data = {
            "chat_id": self._chatId,
            "text": prefix + self.format(record),
        }

        config = RuntimeConfig.getInstance()

        try:
            requests.post(url, data=data, timeout=config.http_request_timeout)
        except Exception as e:
            # Another logger cannot be used due to the risk of deadlock
            print(f"Messenger Logging Error - {e}")
