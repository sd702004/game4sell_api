from django.db import models
from datetimeutc.fields import DateTimeUTCField


class SepPayment(models.Model):
    """
    In this model, transaction IDs related to the Sep gateway are stored. As
    Sep silently accepts duplicate verifications, we first check for the ID in
    this table before verifying a transaction to ensure it's not a duplicate.

    The transaction verification function (Sep payment class) considers
    transactions that have been completed more than an hour ago to be
    unsuccessful. Therefore, records in this table with payment dates at least
    an hour ago can be deleted to optimize database space.
    """

    refnum = models.CharField(unique=True, max_length=50)
    payment_date = DateTimeUTCField()
