from django.urls import path
from apps.bot.webhook import webhook_conf
app_name = 'bot'

urlpatterns = [
    path('webhook/', webhook_conf.webhook, name='webhook'),
]
