from django.db import models
from .category import ProductCategory


def get_upload_path(instance, filename) -> str:
    return "product/{}/{}/{}".format(
        instance.category.slug, instance.id, filename)


class BaseProduct(models.Model):
    slug = models.SlugField(max_length=50, unique=True)
    title = models.CharField(max_length=50)
    category = models.ForeignKey(ProductCategory, on_delete=models.RESTRICT)
    brief_description = models.CharField(max_length=150)
    description = models.TextField()
    additional_details = models.JSONField(null=True)
    cover_image = models.ImageField(upload_to=get_upload_path)
    cover_image_lq = models.ImageField(upload_to=get_upload_path)
