import os
import logging
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from telebot.types import Update
from dotenv import load_dotenv
from apps.bot.views import TelegramBot

bot = TelegramBot().bot
load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(message)s',
    level=logging.INFO
)

WEBHOOK_URL = os.getenv('WEBHOOK_URL')

@csrf_exempt
def webhook(request):
    if request.method == 'POST':
        try:
            update = Update.de_json(request.body.decode('UTF-8'))
            bot.process_new_updates([update])
            logger.info("Успешно обработано обновление от Telegram.")
        except Exception as e:
            logger.exception("Ошибка при обработке обновления: %s", str(e))
            return JsonResponse(
                {'status': 'error', 'message': 'Ошибка при обработке обновления'},
                status=500
            )
        return JsonResponse(
            {'status': 'ok', 'message': 'Обновление успешно обработано'}
        )
    else:
        logger.warning("Получен неподдерживаемый метод HTTP: %s", request.method)
        return JsonResponse(
            {'status': 'error', 'message': 'Метод не поддерживается'},
            status=405
        )

def set_webhook():
    try:
        bot.remove_webhook()
        if bot.set_webhook(url=WEBHOOK_URL):
            logger.info("Webhook успешно установлен по адресу: %s", WEBHOOK_URL)
        else:
            logger.error("Не удалось установить Webhook: Telegram не подтвердил установку.")
    except Exception as e:
        logger.exception("Критическая ошибка при установке Webhook: %s", str(e))

try:
    set_webhook()
except Exception as e:
    logger.critical("Критическая ошибка при инициализации Webhook: %s", str(e))
