from django.db import models
from .base import BaseProduct
from .currency import Currency
from .type import ProductType


class Product(models.Model):
    variation = models.JSONField(null=True)  # product variations
    base_product = models.ForeignKey(BaseProduct, on_delete=models.CASCADE)
    price_irt = models.PositiveIntegerField()
    non_rial_currency = models.ForeignKey(
        Currency, on_delete=models.RESTRICT, null=True)
    non_rial_value = models.FloatField(null=True)
    product_type = models.ForeignKey(ProductType, null=True,
                                     on_delete=models.RESTRICT)
    stock = models.IntegerField(default=0)
