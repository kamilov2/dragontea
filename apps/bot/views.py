import os
import json
import logging
import requests
import pytz
from datetime import datetime, time, timedelta
from geopy.distance import geodesic
from telebot.types import LabeledPrice, ReplyKeyboardRemove
from telebot import TeleBot, types
from dotenv import load_dotenv
from telebot.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from apps.bot.models import Client, Category, Product, Cart, Order

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

load_dotenv()

class TelegramBot:
    def __init__(self):
        self.bot = TeleBot(os.getenv('TELEGRAM_BOT_TOKEN'))
        self.bot.remove_webhook()
        self.user_data = {}
        self.admin_data = {}
        self.register_handlers()

    def register_handlers(self):
        @self.bot.message_handler(commands=['start'])
        def start(message):
            chat_id = message.chat.id
            try:
                client = Client.objects.get(telegram_id=chat_id)
                if not client.preferred_language:
                    self.ask_language(chat_id)
                elif not client.phone_number:
                    self.ask_phone_number(chat_id, client)
                else:
                    self.send_main_menu(chat_id, client.preferred_language)
            except Client.DoesNotExist:
                Client.objects.create(
                    telegram_id=chat_id,
                    name=message.from_user.first_name,
                    telegram_username=message.from_user.username
                )
                self.greet_and_ask_language(chat_id)

        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("close_order_"))
        def handle_close_order(call):
            order_id_str = call.data[len("close_order_"):]
            try:
                order_id = int(order_id_str)
                self.close_order(order_id, call)
            except ValueError:
                self.bot.answer_callback_query(call.id, "Некорректный ID заказа.")

        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("language_"))
        def handle_language_selection(call):
            language_code = call.data.split("_")[1]
            chat_id = call.message.chat.id
            client = Client.objects.get(telegram_id=chat_id)
            client.preferred_language = language_code
            client.save()
            self.bot.answer_callback_query(call.id)
            self.bot.delete_message(chat_id, message_id=call.message.message_id)
            self.bot.send_message(
                chat_id=chat_id,
                text="Til tanlandi" if language_code == 'uz' else "Язык выбран"
            )
            if not client.phone_number:
                self.ask_phone_number(chat_id, client)
            else:
                self.send_main_menu(chat_id, language_code)

        @self.bot.message_handler(content_types=['contact'])
        def handle_contact(message):
            chat_id = message.chat.id
            try:
                client = Client.objects.get(telegram_id=chat_id)
                client.phone_number = message.contact.phone_number
                client.save()
                self.bot.send_message(
                    chat_id=chat_id,
                    text="Telefon raqamingiz muvaffaqiyatli saqlandi. Rahmat!" if client.preferred_language == 'uz' else "Ваш номер телефона успешно сохранён. Спасибо!",
                    reply_markup=types.ReplyKeyboardRemove()
                )
                self.send_main_menu(chat_id, client.preferred_language)
            except Client.DoesNotExist:
                self.bot.send_message(chat_id=chat_id, text="Произошла ошибка. Пожалуйста, попробуйте снова.")

        @self.bot.message_handler(func=lambda message: message.text in ["🍽️ Меню", "🍽️ Menu"])
        def handle_menu(message):
            chat_id = message.chat.id
            try:
                client = Client.objects.get(telegram_id=chat_id)
                self.send_categories(chat_id, client.preferred_language)
            except Client.DoesNotExist:
                self.bot.send_message(chat_id=chat_id, text="Пожалуйста, начните с команды /start.")

        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("category_"))
        def handle_category_selection(call):
            chat_id = call.message.chat.id
            client = Client.objects.get(telegram_id=chat_id)
            category_id = call.data.split("_")[1]
            self.send_products(chat_id, category_id, client.preferred_language)
            self.bot.answer_callback_query(call.id)

        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("product_"))
        def handle_product_selection(call):
            try:
                chat_id = call.message.chat.id
                data = call.data.split("_")
                product_id = data[1]

                product = Product.objects.get(id=product_id)
                client = Client.objects.get(telegram_id=chat_id)
                language_code = client.preferred_language

                self.user_data[chat_id] = {'product_id': product_id}

                size_options = []
                if product.is_small:
                    size_options.append('small')
                if product.is_big:
                    size_options.append('big')

                if size_options:
                    size_keyboard = InlineKeyboardMarkup(row_width=2)
                    buttons = []
                    if 'small' in size_options:
                        buttons.append(InlineKeyboardButton(
                            f"Маленький {product.small_volume}" if language_code == 'ru' else f"Kichik {product.small_volume}",
                            callback_data=f"size_small_{product_id}"
                        ))
                    if 'big' in size_options:
                        buttons.append(InlineKeyboardButton(
                            f"Большой {product.big_volume}" if language_code == 'ru' else f"Katta {product.big_volume}",
                            callback_data=f"size_big_{product_id}"
                        ))
                    size_keyboard.add(*buttons)

                    size_message = "Выберите размер:" if language_code == 'ru' else "Hajmni tanlang:"
                    self.bot.send_message(chat_id, size_message, reply_markup=size_keyboard)
                    self.bot.answer_callback_query(call.id)
                else:
                    self.process_selection_without_size(chat_id, product, client)

            except Exception as e:
                logger.error(f"Error in handle_product_selection: {e}")
                self.bot.send_message(chat_id, f"Произошла ошибка при отображении продукта: {e}")

        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("size_"))
        def handle_size_selection(call):
            try:
                chat_id = call.message.chat.id
                data = call.data.split("_")
                size = data[1]
                product_id = int(data[2])

                product = Product.objects.get(id=product_id)
                client = Client.objects.get(telegram_id=chat_id)
                language_code = client.preferred_language

                is_small = size == 'small'
                is_big = size == 'big'
                unit_price = product.get_price(is_small=is_small, is_big=is_big) or 0

                cart_item, created = Cart.objects.get_or_create(
                    client=client,
                    product=product,
                    is_small=is_small,
                    is_big=is_big,
                    defaults={'quantity': 1}
                )

                if not created:
                    cart_item.is_small = is_small
                    cart_item.is_big = is_big
                    cart_item.save()

                self.send_product_details(
                    chat_id, client, product, cart_item.quantity,
                    is_small, is_big, False, False, cart_item.id
                )
                self.bot.answer_callback_query(call.id)

            except Exception as e:
                logger.error(f"Error in handle_size_selection: {e}")
                self.bot.send_message(chat_id, "Произошла ошибка при выборе размера.")

        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("temp_"))
        def handle_temp_selection(call):
            try:
                chat_id = call.message.chat.id
                data = call.data.split("_")
                temperature = data[1]
                product_id = data[2]

                product = Product.objects.get(id=product_id)
                client = Client.objects.get(telegram_id=chat_id)
                language_code = client.preferred_language

                user_choice = self.user_data.get(chat_id, {})
                size = user_choice.get('size', None)

                is_small = size == 'small' if size else False
                is_big = size == 'big' if size else False
                is_hot = temperature == 'hot'
                is_cold = temperature == 'cold'

                cart_item, created = Cart.objects.get_or_create(
                    client=client,
                    product=product,
                    is_small=is_small,
                    is_big=is_big,
                    is_hot=is_hot,
                    is_cold=is_cold,
                    defaults={'quantity': 0}
                )

                quantity = cart_item.quantity

                self.send_product_details(
                    chat_id, client, product, quantity,
                    is_small, is_big, is_hot, is_cold,
                    cart_item.id
                )
                self.bot.answer_callback_query(call.id)

                if chat_id in self.user_data:
                    del self.user_data[chat_id]

            except Exception as e:
                logger.error(f"Error in handle_temp_selection: {e}")
                error_message = "Произошла ошибка при выборе температуры." if language_code == 'ru' else "Haroratni tanlashda xatolik yuz berdi."
                self.bot.send_message(chat_id, error_message)

        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("increase_") or call.data.startswith("decrease_"))
        def update_quantity(call):
            try:
                chat_id = call.message.chat.id
                message_id = call.message.message_id
                client = Client.objects.get(telegram_id=chat_id)
                language_code = client.preferred_language
                data = call.data.split("_")
                action = data[0]
                cart_item_id = int(data[1])

                cart_item = Cart.objects.get(id=cart_item_id, client=client)

                if action == "increase":
                    cart_item.quantity += 1
                elif action == "decrease":
                    cart_item.quantity = max(0, cart_item.quantity - 1)

                cart_item.save()

                quantity = cart_item.quantity

                self.send_product_details(
                    chat_id, client, cart_item.product, quantity,
                    cart_item.is_small, cart_item.is_big, cart_item.is_hot, cart_item.is_cold,
                    cart_item.id, message_id=message_id
                )
                success_message = "Количество обновлено." if language_code == 'ru' else "Miqdori yangilandi."
                self.bot.answer_callback_query(call.id, text=success_message)

            except Exception as e:
                logger.error(f"Ошибка при обновлении количества: {e}")
                error_message = "Ошибка при обновлении." if language_code == 'ru' else "Yangilashda xatolik yuz berdi."
                self.bot.answer_callback_query(call.id, text=error_message)

        @self.bot.callback_query_handler(func=lambda call: call.data == "quantity_do_nothing")
        def quantity_do_nothing(call):
            self.bot.answer_callback_query(call.id)

        @self.bot.message_handler(func=lambda message: message.text in ["🛒 Корзина", "🛒 Savat"])
        def handle_cart(message):
            chat_id = message.chat.id
            try:
                client = Client.objects.get(telegram_id=chat_id)
                self.show_cart(chat_id, client)
            except Client.DoesNotExist:
                self.bot.send_message(chat_id=chat_id, text="Пожалуйста, начните с команды /start.")

        @self.bot.callback_query_handler(func=lambda call: call.data == "view_cart")
        def view_cart(call):
            chat_id = call.message.chat.id
            try:
                client = Client.objects.get(telegram_id=chat_id)
            except Client.DoesNotExist:
                self.bot.answer_callback_query(
                    call.id,
                    text="Клиент не найден",
                    show_alert=True
                )
                return

            self.show_cart(chat_id, client)
            self.bot.answer_callback_query(call.id)

        @self.bot.callback_query_handler(func=lambda call: call.data == "checkout")
        def checkout(call):
            chat_id = call.message.chat.id
            client = Client.objects.get(telegram_id=chat_id)
            cart_items = Cart.objects.filter(client=client, quantity__gt=0)
            if not cart_items.exists():
                self.bot.answer_callback_query(
                    call.id,
                    text="Корзина пуста" if client.preferred_language == 'ru' else "Savat bo'sh",
                    show_alert=True
                )
                return

            uzbekistan_tz = pytz.timezone('Asia/Tashkent')
            current_time = datetime.now(uzbekistan_tz).time()
            start_time = time(6, 0, 0)
            end_time = time(1, 0, 0)

            if not ((start_time <= current_time <= time(23, 59, 59)) or (time(0, 0, 0) <= current_time <= end_time)):
                self.bot.answer_callback_query(
                    call.id,
                    text="Заказы принимаются с 10:00 до 01:00" if client.preferred_language == 'ru' else "Buyurtmalar 10:00 dan 01:00 gacha qabul qilinadi",
                    show_alert=True
                )
                return
            self.bot.answer_callback_query(call.id)

            location_keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            location_button = KeyboardButton(
                text="📍 Отправить местоположение" if client.preferred_language == 'ru' else "📍 Joylashuvni yuborish",
                request_location=True
            )
            location_keyboard.add(location_button)
            self.bot.send_message(
                chat_id=chat_id,
                text="Пожалуйста, отправьте ваше местоположение для расчета стоимости доставки." if client.preferred_language == 'ru' else "Iltimos, yetkazib berish narxini hisoblash uchun joylashuvingizni yuboring.",
                reply_markup=location_keyboard
            )

        @self.bot.message_handler(content_types=['location'])
        def handle_location(message):
            chat_id = message.chat.id
            try:
                client = Client.objects.get(telegram_id=chat_id)
            except Client.DoesNotExist:
                self.bot.send_message(chat_id=chat_id, text="Пожалуйста, начните с команды /start.")
                return

            cart_items = Cart.objects.filter(client=client, quantity__gt=0)
            if not cart_items.exists():
                self.bot.send_message(
                    chat_id=chat_id,
                    text="У вас нет товаров в корзине. Пожалуйста, добавьте товары в корзину перед оформлением заказа." if client.preferred_language == 'ru' else "Sizning savatingiz bo'sh. Buyurtma berishdan oldin savatga mahsulot qo'shing."
                )
                self.send_main_menu(chat_id, client.preferred_language)
                return

            user_latitude = message.location.latitude
            user_longitude = message.location.longitude

            cart_data = []
            total_price = 0
            for item in cart_items:
                unit_price = item.product.get_price(is_small=item.is_small, is_big=item.is_big) or 0
                price = unit_price * item.quantity
                total_price += price
                cart_data.append({
                    'product_title_ru': item.product.title_ru,
                    'product_title_uz': item.product.title_uz,
                    'quantity': item.quantity,
                    'price': unit_price,
                    'is_small': item.is_small,
                    'is_big': item.is_big,
                    'is_hot': item.is_hot,
                    'is_cold': item.is_cold,
                    'small_volume': item.product.small_volume,
                    'big_volume': item.product.big_volume,
                })

            order = Order.objects.create(
                client=client,
                total_price=total_price,
                status='pending',
                cart_data_json=cart_data
            )

            cart_items.delete()

            order.latitude = user_latitude
            order.longitude = user_longitude

            cafe_latitude = 41.314652
            cafe_longitude = 69.240562

            client_location = (user_latitude, user_longitude)
            cafe_location = (cafe_latitude, cafe_longitude)
            distance_km = geodesic(client_location, cafe_location).km

            delivery_rate_per_km = 3800
            delivery_cost = int(distance_km * delivery_rate_per_km)

            order.delivery_address = f"{user_latitude}, {user_longitude}"
            order.delivery_cost = delivery_cost
            order.total_price += delivery_cost
            order.save()

            self.send_payment_invoice(chat_id, client, order, cart_data)

        @self.bot.message_handler(func=lambda message: message.text in ["⚙️ Настройки", "⚙️ Sozlamalar"])
        def handle_settings(message):
            chat_id = message.chat.id
            try:
                client = Client.objects.get(telegram_id=chat_id)
                self.send_settings(chat_id, client.preferred_language)
            except Client.DoesNotExist:
                self.bot.send_message(chat_id=chat_id, text="Пожалуйста, начните с команды /start.")

        @self.bot.callback_query_handler(func=lambda call: call.data == "settings_language")
        def change_language(call):
            chat_id = call.message.chat.id
            self.bot.answer_callback_query(call.id)
            self.ask_language(chat_id)

        @self.bot.callback_query_handler(func=lambda call: call.data == "settings_phone")
        def change_phone_number(call):
            chat_id = call.message.chat.id
            client = Client.objects.get(telegram_id=chat_id)
            self.bot.answer_callback_query(call.id)
            self.ask_phone_number(chat_id, client)

        @self.bot.message_handler(func=lambda message: message.text in ["🎁 Мои заказы", "🎁 Buyurtmalarim"])
        def handle_my_orders(message):
            chat_id = message.chat.id
            try:
                client = Client.objects.get(telegram_id=chat_id)
                orders = Order.objects.filter(client=client).order_by('-id')[:4]

                if not orders.exists():
                    self.bot.send_message(
                        chat_id=chat_id,
                        text="У вас нет заказов." if client.preferred_language == 'ru' else "Sizda buyurtmalar yo'q."
                    )
                    return
                for order in orders:
                    cart_data = order.cart_data_json if order.cart_data_json else None

                    order_text, order_keyboard = self.format_order_text(order, client.preferred_language, cart_data)
                    self.bot.send_message(
                        chat_id=chat_id,
                        text=order_text,
                        reply_markup=order_keyboard,
                        parse_mode='HTML'
                    )
            except Client.DoesNotExist:
                self.bot.send_message(chat_id=chat_id, text="Пожалуйста, начните с команды /start.")

        @self.bot.callback_query_handler(func=lambda call: call.data == "clear_cart")
        def clear_cart(call):
            chat_id = call.message.chat.id
            message_id = call.message.message_id
            try:
                client = Client.objects.get(telegram_id=chat_id)
                language_code = client.preferred_language

                Cart.objects.filter(client=client).delete()

                self.bot.delete_message(chat_id, message_id)

                cleared_message = "Корзина успешно очищена." if language_code == 'ru' else "Savat muvaffaqiyatli tozalandi."
                self.bot.send_message(chat_id, cleared_message)

            except Client.DoesNotExist:
                self.bot.answer_callback_query(
                    call.id,
                    text="Клиент не найден." if language_code == 'ru' else "Mijoz topilmadi.",
                    show_alert=True
                )
            except Exception as e:
                logger.error(f"Ошибка при очистке корзины: {e}")
                self.bot.answer_callback_query(
                    call.id,
                    text="Произошла ошибка при очистке корзины." if language_code == 'ru' else "Savatni tozalashda xatolik yuz berdi.",
                    show_alert=True
                )

        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("back_to_products_"))
        def handle_back_to_products(call):
            chat_id = call.message.chat.id
            message_id = call.message.message_id

            try:
                data_parts = call.data.split("_")
                category_id = int(data_parts[3])

                client = Client.objects.get(telegram_id=chat_id)
                language_code = client.preferred_language or 'ru'

                self.send_products(chat_id, category_id, language_code)
                self.bot.answer_callback_query(call.id)

            except Client.DoesNotExist:
                self.bot.answer_callback_query(
                    call.id,
                    text="Клиент не найден." if language_code == 'ru' else "Mijoz topilmadi.",
                    show_alert=True
                )
            except Exception as e:
                logger.error(f"Error in handle_back_to_products: {e}")
                self.bot.answer_callback_query(
                    call.id,
                    text="Произошла ошибка." if language_code == 'ru' else "Xatolik yuz berdi.",
                    show_alert=True
                )

        @self.bot.callback_query_handler(func=lambda call: call.data == "back_to_categories")
        def handle_back_to_categories(call):
            chat_id = call.message.chat.id
            client = Client.objects.get(telegram_id=chat_id)
            self.send_categories(chat_id, client.preferred_language)
            self.bot.answer_callback_query(call.id)

        @self.bot.callback_query_handler(func=lambda call: call.data == "back_to_main")
        def handle_back_to_main(call):
            chat_id = call.message.chat.id
            client = Client.objects.get(telegram_id=chat_id)
            self.send_main_menu(chat_id, client.preferred_language)
            self.bot.answer_callback_query(call.id)

        @self.bot.message_handler(func=lambda message: message.text.startswith("🚚 Ваш заказ") or message.text.startswith("🚚 Buyurtma"))
        def handle_current_order_status(message):
            chat_id = message.chat.id
            try:
                client = Client.objects.get(telegram_id=chat_id)
                order = Order.objects.filter(client=client).order_by('-id').first()

                if not order or order.status not in ['in_progress', 'delivering', 'completed']:
                    self.bot.send_message(
                        chat_id=chat_id,
                        text="У вас нет активных заказов." if client.preferred_language == 'ru' else "Sizda faol buyurtma yo'q."
                    )
                    return

                cart_data = order.cart_data_json if order.cart_data_json else []
                order_text, _ = self.format_order_text(order, client.preferred_language, cart_data)

                if order.courier_name and order.car_number and order.car_model:
                    courier_info = (
                        f"\n\n<b>Информация о курьере:</b>\n"
                        f"👤 Курьер: {order.courier_name}\n"
                        f"🚘 Машина: {order.car_model} (№ {order.car_number})"
                        if client.preferred_language == 'ru'
                        else f"\n\n<b>Kuryer haqida ma'lumot:</b>\n"
                             f"👤 Kuryer: {order.courier_name}\n"
                             f"🚘 Mashina: {order.car_model} (№ {order.car_number})"
                    )
                    order_text += courier_info

                self.bot.send_message(
                    chat_id=chat_id,
                    text=order_text,
                    parse_mode='HTML'
                )
            except Client.DoesNotExist:
                self.bot.send_message(chat_id=chat_id, text="Пожалуйста, начните с команды /start.")
            except Exception as e:
                logger.error(f"Ошибка в handle_current_order_status: {e}")
                self.bot.send_message(chat_id=chat_id, text="Произошла ошибка при получении информации о заказе.")

        @self.bot.pre_checkout_query_handler(func=lambda query: True)
        def checkout_handler(pre_checkout_query):
            self.bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("assign_courier_"))
        def handle_assign_courier(call):
            order_id_str = call.data[len('assign_courier_'):]
            try:
                order_id = int(order_id_str)
                self.assign_courier(order_id, call)
            except ValueError:
                self.bot.answer_callback_query(call.id, "Некорректный ID заказа.")

        @self.bot.message_handler(func=lambda message: self.is_waiting_for_courier_data(message))
        def handle_courier_data(message):
            self.process_courier_data(message)

        @self.bot.message_handler(content_types=['successful_payment'])
        def got_payment(message):
            chat_id = message.chat.id

            try:
                client = Client.objects.get(telegram_id=chat_id)
            except Client.DoesNotExist:
                self.bot.send_message(chat_id=chat_id, text="Пожалуйста, начните с команды /start.")
                return

            order_payload = message.successful_payment.invoice_payload
            try:
                order_id = int(order_payload.split('_')[1])
                order = Order.objects.get(id=order_id, client=client)
            except (IndexError, ValueError, Order.DoesNotExist):
                self.bot.send_message(chat_id=chat_id, text="Произошла ошибка при обработке вашего заказа.")
                return

            order.status = 'in_progress'
            order.save()

            self.bot.send_message(
                chat_id=chat_id,
                text="Спасибо за оплату! Ваш заказ принят и находится в обработке." if client.preferred_language == 'ru' else "To'lovingiz uchun rahmat! Buyurtmangiz qabul qilindi va qayta ishlanmoqda."
            )
            self.send_main_menu(chat_id, client.preferred_language)

            cart_data = order.cart_data_json if order.cart_data_json else []
            self.send_order_to_group(order, cart_data=cart_data)

            client.order_in_progress = None
            client.save()

    def greet_and_ask_language(self, chat_id):
        self.bot.send_message(
            chat_id=chat_id,
            text="""Assalomu alaykum Dragon Tea botiga xush kelibsiz!
Здравствуйте, вас приветствует бот Dragon Tea!
""",
            reply_markup=types.ReplyKeyboardRemove()
        )
        self.ask_language(chat_id)
    def ask_language(self, chat_id):
        language_keyboard = InlineKeyboardMarkup()
        language_keyboard.add(
            InlineKeyboardButton("🇺🇿 O'zbek", callback_data="language_uz"),
            InlineKeyboardButton("🇷🇺 Русский", callback_data="language_ru")
        )
        self.bot.send_message(
            chat_id=chat_id,
            text="🇺🇿 Muloqot tilini tanlang\n🇷🇺 Выберите язык",
            reply_markup=language_keyboard
        )

    def ask_phone_number(self, chat_id, client):
        phone_keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        phone_button = KeyboardButton(
            text="📞 Telefon raqamni yuborish" if client.preferred_language == 'uz' else "📞 Отправить номер телефона",
            request_contact=True
        )
        phone_keyboard.add(phone_button)
        self.bot.send_message(
            chat_id=chat_id,
            text="Telefon raqamingizni yuboring:" if client.preferred_language == 'uz' else "Отправьте ваш номер телефона:",
            reply_markup=phone_keyboard
        )

    def send_main_menu(self, chat_id, language_code):
        main_menu_keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)

        if language_code == 'ru':
            main_menu_keyboard.add(
                KeyboardButton("🍽️ Меню"),
                KeyboardButton("🎁 Мои заказы"),
                KeyboardButton("🛒 Корзина"),
                KeyboardButton("⚙️ Настройки")
            )
        elif language_code == 'uz':
            main_menu_keyboard.add(
                KeyboardButton("🍽️ Menu"),
                KeyboardButton("🎁 Buyurtmalarim"),
                KeyboardButton("🛒 Savat"),
                KeyboardButton("⚙️ Sozlamalar")
            )

        try:
            client = Client.objects.get(telegram_id=chat_id)
            order = Order.objects.filter(client=client).order_by('-id').first()

            if order and order.status in ['in_progress', 'delivering']:
                if language_code == 'ru':
                    status_text = {
                        'in_progress': "В обработке",
                        'delivering': "Доставляется",
                    }
                    button_text = f"🚚 Ваш заказ: {status_text.get(order.status, 'Неизвестно')}"
                elif language_code == 'uz':
                    status_text = {
                        'in_progress': "Qayta ishlanmoqda",
                        'delivering': "Yetkazilmoqda",
                    }
                    button_text = f"🚚 Buyurtma: {status_text.get(order.status, 'Noma’lum')}"

                main_menu_keyboard.add(KeyboardButton(button_text))

        except Client.DoesNotExist:
            pass

        self.bot.send_message(
            chat_id=chat_id,
            text="Asosiy menyu" if language_code == 'uz' else "Главное меню",
            reply_markup=main_menu_keyboard
        )


    def send_categories(self, chat_id, language_code):

        categories = Category.objects.all()
        if not categories.exists():
            self.bot.send_message(
                chat_id=chat_id,
                text="Menu mavjud emas." if language_code == 'uz' else "Меню отсутствуют."
            )
            return

        content = "<h1>Menu</h1>\n" if language_code == 'uz' else "<h1>Меню</h1>\n"
        for category in categories:
            category_title = category.title_uz if language_code == 'uz' else category.title_ru
            content += f"<p>➡️ <strong>{category_title}</strong></p>\n"




        telegraph_url = f"https://telegra.ph/DRAGON-TEA-MENU-12-06"

        category_keyboard = InlineKeyboardMarkup(row_width=2)
        buttons = []
        for category in categories:
            category_title = category.title_uz if language_code == 'uz' else category.title_ru
            buttons.append(InlineKeyboardButton(
                text=category_title,
                callback_data=f"category_{category.id}"
            ))
        category_keyboard.add(*buttons)
        category_keyboard.add(
            InlineKeyboardButton(
                "🔙 Orqaga" if language_code == 'uz' else "🔙 Назад",
                callback_data="back_to_main"
            )
        )

        self.bot.send_message(
            chat_id=chat_id,
            text=f"📰 <a href='{telegraph_url}'>MENU</a>",
            reply_markup=category_keyboard,
            parse_mode="HTML"
        )


    def send_products(self, chat_id, category_id, language_code):
        products = Product.objects.filter(category_id=category_id)
        if not products.exists():
            self.bot.send_message(
                chat_id=chat_id,
                text="Mahsulotlar mavjud emas." if language_code == 'uz' else "Товары отсутствуют."
            )
            return

        product_keyboard = InlineKeyboardMarkup(row_width=2)
        buttons = []
        for product in products:
            product_title = product.title_uz if language_code == 'uz' else product.title_ru
            buttons.append(InlineKeyboardButton(
                text=product_title,
                callback_data=f"product_{product.id}"
            ))
        product_keyboard.add(*buttons)
        product_keyboard.add(
            InlineKeyboardButton(
                "🔙 Orqaga" if language_code == 'uz' else "🔙 Назад",
                callback_data="back_to_categories"
            )
        )
        self.bot.send_message(
            chat_id=chat_id,
            text="Mahsulotni tanlang:" if language_code == 'uz' else "Выберите продукт:",
            reply_markup=product_keyboard
        )

    def show_cart(self, chat_id, client):
        # Исправленный подсчёт цены:
        cart_items = Cart.objects.filter(client=client, quantity__gt=0)
        language_code = client.preferred_language

        if not cart_items.exists():
            empty_cart_message = "Корзина пуста" if language_code == 'ru' else "Savat bo'sh"
            self.bot.send_message(chat_id=chat_id, text=empty_cart_message)
            return

        cart_text = "🛒 Ваша корзина:\n" if language_code == 'ru' else "🛒 Savatingiz:\n"
        total_price = 0
        for item in cart_items:
            unit_price = item.product.get_price(is_small=item.is_small, is_big=item.is_big) or 0
            price = unit_price * item.quantity
            product_title = item.product.title_ru if language_code == 'ru' else item.product.title_uz

            size_text = ""
            if item.is_small:
                size_text = f"Маленький {item.product.small_volume}" if language_code == 'ru' else f"Kichik {item.product.small_volume}"
            elif item.is_big:
                size_text = f"Большой {item.product.big_volume}" if language_code == 'ru' else f"Katta {item.product.big_volume}"

            total_price += price
            cart_text += f"{product_title} ({size_text}) x {item.quantity} = {price} {'сум' if language_code == 'ru' else 'so‘m'}\n"

        total_text = "Итого" if language_code == 'ru' else "Jami"
        cart_text += f"\n{total_text}: {total_price} {'сум' if language_code == 'ru' else 'so‘m'}"

        cart_keyboard = InlineKeyboardMarkup(row_width=2)
        cart_keyboard.add(
            InlineKeyboardButton(
                "✅ Оформить заказ" if language_code == 'ru' else "✅ Buyurtma berish",
                callback_data="checkout"
            ),
            InlineKeyboardButton(
                "🗑️ Очистить корзину" if language_code == 'ru' else "🗑️ Savatni tozalash",
                callback_data="clear_cart"
            )
        )
        cart_keyboard.add(
            InlineKeyboardButton(
                "🔙 Назад" if language_code == 'ru' else "🔙 Orqaga",
                callback_data="back_to_main"
            )
        )

        self.bot.send_message(chat_id, cart_text, reply_markup=cart_keyboard)


    def send_settings(self, chat_id, language_code):
        client = Client.objects.get(telegram_id=chat_id)

        language_map = {
            'ru': '🇷🇺 Русский',
            'uz': "🇺🇿 O'zbek",
        }

        client_language = language_map.get(client.preferred_language, 'Неизвестно')
        client_phone = client.phone_number or 'Не указан'

        if language_code == 'ru':
            settings_text = (
                f"Язык: {client_language}\n"
                f"Телефон: {client_phone}\n"
                "Выберите одно из следующих:"
            )
        elif language_code == 'uz':
            settings_text = (
                f"Til: {client_language}\n"
                f"Telefon: {client_phone}\n"
                "Quyidagilardan birini tanlang:"
            )
        else:
            settings_text = "Настройки"

        settings_keyboard = InlineKeyboardMarkup()
        settings_keyboard.add(
            InlineKeyboardButton(
                "🌐 Tilni o'zgartirish" if language_code == 'uz' else "🌐 Изменить язык",
                callback_data="settings_language"
            ),
            InlineKeyboardButton(
                "📞 Raqamni o'zgartirish" if language_code == 'uz' else "📞 Изменить номер",
                callback_data="settings_phone"
            ),
        )
        settings_keyboard.add(
            InlineKeyboardButton(
                "🔙 Orqaga" if language_code == 'uz' else "🔙 Назад",
                callback_data="back_to_main"
            )
        )

        self.bot.send_message(
            chat_id=chat_id,
            text=settings_text,
            reply_markup=settings_keyboard
        )

    def send_product_details(self, chat_id, client, product, quantity, is_small, is_big, is_hot, is_cold, cart_item_id, message_id=None):
        language_code = client.preferred_language

        unit_price = product.get_price(is_small=is_small, is_big=is_big) or 0

        size_text = ""
        if is_small:
            size_text = f"Маленький {product.small_volume}" if language_code == 'ru' else f"Kichik {product.small_volume}"
        elif is_big:
            size_text = f"Большой {product.big_volume}" if language_code == 'ru' else f"Katta {product.big_volume}"

        temp_text = ""
        if is_hot:
            temp_text = "🔥 Горячий" if language_code == 'ru' else "🔥 Issiq"
        elif is_cold:
            temp_text = "❄️ Холодный" if language_code == 'ru' else "❄️ Sovuq"

        details = (
            f"🛍️ {product.title_ru if language_code == 'ru' else product.title_uz}\n"
            f"{'Размер' if language_code == 'ru' else 'Hajmi'}: {size_text}\n"
            f"{'Температура' if language_code == 'ru' else 'Harorati'}: {temp_text}\n"
            f"💵 {'Цена' if language_code == 'ru' else 'Narxi'}: {unit_price} {'сум' if language_code == 'ru' else 'so‘m'}\n"
            f"📦 {'Количество' if language_code == 'ru' else 'Miqdori'}: {quantity}\n"
            f"💰 {'Общая стоимость' if language_code == 'ru' else 'Umumiy narxi'}: {unit_price * quantity} {'сум' if language_code == 'ru' else 'so‘m'}\n"
        )
        category_id = product.category.id if product.category else 0

        product_keyboard = InlineKeyboardMarkup(row_width=3)
        product_keyboard.add(
            InlineKeyboardButton("➖", callback_data=f"decrease_{cart_item_id}"),
            InlineKeyboardButton(f"{quantity}", callback_data="quantity_do_nothing"),
            InlineKeyboardButton("➕", callback_data=f"increase_{cart_item_id}")
        )
        product_keyboard.add(
            InlineKeyboardButton(
                "🛒 Корзина" if language_code == 'ru' else "🛒 Savat",
                callback_data="view_cart"
            ),
            InlineKeyboardButton(
                "🔙 Назад" if language_code == 'ru' else "🔙 Orqaga",
                callback_data=f"back_to_products_{category_id}"
            )
        )

        if product.image:
            photo = open(product.image.path, 'rb')
        else:
            photo = None

        if message_id:
            if photo:
                media = types.InputMediaPhoto(media=photo, caption=details)
                self.bot.edit_message_media(
                    media=media,
                    chat_id=chat_id,
                    message_id=message_id,
                    reply_markup=product_keyboard
                )
                photo.close()
            else:
                self.bot.edit_message_caption(
                    chat_id=chat_id,
                    message_id=message_id,
                    caption=details,
                    reply_markup=product_keyboard
                )
        else:
            if photo:
                self.bot.send_photo(
                    chat_id=chat_id,
                    photo=photo,
                    caption=details,
                    reply_markup=product_keyboard
                )
                photo.close()
            else:
                self.bot.send_message(
                    chat_id=chat_id,
                    text=details,
                    reply_markup=product_keyboard
                )
    def format_order_text(self, order, language_code, cart_data=None, is_admin=False):
        status_display = {
            'ru': {
                'pending': 'Ожидание оплаты',
                'in_progress': 'В процессе',
                'delivering': 'Доставляется',
                'completed': 'Завершён',
                'canceled': 'Отменён',
                'closed': 'Закрыт',
            },
            'uz': {
                'pending': "To'lov kutilyapti",
                'in_progress': 'Jarayonda',
                'delivering': 'Yetkazilmoqda',
                'completed': 'Yakunlangan',
                'canceled': 'Bekor qilingan',
                'closed': 'Yopilgan',
            },
        }

        order_status = status_display.get(language_code, status_display['ru']).get(order.status, order.status)

        if language_code == 'ru':
            order_text = f"🧾 <b>Заказ №{order.id}</b>\n"
            order_text += f"👤 <b>Клиент:</b> @{order.client.telegram_username or order.client.name}\n"
            order_text += f"📞 <b>Телефон:</b> {order.client.phone_number}\n"
            order_text += f"📦 <b>Статус:</b> #{order_status}\n"
            order_text += f"""📍 <b>Адрес доставки:</b> GOOGLE MAPS: https://www.google.com/maps?q={order.delivery_address.replace(' ', '')}\n\n"""
        else:
            order_text = f"🧾 <b>Buyurtma №{order.id}</b>\n"
            order_text += f"👤 <b>Mijoz:</b> @{order.client.telegram_username or order.client.name}\n"
            order_text += f"📞 <b>Telefon:</b> {order.client.phone_number}\n"
            order_text += f"📦 <b>Holati:</b> #{order_status}\n"
            order_text += f"""📍 <b>Yetkazib berish manzili:</b> GOOGLE MAPS: https://www.google.com/maps?q={order.delivery_address.replace(' ', '')}\n\n"""

        if cart_data:
            order_text += "🛒 <b>Товары:</b>\n" if language_code == 'ru' else "🛒 <b>Mahsulotlar:</b>\n"

            for item in cart_data:
                product_title = item['product_title_ru'] if language_code == 'ru' else item['product_title_uz']
                quantity = item['quantity']
                unit_price = item['price']
                total_price = quantity * unit_price

                size_text = ""
                if item.get('is_small'):
                    small_volume = item.get('small_volume') or ''
                    size_text = f"Маленький {small_volume} ml" if language_code == 'ru' else f"Kichik {small_volume} ml"
                elif item.get('is_big'):
                    big_volume = item.get('big_volume') or ''
                    size_text = f"Большой {big_volume} ml" if language_code == 'ru' else f"Katta {big_volume} ml"

                temp_text = ""
                if item.get('is_hot'):
                    temp_text = "🔥 Горячий" if language_code == 'ru' else "🔥 Issiq"
                elif item.get('is_cold'):
                    temp_text = "❄️ Холодный" if language_code == 'ru' else "❄️ Sovuq"

                if language_code == 'ru':
                    order_text += f"• <b>{product_title}</b> ({size_text}, {temp_text})\n  {quantity}️⃣ ✖️ {unit_price:,.0f} = {total_price:,.0f} сум\n"
                else:
                    order_text += f"• <b>{product_title}</b> ({size_text}, {temp_text})\n  {quantity}️⃣ ✖️ {unit_price:,.0f} = {total_price:,.0f} so‘m\n"

        if language_code == 'ru':
            order_text += f"\n📦 <b>Сумма товаров:</b>    {order.total_price - order.delivery_cost:,.0f} сум\n"
            order_text += f"🚚 <b>Доставка:</b>    {order.delivery_cost:,.0f} сум\n"
            order_text += f"💰 <b>Итого:</b>    {order.total_price:,.0f} сум"
        else:
            order_text += f"\n📦 <b>Mahsulotlar summasi:</b>    {order.total_price - order.delivery_cost:,.0f} so‘m\n"
            order_text += f"🚚 <b>Yetkazib berish:</b>    {order.delivery_cost:,.0f} so‘m\n"
            order_text += f"💰 <b>Jami:</b>    {order.total_price:,.0f} so‘m"

        if is_admin:
            order_keyboard = InlineKeyboardMarkup(row_width=2)
            if order.status in ['pending', 'in_progress', 'delivering']:
                assign_courier_button = InlineKeyboardButton(
                    "Передать курьеру" if language_code == 'ru' else "Kuryerga berish",
                    callback_data=f"assign_courier_{order.id}"
                )
                close_order_button = InlineKeyboardButton(
                    "Закрыть заказ" if language_code == 'ru' else "Buyurtmani yopish",
                    callback_data=f"close_order_{order.id}"
                )
                order_keyboard.add(assign_courier_button, close_order_button)
            elif order.status == 'completed':
                close_order_button = InlineKeyboardButton(
                    "Закрыть заказ" if language_code == 'ru' else "Buyurtmani yopish",
                    callback_data=f"close_order_{order.id}"
                )
                order_keyboard.add(close_order_button)
            else:
                order_keyboard = None

            return order_text, order_keyboard
        else:
            return order_text, None

    def send_payment_invoice(self, chat_id, client, order, cart_data):
        PAYMENT_PROVIDER_TOKEN = os.getenv('PAYMENT_PROVIDER_TOKEN')

        language_code = client.preferred_language

        delivery_cost = order.delivery_cost
        products_cost = order.total_price - delivery_cost

        product_lines = []
        for item in cart_data:
            product_title = item['product_title_ru'] if language_code == 'ru' else item['product_title_uz']
            line = f"{product_title} x {item['quantity']} - {item['price'] * item['quantity']} {'сум' if language_code == 'ru' else 'so‘m'}"
            product_lines.append(line)
        products_details = '\n'.join(product_lines)

        if language_code == 'ru':
            title = "Оплата заказа"
            description = (
                f"Ваш заказ на сумму {order.total_price} сум\n"
                f"Товары:\n{products_details}\n"
                f"Доставка: {delivery_cost} сум"
            )
            price_label_products = 'Товары'
            price_label_delivery = 'Доставка'
        elif language_code == 'uz':
            title = "Buyurtma uchun to'lov"
            description = (
                f"Sizning buyurtmangiz summasi {order.total_price} so'm\n"
                f"Mahsulotlar:\n{products_details}\n"
                f"Yetkazib berish: {delivery_cost} so'm"
            )
            price_label_products = 'Mahsulotlar'
            price_label_delivery = 'Yetkazib berish'
        else:
            title = "Оплата заказа"
            description = (
                f"Ваш заказ на сумму {order.total_price} сум\n"
                f"Товары:\n{products_details}\n"
                f"Доставка: {delivery_cost} сум"
            )
            price_label_products = 'Товары'
            price_label_delivery = 'Доставка'

        prices = [
            types.LabeledPrice(label=price_label_products, amount=int(products_cost * 100)),
            types.LabeledPrice(label=price_label_delivery, amount=int(delivery_cost * 100))
        ]

        payload = f"order_{order.id}"

        self.bot.send_invoice(
            chat_id=chat_id,
            title=title,
            description=description,
            provider_token=PAYMENT_PROVIDER_TOKEN,
            currency='UZS',
            prices=prices,
            start_parameter='payment',
            invoice_payload=payload
        )

    def send_order_to_group(self, order, cart_data):
        GROUP_CHAT_ID = int(os.getenv('GROUP_CHAT_ID'))
        cart_data = order.cart_data_json if order.cart_data_json else []

        language_code = order.client.preferred_language or 'ru'

        order_text, order_keyboard = self.format_order_text(order, language_code, cart_data, is_admin=True)

        self.bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=order_text,
            reply_markup=order_keyboard,
            parse_mode='HTML'
        )

    def is_waiting_for_courier_data(self, message):
        user_id = message.from_user.id
        return user_id in self.admin_data and self.admin_data[user_id]['waiting_for_data'] and message.reply_to_message and message.reply_to_message.message_id == self.admin_data[user_id]['message_id']

    def process_courier_data(self, message):
        user_id = message.from_user.id
        admin_info = self.admin_data.get(user_id, {})
        order_id = admin_info.get('order_id')

        if not order_id:
            self.bot.send_message(
                chat_id=message.chat.id,
                text="⚠️ Нет активного заказа для обработки. Попробуйте снова."
            )
            return

        if not message.reply_to_message or message.reply_to_message.message_id != admin_info.get('message_id'):
            self.bot.send_message(
                chat_id=message.chat.id,
                text="⚠️ Пожалуйста, ответьте на ожидаемое сообщение."
            )
            return

        try:
            order = Order.objects.get(id=order_id)
            text = message.text.strip()

            parts = [part.strip() for part in text.split(',')]
            if len(parts) != 3:
                error_text = (
                    "⚠️ <b>Ошибка:</b> Данные не соответствуют формату.\n\n"
                    "💡 <b>Формат:</b>\n"
                    "Имя курьера, Номер машины, Модель машины\n\n"
                    "🔍 <b>Пример:</b>\n"
                    "Иван Иванов, 01A123AA, Toyota Corolla"
                )
                self.bot.send_message(
                    chat_id=message.chat.id,
                    text=error_text,
                    parse_mode="HTML",
                    reply_markup=types.ForceReply(selective=True)
                )
                return

            courier_name, car_number, car_model = parts

            order.courier_name = courier_name
            order.car_model = car_model
            order.car_number = car_number
            order.status = 'delivering'
            order.save()

            success_message = (
                "✅ <b>Данные курьера успешно добавлены и отправлены клиенту.</b>\n"
                "Заказ обновлён."
            )
            self.bot.send_message(
                chat_id=message.chat.id,
                text=success_message,
                parse_mode="HTML"
            )

            del self.admin_data[user_id]

            self.send_order_update_to_client(order)
            self.send_order_update(order)

        except Order.DoesNotExist:
            self.bot.send_message(
                chat_id=message.chat.id,
                text="⚠️ Заказ не найден. Попробуйте снова."
            )
            if user_id in self.admin_data:
                del self.admin_data[user_id]

    def assign_courier(self, order_id, call):
        try:
            order = Order.objects.get(id=order_id)
            language_code = order.client.preferred_language or 'ru'
            chat_id = call.message.chat.id
            user_id = call.from_user.id

            if order.status in ['pending', 'in_progress']:
                example_text = (
                    "<b>Введите данные курьера для данного заказа:</b>\n\n"
                    "💡 <b>Формат:</b>\n"
                    "Имя курьера, Номер машины, Модель машины\n\n"
                    "🔍 <b>Пример:</b>\n"
                    "Иван Иванов, 01A123AA, Toyota Corolla"
                )
                force_reply = types.ForceReply(selective=True)
                sent_message = self.bot.send_message(
                    chat_id=chat_id,
                    text=example_text,
                    reply_markup=force_reply,
                    parse_mode="HTML"
                )
                self.admin_data[user_id] = {
                    'order_id': order_id,
                    'message_id': sent_message.message_id,
                    'waiting_for_data': True
                }
                self.bot.answer_callback_query(call.id)
            else:
                self.bot.answer_callback_query(
                    call.id,
                    text="Нельзя передать курьеру заказ с текущим статусом." if language_code == 'ru' else "Buyurtmani joriy holatda kuryerga berish mumkin emas."
                )
        except Order.DoesNotExist:
            self.bot.answer_callback_query(
                call.id,
                text="Заказ не найден." if language_code == 'ru' else "Buyurtma topilmadi."
            )

    def close_order(self, order_id, call):
        try:
            order = Order.objects.get(id=order_id)
            language_code = order.client.preferred_language or 'ru'

            if order.status in ['delivering', 'in_progress']:
                order.status = 'completed'
                order.save()

                self.send_order_update_to_client(order)
                self.send_main_menu(order.client.telegram_id, language_code)
                self.send_order_update(order)

                self.bot.answer_callback_query(call.id, "Заказ закрыт." if language_code == 'ru' else "Buyurtma yopildi.")
            else:
                self.bot.answer_callback_query(call.id, "Нельзя закрыть заказ с текущим статусом." if language_code == 'ru' else "Buyurtmani joriy holatda yopish mumkin emas.")
        except Order.DoesNotExist:
            self.bot.answer_callback_query(call.id, "Заказ не найден." if language_code == 'ru' else "Buyurtma topilmadi.")

    def send_order_update(self, order):
        GROUP_CHAT_ID = int(os.getenv('GROUP_CHAT_ID'))
        cart_data = order.cart_data_json if order.cart_data_json else []

        language_code = order.client.preferred_language or 'ru'

        order_text, order_keyboard = self.format_order_text(order, language_code, cart_data, is_admin=True)

        self.bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=order_text,
            reply_markup=order_keyboard,
            parse_mode='HTML'
        )

    def send_order_update_to_client(self, order):
        try:
            chat_id = order.client.telegram_id
            language_code = order.client.preferred_language or 'ru'

            status_text = "Ваш заказ передан курьеру и доставляется!" if language_code == 'ru' else "Buyurtmangiz kuryerga berildi va yetkazilmoqda!"
            self.bot.send_message(chat_id, text=status_text)

        except Exception as e:
            logger.error(f"Error in send_order_update_to_client: {e}")
            
    def process_selection_without_size(self, chat_id, product, client):
        try:
            # Используем единую цену для продукта
            unit_price = product.small_size_price or product.big_size_price
            price_label = f"{unit_price} {'сум' if client.preferred_language == 'ru' else 'so‘m'}"
    
            # Добавление продукта в корзину
            cart_item, created = Cart.objects.get_or_create(
                client=client,
                product=product,
                defaults={'quantity': 1}
            )
            if not created:
                cart_item.quantity += 1
                cart_item.save()
    
            # Формирование текста для отправки клиенту
            product_details = (
                f"🛍️ {product.title_ru if client.preferred_language == 'ru' else product.title_uz}\n"
                f"💵 {'Цена' if client.preferred_language == 'ru' else 'Narxi'}: {price_label}\n"
                f"📦 {'Количество' if client.preferred_language == 'ru' else 'Miqdor'}: {cart_item.quantity}\n"
                f"💰 {'Итого' if client.preferred_language == 'ru' else 'Jami'}: {unit_price * cart_item.quantity} {'сум' if client.preferred_language == 'ru' else 'so‘m'}"
            )
    
            # Клавиатура для управления корзиной
            product_keyboard = InlineKeyboardMarkup(row_width=3)
            product_keyboard.add(
                InlineKeyboardButton("➖", callback_data=f"decrease_{cart_item.id}"),
                InlineKeyboardButton(f"{cart_item.quantity}", callback_data="quantity_do_nothing"),
                InlineKeyboardButton("➕", callback_data=f"increase_{cart_item.id}")
            )
            product_keyboard.add(
                InlineKeyboardButton(
                    "🛒 Корзина" if client.preferred_language == 'ru' else "🛒 Savat",
                    callback_data="view_cart"
                ),
                InlineKeyboardButton(
                    "🔙 Назад" if client.preferred_language == 'ru' else "🔙 Orqaga",
                    callback_data="back_to_categories"
                )
            )
    
            # Отправка информации клиенту
            self.bot.send_message(chat_id, product_details, reply_markup=product_keyboard)
    
        except Exception as e:
            logger.error(f"Error in process_selection_without_size: {e}")
            self.bot.send_message(chat_id, "Произошла ошибка при обработке продукта.")

