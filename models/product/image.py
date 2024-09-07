from django.db import models
from .base import BaseProduct


def get_upload_path(instance, filename) -> str:
    return "product/{}/{}/{}".format(
        instance.base_product.category.slug,
        instance.base_product.id,
        filename)


class ProductImage(models.Model):
    base_product = models.ForeignKey(BaseProduct, on_delete=models.RESTRICT)
    image = models.ImageField(upload_to=get_upload_path)
    image_lq = models.ImageField(upload_to=get_upload_path)
    image_thumbnail = models.ImageField(upload_to=get_upload_path)
