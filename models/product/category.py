from django.db import models

from .type import ProductType


class ProductCategory(models.Model):
    slug = models.SlugField(max_length=50)
    title = models.CharField(max_length=50)
    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True)
    brief_description = models.CharField(max_length=150)
    product_type = models.ForeignKey(ProductType, null=True,
                                     on_delete=models.RESTRICT)

    # additional descriptions for products in this category
    description = models.TextField(null=True)

    class Meta:
        unique_together = ["slug", "parent"]
