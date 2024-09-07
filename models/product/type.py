from django.db import models


class ProductType(models.Model):
    """
    Products have different methods for inventory, requirements, delivery, and
    reservations. This model defines product types to manage these aspects.
    Product types can be set at the category or individual product level, with
    the product's type taking precedence if specified. This dual-level type
    definition is useful for categories like gift cards, where all products
    share the same type.
    """

    typename = models.CharField(max_length=30, unique=True)
    description = models.CharField(max_length=150, null=True)
