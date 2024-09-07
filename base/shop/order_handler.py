from typing import TypedDict, List, Dict, Optional
from dataclasses import dataclass
from enum import Enum, auto

from django.db import transaction

from restapi.base.service.product_service import ProductService
from restapi.base.service.order_service import OrderService
from restapi.base.shop.product.interface_product import IProduct
from restapi.base.shop.product.game import Game
from restapi.base.shop.product.giftcard import GiftCard
from restapi.base.shop.product.steam import Steam
from restapi.models.user import User

import logging
logger = logging.getLogger(__name__)


class Product(TypedDict):
    id: int
    count: int


class ErrorId(Enum):
    INVALID_ID = auto()
    NO_PRODUCT_HANDLER = auto()
    OUT_OF_STOCK = auto()
    LOW_STOCK = auto()
    SAVE_ERROR = auto()


@dataclass
class OrderError:
    error_id: ErrorId
    info: Dict | None = None


@dataclass
class CheckoutDetail:
    price: int
    requirements: Dict


class OrderHandler:
    def __init__(self):
        self._product_service = ProductService()
        self._order_service = OrderService()

        self._handlers = {
            "game-pc-steam": Game,
            "game-pc-epic": Game,
            "game-pc-ubisoft": Game,
            "gift-card": GiftCard,
            "steam-gem": Steam,
            "steam-tf2": Steam,
        }

    def submitOrder(self, user: User,
                    order_list: List[Product]) \
            -> bool | OrderError:

        # delete previous unpaid order and retrieve the submitted requirements
        order = self._order_service.getUnpaidOrderAndUpdateLastModified(user)
        last_unpaid_order_reqs = {}

        if order is not None:
            if order.requirements:
                last_unpaid_order_reqs = {
                    key: value for key, value in order.requirements.items()
                    if value is not None}

            try:
                order.delete()
            except Exception as e:
                logger.warning(e)
                pass

        # save order to database
        products: List[IProduct] = []
        products_count: List[int] = []

        for product_cart in order_list:
            try:
                item = self._product_service \
                    .getProductSummaryByIds([product_cart["id"]])[0]
            except IndexError as e:
                # product not found
                logger.info("[uid: {}] [CLIENT_ERROR] Product not found - {}"
                            .format(user.id, e))

                return OrderError(error_id=ErrorId.INVALID_ID,
                                  info={"product_id": product_cart["id"]})

            product = self.createProduct(
                item.product_type, product_cart["id"])

            if product is None:
                logger.info("[uid: {}] [CLIENT_ERROR] Product {} not found"
                            .format(user.id, item.title))

                return OrderError(error_id=ErrorId.NO_PRODUCT_HANDLER,
                                  info={"product_id": product_cart["id"],
                                        "product_title": item.title})

            stock = product.getStock()

            if stock == 0:
                logger.info(("[uid: {}] [CLIENT_ERROR] Product {} is out of "
                             "stock").format(user.id, item.title))

                return OrderError(error_id=ErrorId.OUT_OF_STOCK,
                                  info={"product_id": product_cart["id"],
                                        "product_title": item.title})

            if stock > 0 and product_cart["count"] > stock:
                logger.info(("[uid: {}] [CLIENT_ERROR] The stock of product {}"
                             " is below {}. Current stock: {}")
                            .format(user.id, item.title,
                                    product_cart["count"], stock))

                return OrderError(error_id=ErrorId.LOW_STOCK,
                                  info={"product_id": product_cart["id"],
                                        "product_title": item.title,
                                        "stock": stock})

            products.append(product)
            products_count.append(product_cart["count"])

        if not self._saveUserOrder(user, products, products_count,
                                   last_unpaid_order_reqs):

            return OrderError(error_id=ErrorId.SAVE_ERROR)

        return True

    def getUnpaidOrderCheckoutDetails(self,
                                      user: User) -> CheckoutDetail | None:
        order = self._order_service.getUnpaidOrderAndUpdateLastModified(user)

        if order is None:
            return None

        price = self._order_service.calcOrderPrice(order)

        if price is None:
            return None

        return CheckoutDetail(price=price, requirements=order.requirements)

    def submitRequirement(self, user: User,
                          req_name: str, data: Dict) -> bool | None:
        order = self._order_service.getUnpaidOrderAndUpdateLastModified(user)

        if order is None:
            logger.info("[uid: {}] [CLIENT_ERROR] Order not found"
                        .format(user.id))

            return None

        if req_name not in order.requirements:
            logger.info(("[uid: {}] [CLIENT_ERROR] Requirement {} is not "
                         "included in the order requirements - "
                         "requirements: {}").format(user.id,
                                                    req_name,
                                                    order.requirements))

            return False

        return self._order_service.saveRequirmenet(order, req_name, data)

    def createProduct(self, product_type: str | None,
                      product_id: int) -> IProduct | None:

        if product_type is None:
            return None

        handler = self._handlers.get(product_type)

        if handler is None:
            logger.error(f"No handler found for product type {product_type}")
            return None

        product = self._product_service.getProductById(product_id)
        return handler(product, product_type)

    def _saveUserOrder(self, user: User, products: List[IProduct],
                       products_count: List[int],
                       prev_reqs: Optional[Dict] = None) -> bool:

        try:
            with transaction.atomic():
                # create order (order id)
                order = self._order_service.createOrder(user=user)

                if order is None:
                    raise Exception()

                # save order list
                product_list = [{"product": item[0].getProduct(),
                                 "count": item[1]}
                                for item in zip(products, products_count)]

                if not self._order_service.addProductsToOrder(order,
                                                              product_list):
                    raise Exception()

                # reserve products
                for item in zip(products, products_count):
                    product = item[0]
                    count = item[1]

                    if not product.reserve(count, order.id):
                        raise Exception()

                # save requirmenets
                requirements = set()

                for product in products:
                    req = product.getRequirement()

                    if req:
                        requirements.add(req)

                if (len(requirements) and
                    not self._order_service.saveRequirementTitleList(
                        order, requirements, prev_reqs)):

                    raise Exception()

        except Exception:
            logger.error("[uid: {}] Order save failed".format(user.id))
            return False

        return True
