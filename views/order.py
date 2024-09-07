from typing import cast

from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import Serializer
from rest_framework import status
from ipware import get_client_ip

from django.views.decorators.csrf import csrf_protect
from django.utils.decorators import method_decorator
from django.conf import settings
from rest_framework_simplejwt.authentication import JWTAuthentication

from restapi.serializers.order_serializer import (ProductIdsSerializer,
                                                  CartProductsSerializer,
                                                  SteamTradeLinkSerializer,
                                                  SteamAccountSerializer,
                                                  EmailPassSerializer)
from restapi.base.service.product_service import ProductService
from restapi.base.shop.order_handler import OrderHandler, OrderError, ErrorId
from restapi.models.user import User
from restapi.base.crypto import Crypto

import logging
logger = logging.getLogger(__name__)


@method_decorator(csrf_protect, name="dispatch")
class Order(APIView):
    authentication_classes = [JWTAuthentication]

    def get(self, request: Request, method: str) -> Response:
        match method:
            case "get-cart-details":
                return self._getCartDetails(request)
            case "get-unpaid-order-details":
                return self._getUnpaidOrderDetails(request)
            case _:
                logger.info("[IP: {}] [CLIENT_ERROR] Invalid method: {}"
                            .format(get_client_ip(request)[0], method))

                return Response(status=status.HTTP_400_BAD_REQUEST)

    def post(self, request: Request, method: str) -> Response:
        if request.auth is None:
            logger.info("[IP: {}] [CLIENT_ERROR] Unauthorized request"
                        .format(get_client_ip(request)[0]))

            return Response(status=status.HTTP_401_UNAUTHORIZED)

        match method:
            case "submit-cart":
                return self._submitCart(request)

            case "submit-steam-tradelink":
                return self._submitRequirement(
                    request, "steam-tradelink",
                    SteamTradeLinkSerializer)

            case "submit-steam-user-pass-backup":
                return self._submitRequirement(
                    request,
                    "steam-user-pass-backup",
                    SteamAccountSerializer)

            case "submit-epic-email-pass":
                return self._submitRequirement(
                    request,
                    "epic-email-pass",
                    EmailPassSerializer)

            case "submit-ubisoft-email-pass":
                return self._submitRequirement(
                    request,
                    "ubisoft-email-pass",
                    EmailPassSerializer)

        logger.info("[IP: {}] [CLIENT_ERROR] Invalid method: {}"
                    .format(get_client_ip(request)[0], method))

        return Response(status=status.HTTP_400_BAD_REQUEST)

    def _getCartDetails(self, request: Request) -> Response:
        serializer = ProductIdsSerializer(data=request.query_params)

        if not serializer.is_valid():
            logger.info("[IP: {}] [CLIENT_ERROR] Invalid data - {}"
                        .format(get_client_ip(request)[0],
                                request.query_params))

            return Response(status=status.HTTP_400_BAD_REQUEST)

        product_ids = serializer.data.get("product_ids")
        product_service = ProductService()

        summeries = product_service.getProductSummaryByIds(product_ids)
        summaries_serializable = [summary.__dict__ for summary in summeries]

        response = {
            "img_base_url": settings.MEDIA_URL,
            "summaries": summaries_serializable
        }

        return Response(response, status=status.HTTP_200_OK)

    def _submitCart(self, request: Request) -> Response:
        user = cast(User, request.user)  # user type cannot be AnonymousUser
        serializer = CartProductsSerializer(data=request.data)

        if (not serializer.is_valid() or
                len(serializer.data["order_list"]) == 0):

            logger.info("[IP: {}] [uid: {}] [CLIENT_ERROR] Invalid data - {}"
                        .format(get_client_ip(request)[0],
                                user.id,
                                request.data))

            return Response(status=status.HTTP_400_BAD_REQUEST)

        order_handler = OrderHandler()

        submit_result = order_handler \
            .submitOrder(user, serializer.data["order_list"])

        if submit_result is True:  # order submission successful
            logger.info(("[IP: {}] [uid: {}] Order submitted successfully - "
                         "order list: {}")
                        .format(get_client_ip(request)[0],
                                user.id,
                                serializer.data["order_list"]))

            return Response(status=status.HTTP_201_CREATED)

        if type(submit_result) is OrderError:
            match submit_result.error_id:
                case ErrorId.INVALID_ID:
                    error_msg = ("در سبد خرید شما، کالای نامعتبر وجود دارد. "
                                 "لطفا کالاها را از سبد خرید حذف و "
                                 "دوباره اقدام به خرید کنید.")

                    response_err = {
                        "error_type": "invalid-product",
                        "error_msg": error_msg,
                    }

                    logger.info(("[IP: {}] [uid: {}] [CLIENT_ERROR] "
                                 "Order contains invalid products - "
                                 "order list: {}")
                                .format(get_client_ip(request)[0],
                                        user.id,
                                        serializer.data["order_list"]))

                    return Response(response_err,
                                    status=status.HTTP_400_BAD_REQUEST)

                case ErrorId.NO_PRODUCT_HANDLER:
                    product_title = (submit_result.info["product_title"]
                                     if submit_result.info is not None else "")

                    error_msg = ("به دلیل مشکل فنی، امکان خرید محصول "
                                 f"«{product_title}» "
                                 "وجود ندارد. ")

                    response_err = {
                        "error_type": "no-product-handler",
                        "error_msg": error_msg,
                        "product_title": product_title
                    }

                    logger.error(("[IP: {}] [uid: {}] Product ({}) cannot be "
                                  "handled").format(get_client_ip(request)[0],
                                                    user.id,
                                                    product_title))

                    return Response(response_err,
                                    status=status.HTTP_501_NOT_IMPLEMENTED)

                case ErrorId.OUT_OF_STOCK:
                    product_title = (submit_result.info["product_title"]
                                     if submit_result.info is not None else "")

                    error_msg = ("موجودی محصول "
                                 f"«{product_title}» "
                                 "به اتمام رسیده است")

                    response_err = {
                        "error_type": "out-of-stock",
                        "error_msg": error_msg,
                        "product_title": product_title
                    }

                    logger.info(("[IP: {}] [uid: {}] [CLIENT_ERROR] "
                                 "Product ({}) is out of stock")
                                .format(get_client_ip(request)[0],
                                        user.id, product_title))

                    return Response(response_err,
                                    status=status.HTTP_404_NOT_FOUND)

                case ErrorId.LOW_STOCK:
                    product_title = (submit_result.info["product_title"]
                                     if submit_result.info is not None else "")

                    stock = (submit_result.info["stock"]
                             if submit_result.info is not None else 0)

                    error_msg = (f"موجودی محصول «{product_title}» "
                                 f"برابر با {stock} عدد می‌باشد")

                    response_err = {
                        "error_type": "low-stock",
                        "error_msg": error_msg,
                        "product_title": product_title,
                        "stock": stock
                    }

                    logger.info(("[IP: {}] [uid: {}] [CLIENT_ERROR] "
                                 "There is insufficient stock of product ({})")
                                .format(get_client_ip(request)[0],
                                        user.id, product_title))

                    return Response(response_err,
                                    status=status.HTTP_404_NOT_FOUND)

                case ErrorId.SAVE_ERROR:
                    error_msg = ("ثبت سفارش امکان‌پذیر نیست. "
                                 "لطفا دوباره اقدام کنید.")

                    response_err = {
                        "error_type": "no-product-handler",
                        "error_msg": error_msg,
                    }

                    logger.error("[IP: {}] [uid: {}] Order submission failed"
                                 .format(get_client_ip(request)[0], user.id))

                    return Response(
                        response_err,
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        logger.error("[IP: {}] [uid: {}] Order submission failed - no handler"
                     .format(get_client_ip(request)[0], user.id))

        return Response(status=status.HTTP_501_NOT_IMPLEMENTED)

    def _getUnpaidOrderDetails(self, request: Request) -> Response:
        if request.auth is None:
            logger.info("[IP: {}] [CLIENT_ERROR] Unauthorized request"
                        .format(get_client_ip(request)[0]))

            return Response(status=status.HTTP_401_UNAUTHORIZED)

        user = cast(User, request.user)  # user type cannot be AnonymousUser
        order_handler = OrderHandler()

        order_det = order_handler.getUnpaidOrderCheckoutDetails(user)

        if order_det is None:
            logger.info("[IP: {}] [uid: {}] [CLIENT_ERROR] "
                        .format(get_client_ip(request)[0], user.id))

            return Response(status=status.HTTP_404_NOT_FOUND)

        requirements = []

        for key, value in order_det.requirements.items():
            # Return any pre-existing value for a requirement to the user,
            # omitting the password key if one exists.

            if value:
                value.pop("password", None)

            req = {"requirement": key, "data": value}
            requirements.append(req)

        response = {
            "price": order_det.price,
            "requirements": requirements,
            "cards": [],  # dictionaries with 'card_number' & 'bank_name' keys
            "wallet_amount": 0,
            "payment_gate": "sep",
        }

        return Response(response, status=status.HTTP_200_OK)

    def _submitRequirement(self, request: Request, req_type: str,
                           serializer_class: type[Serializer]) -> Response:

        user = cast(User, request.user)  # user type cannot be AnonymousUser
        serializer = serializer_class(data=request.data)

        if not serializer.is_valid():
            response = {
                "error_type": "validation",
                "error_msg": "داده‌های واردشده نامعتبر است",
            }

            logger.info("[IP: {}] [uid: {}] [CLIENT_ERROR] Invalid data"
                        .format(get_client_ip(request)[0], user.id))

            return Response(response, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.data

        if "password" in data:
            crypto = Crypto(settings.FERNET_KEY)
            password_enc = crypto.encrypt(serializer.data["password"])

            data = serializer.data
            data["password"] = password_enc

        order_handler = OrderHandler()

        submit_result = order_handler.submitRequirement(
            user, req_type, data)

        if submit_result is None:
            logger.info(("[IP: {}] [uid: {}] [CLIENT_ERROR] "
                         "Requirement submission failed")
                        .format(get_client_ip(request)[0], user.id))

            return Response(status=status.HTTP_404_NOT_FOUND)

        if not submit_result:
            response = {
                "error_type": "submit-error",
                "error_msg": "ثبت داده‌ها با مشکل مواجه شد",
            }

            logger.error(("[IP: {}] [uid: {}] "
                         "The requirement could not be submitted ({})")
                         .format(get_client_ip(request)[0], user.id, req_type))

            return Response(response,
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        logger.info(("[IP: {}] [uid: {}] Requirement submitted - "
                     "type: {}, data: {}")
                    .format(get_client_ip(request)[0],
                            user.id, req_type, data))

        return Response()
