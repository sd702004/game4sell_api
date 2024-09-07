from abc import ABC, abstractmethod
from typing import List, Dict, TypedDict
from enum import Enum
from dataclasses import dataclass
import hashlib

import logging
logger = logging.getLogger(__name__)


class PaymentStatus(Enum):
    OK = 0
    UNKNOWN = 1
    PAYMENTFAILED = 2
    UNAUTHORIZEDCARD = 3


class MaskedCard(TypedDict):
    first_digits: int
    last_digits: int


@dataclass
class VerifiedPaymentResult:
    paid_amount_rial: int
    card_number: MaskedCard


class IPayment(ABC):
    @abstractmethod
    def requestPayment(self, orderid: str, amount_toman: int,
                       mobile: int | None = None) -> str | None:
        pass

    @abstractmethod
    def getPaymentUrl(self, trackid: str) -> str:
        pass

    @abstractmethod
    def isPaymentVerifiable(self, callback_data: Dict,
                            authorized_cards: List[int] = []) -> PaymentStatus:
        pass

    @abstractmethod
    def verifyPayment(self, trackid: str) -> VerifiedPaymentResult | None:
        pass

    @abstractmethod
    def inquiryPayment(self, trackid: str) -> Dict:
        pass

    def _isCardAuthorized(self, masked_card: str, card_hash: str,
                          authorized_cards: List[int] = []) -> bool:

        if len(masked_card) != 16:
            return False

        try:
            card_hash_bin = bytes.fromhex(card_hash)
        except ValueError as e:
            logger.warning(e)
            return False

        first_digits = masked_card[:6]
        last_digits = masked_card[-4:]

        for card in authorized_cards:
            card_str = str(card)

            if card_str[:6] != first_digits or card_str[-4:] != last_digits:
                continue

            h = hashlib.sha256()
            h.update(card_str.encode())

            if h.digest() == card_hash_bin:
                return True

        logger.info("[CLIENT_ERROR] Unauthorized cardnumber: {}"
                    .format(masked_card))

        return False
