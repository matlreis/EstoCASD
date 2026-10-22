from django.db import models


class LogEvento(models.Model):
    ip_aparelho = models.GenericIPAddressField(null=True, blank=True)
    
    event_date = models.DateTimeField(auto_now_add=True)
    event_type = models.CharField(max_length=20)

    class Meta:
        abstract = True