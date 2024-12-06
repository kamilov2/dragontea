from telebot.types import ReplyKeyboardMarkup, KeyboardButton


class MainMenuKeyboard:
    def __init__(self, lang_code):
        self.lang_code = lang_code

    def generate(self):
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)

        if self.lang_code == 'ru':  
            buttons = [
                KeyboardButton("🍽️ Меню"),
                KeyboardButton("🎁 Мои заказы"),
                KeyboardButton("✍️ Оставить отзыв"),
                KeyboardButton("⚙️ Настройки"),
            ]
        elif self.lang_code == 'uz':
            buttons = [
                KeyboardButton("🍽️ Menu"),
                KeyboardButton("🎁 Buyurtmalarim"),
                KeyboardButton("✍️ Fikr bildirish"),
                KeyboardButton("⚙️ Sozlamalar"),
            ]
        else:
            buttons = [
                KeyboardButton("🍽️ Меню"),
                KeyboardButton("🎁 Мои заказы"),
                KeyboardButton("✍️ Оставить отзыв"),
                KeyboardButton("⚙️ Настройки"),
            ]

        keyboard.add(*buttons)
        return keyboard
