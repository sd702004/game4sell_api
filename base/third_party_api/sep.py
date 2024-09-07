from typing import List, Dict
import requests
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from restapi.base.runtime_config import RuntimeConfig
from restapi.base.interface_payment import (IPayment, PaymentStatus,
                                            VerifiedPaymentResult)
from restapi.models import SepPayment

import logging
logger = logging.getLogger(__name__)
messenger_logger = logging.getLogger("messenger")


class Sep(IPayment):
    def __init__(self, terminal_id: str, callback_url: str) -> None:
        self._terminal_id = terminal_id
        self._callback_url = callback_url
        self._messenger_log_msg = ("[SEP] Operation failed. Please check the "
                                   "logs and consider changing the payment "
                                   "gateway if necessary.")

    def requestPayment(self, orderid: str, amount_toman: int,
                       mobile: int | None = None) -> str | None:

        url = "https://sep.shaparak.ir/onlinepg/onlinepg"
        wage = self._calcWage(amount_toman)

        data = {
            "action": "token",
            "TerminalId": self._terminal_id,
            "Amount": (amount_toman + wage) * 10,
            "ResNum": orderid,
            "RedirectUrl": self._callback_url,
        }

        if mobile is not None:
            data["CellNumber"] = f"0{mobile}"

        config = RuntimeConfig.getInstance()

        try:
            logger.info(("Payment request has been made. amount: {:,} toman, "
                         "orderid: {}, mobile: {}")
                        .format(amount_toman, orderid, mobile))

            r = requests.post(url, json=data,
                              timeout=config.http_request_timeout)
        except requests.exceptions.RequestException as e:
            logger.error("{} - orderid: {}, mobile: {}"
                         .format(e, orderid, mobile))

            messenger_logger.error(self._messenger_log_msg)
            return None

        if r.status_code != requests.codes.ok:
            logger.error("response code: {} - orderid: {}, mobile: {}"
                         .format(r.status_code, orderid, mobile))

            messenger_logger.error(self._messenger_log_msg)
            return None

        try:
            response = r.json()

            logger.info("orderid: {}, mobile: {}, response: {}"
                        .format(orderid, mobile, r.text))

            if response["status"] != 1:
                logger.error("result code isn't 1 - {}".format(r.text))
                messenger_logger.error(self._messenger_log_msg)

                return None

            return response["token"]
        except requests.exceptions.JSONDecodeError:
            logger.error("response isn't json - {}", r.text)
            messenger_logger.error(self._messenger_log_msg)
            return None
        except KeyError as e:
            logger.error("{} - {}", e, r.text)
            messenger_logger.error(self._messenger_log_msg)
            return None

    def getPaymentUrl(self, trackid: str) -> str:
        return f"https://sep.shaparak.ir/OnlinePG/SendToken?token={trackid}"

    def isPaymentVerifiable(self, callback_data: Dict,
                            authorized_cards: List[int] = []) -> PaymentStatus:

        try:
            if callback_data["State"] != "OK":
                logger.warning("'State' key is not 'OK' - {}"
                               .format(callback_data))

                return PaymentStatus.PAYMENTFAILED

            if (authorized_cards and
                not self._isCardAuthorized(callback_data["SecurePan"],
                                           callback_data["HashedCardNumber"],
                                           authorized_cards)):

                logger.info("[CLIENT_ERROR] Unauthorized card - {}"
                            .format(callback_data))

                return PaymentStatus.UNAUTHORIZEDCARD
        except KeyError as e:
            logger.error("{} - {}", e, callback_data)
            messenger_logger.error(self._messenger_log_msg)
            return PaymentStatus.UNKNOWN

        return PaymentStatus.OK

    def verifyPayment(self, trackid: str) -> VerifiedPaymentResult | None:
        if SepPayment._default_manager.filter(refnum=trackid).exists():
            # duplicate transaction

            logger.warning("Transaction with ID {} has already been verified."
                           .format(trackid))

            return None

        url = ("https://sep.shaparak.ir/"
               "verifyTxnRandomSessionkey/ipg/VerifyTransaction")

        data = {
            "TerminalNumber": self._terminal_id,
            "RefNum": trackid,
        }

        config = RuntimeConfig.getInstance()

        try:
            logger.info("Verification of transaction {} has been requested"
                        .format(trackid))

            r = requests.post(url, json=data,
                              timeout=config.http_request_timeout)
        except requests.exceptions.RequestException as e:
            logger.error("{} - trackid: {}".format(e, trackid))
            messenger_logger.error(self._messenger_log_msg)
            return None

        if r.status_code != requests.codes.ok:
            logger.error("response code: {}, trackid: {}"
                         .format(r.status_code, trackid))
            messenger_logger.error(self._messenger_log_msg)

            return None

        try:
            response = r.json()

            logger.info("trackid: {}, response: {}".format(trackid, r.text))

            if not response["Success"] or response["ResultCode"] != 0:
                logger.warning("trackid: {}, response: {}"
                               .format(trackid, r.text))
                messenger_logger.error(self._messenger_log_msg)

                return None

            detail = response["TransactionDetail"]

            if len(detail["MaskedPan"]) != 16:
                logger.warning("The card number is not 16 digits long - {}"
                               .format(r.text))

                return None

            payment_date = datetime.strptime(detail["StraceDate"],
                                             "%Y-%m-%d %H:%M:%S")

            try:
                payment_date = payment_date.replace(
                    tzinfo=ZoneInfo("Asia/Tehran"))
            except ZoneInfoNotFoundError:
                payment_date = payment_date.replace(
                    tzinfo=timezone(timedelta(hours=3, minutes=30)))

            payment_date_utc = payment_date.astimezone(timezone.utc)

            time_since_payment = datetime.now(timezone.utc) - payment_date_utc

            if time_since_payment.total_seconds() > 3600:
                # possibility of a duplicate transaction
                logger.warning(("Given that this transaction is over an hour "
                                "old, verification will be omitted due to the "
                                "risk of duplication - {}").format(r.text))

                return None

            db_record = SepPayment(refnum=trackid,
                                   payment_date=payment_date_utc)

            try:
                db_record.save()
            except Exception as e:
                """
                The transaction was successfully verified, but None is returned
                due to an error saving its identifier to the database. This is
                because uniqueness cannot be guaranteed if the corresponding
                record cannot be saved.
                """

                logger.error("{} - {}", e, r.text)
                return None

        except requests.exceptions.JSONDecodeError:
            logger.error("response isn't json - {}", r.text)
            messenger_logger.error(self._messenger_log_msg)
            return None
        except KeyError as e:
            logger.error("{} - {}", e, r.text)
            messenger_logger.error(self._messenger_log_msg)
            return None
        except ValueError as e:
            logger.error("{} - {}", e, r.text)
            messenger_logger.error(self._messenger_log_msg)
            return None

        cardnumber = detail["MaskedPan"]
        first_digits = cardnumber[:6]
        last_digits = cardnumber[-4:]

        if (not first_digits.isdigit() or
            not last_digits.isdigit() or
                type(detail["AffectiveAmount"]) is not int):

            logger.warning("The card number or response amount is invalid - {}"
                           .format(r.text))

            return None

        return VerifiedPaymentResult(
            paid_amount_rial=detail["AffectiveAmount"],
            card_number={
                "first_digits": int(first_digits),
                "last_digits": int(last_digits)
            }
        )

    def inquiryPayment(self, trackid: str) -> Dict:
        """
        [IMPORTANT] This method verifies successful transactions. Therefore,
        before using it, ensure the bank card used for payment is authorized to
        prevent verification of unauthorized transactions.
        """

        url = ("https://sep.shaparak.ir/"
               "verifyTxnRandomSessionkey/ipg/VerifyTransaction")

        data = {
            "TerminalNumber": self._terminal_id,
            "RefNum": trackid,
        }

        config = RuntimeConfig.getInstance()

        try:
            r = requests.post(url, json=data,
                              timeout=config.http_request_timeout)
        except requests.exceptions.RequestException as e:
            logger.warning(e)

            response = {
                "error": "Connection Error",
                "message": e
            }

            return response

        if r.status_code != requests.codes.ok:
            logger.warning("response code: {}".format(r.status_code))

            response = {
                "error": "HTTP Error",
                "raw_result": r.text
            }

            return response

        try:
            return r.json()
        except requests.exceptions.JSONDecodeError:
            logger.warning("Invalid response - {}".format(r.text))

            response = {
                "error": "result isn't json",
                "raw_result": r.text
            }

            return response

    def _calcWage(self, amount_toman: int) -> int:
        if amount_toman < 600_000:
            return 120

        if amount_toman < 20_000_000:
            return int(amount_toman * .0002)

        return 4000
