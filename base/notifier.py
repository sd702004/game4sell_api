from restapi.base.interface_sms import ISms
from restapi.base.singleton_defaults import get_default_sms_handler
from restapi.base.singleton_meta import SingletonMeta

import logging
logger = logging.getLogger(__name__)


class Notifier(metaclass=SingletonMeta):
    """
    This class is a singleton, so it's advisable to use the getInstance method
    instead of directly using the constructor
    """

    def __init__(self) -> None:
        self._sms_handler: ISms = get_default_sms_handler()

    @classmethod
    def getInstance(cls):
        return cls()

    def sendOtpToMobile(self, mobile: int, code: str) -> int:
        logger.info("OTP code {} has been requested for mobile number {}"
                    .format(code, mobile))

        return self._sms_handler.sendOtp(mobile, code)

    def setSmsHandler(self, sms_handler: ISms) -> None:
        self._sms_handler = sms_handler
