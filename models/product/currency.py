from django.db import models


class Currency(models.Model):
    unit = models.CharField(primary_key=True, max_length=5)
    name = models.CharField(max_length=20)  # currency unit equivalent
    toman_value = models.FloatField()
