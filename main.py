from telethon import TelegramClient
from telethon.tl.functions.account import ReportPeerRequest
from telethon.tl.types import InputReportReasonSpam
import asyncio
import time

# Ваши учетные данные
API_ID = "27846307"
API_HASH = "e0edb165f9009efab3102d47f08188ad"
PHONE_NUMBER = "+998902113123"

# Название канала
CHANNEL_USERNAME = "@AZAI_STORE"

async def report_channel():
    async with TelegramClient('report_session', API_ID, API_HASH) as client:
        while True:  # Бесконечный цикл
            try:
                # Подача жалобы
                result = await client(ReportPeerRequest(
                    peer=CHANNEL_USERNAME,
                    reason=InputReportReasonSpam(),
                    message="Этот канал занимается мошенничеством. Прошу принять меры."
                ))
                print("Жалоба успешно отправлена:", result)

                # Задержка между отправками (рекомендуется не менее 30-60 секунд)
                time.sleep(30)
            except Exception as e:
                print(f"Произошла ошибка: {e}")
                # Добавим небольшую паузу перед повтором, если произошла ошибка
                time.sleep(10)

# Запуск
asyncio.run(report_channel())
