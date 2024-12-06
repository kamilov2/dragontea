from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

language = {
    'uz': '🇺🇿 O\'zbek',
    'ru': '🇷🇺 Русский'
}

class LanguageHandler:
    def __init__(self, language_dict=None):
        self.language = language_dict or language

    def generate_language_keyboard(self):
        markup = InlineKeyboardMarkup()
        for lang_code, lang_name in self.language.items():
            button = InlineKeyboardButton(text=lang_name, callback_data=f"language_{lang_code}")
            markup.add(button)
        return markup
