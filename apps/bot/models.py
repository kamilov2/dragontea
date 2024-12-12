from datetime import datetime, timedelta
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

class Client(models.Model):
    telegram_id = models.CharField(
        max_length=155,
        verbose_name=_('Telegram ID'),
        help_text=_('Telegram ID'),
        editable=False,
        blank=True,
        null=True
    )
    name = models.CharField(
        max_length=155,
        verbose_name=_('Name'),
        help_text=_('Name'),
        editable=False,
        blank=True,
        null=True
    )
    telegram_username = models.CharField(
        max_length=155,
        verbose_name=_('Telegram Username'),
        help_text=_('Telegram Username'),
        editable=False,
        blank=True,
        null=True
    )
    phone_number = models.CharField(
        max_length=155,
        verbose_name=_('Phone Number'),
        help_text=_('Phone Number'),
        editable=False,
        blank=True,
        null=True
    )
    city = models.CharField(
        max_length=155,
        verbose_name=_('City'),
        help_text=_('City'),
        blank=True,
        null=True,
        default='Ташкент'
    )
    preferred_language = models.CharField(
        max_length=50,
        verbose_name=_('Preferred Language'),
        help_text=_('Preferred language for bot interaction'),
        choices=[
            ('ru', _('Russian')),
            ('uz', _('Uzbek')),
            ('en', _('English')),
            ('fr', _('French'))
        ],
        blank=True,
        null=True
    )

    class Meta:
        verbose_name = _('Client')
        verbose_name_plural = _('Clients')

    def __str__(self):
        return self.name if self.name else _('Unnamed Client')


class Category(models.Model):
    title_ru = models.CharField(
        max_length=155,
        verbose_name=_('Title (Russian)'),
        help_text=_('Title in Russian')
    )
    title_uz = models.CharField(
        max_length=155,
        verbose_name=_('Title (Uzbek)'),
        help_text=_('Title in Uzbek')
    )
    title = models.CharField(
        max_length=155,
        verbose_name=_('Title'),
        help_text=_('Title')
    )

    class Meta:
        verbose_name = _('Category')
        verbose_name_plural = _('Categories')

    def __str__(self):
        return f'{self.title_ru} / {self.title_uz}'


class Product(models.Model):
    title_ru = models.CharField(
        max_length=155,
        verbose_name=_('Title (Russian)'),
        help_text=_('Title in Russian')
    )
    title_uz = models.CharField(
        max_length=155,
        verbose_name=_('Title (Uzbek)'),
        help_text=_('Title in Uzbek')
    )

    small_price = models.PositiveIntegerField(
        verbose_name=_('Small Size Price'),
        help_text=_('Price for small size in local currency'),
        null=True,
        blank=True
    )
    big_price = models.PositiveIntegerField(
        verbose_name=_('Big Size Price'),
        help_text=_('Price for big size in local currency'),
        null=True,
        blank=True
    )

    image = models.ImageField(
        verbose_name=_('Image'),
        help_text=_('Image'),
        null=True,
        blank=True
    )
    category = models.ForeignKey(
        'Category',
        on_delete=models.SET_NULL,
        verbose_name=_('Category'),
        help_text=_('Category'),
        null=True
    )
    is_small = models.BooleanField(
        default=False,
        verbose_name=_('Has Small Size'),
        help_text=_('Product has small size option')
    )
    is_big = models.BooleanField(
        default=False,
        verbose_name=_('Has Big Size'),
        help_text=_('Product has big size option')
    )
    small_volume = models.PositiveIntegerField(
        default=250,
        verbose_name=_('Small Volume (ml)'),
        help_text=_('Volume of small size in milliliters')
    )
    big_volume = models.PositiveIntegerField(
        default=500,
        verbose_name=_('Big Volume (ml)'),
        help_text=_('Volume of big size in milliliters')
    )
    is_hot = models.BooleanField(
        default=False,
        verbose_name=_('Hot Option'),
        help_text=_('Product has hot option')
    )
    is_cold = models.BooleanField(
        default=False,
        verbose_name=_('Cold Option'),
        help_text=_('Product has cold option')
    )

    class Meta:
        verbose_name = _('Product')
        verbose_name_plural = _('Products')

    def __str__(self):
        return f'{self.title_ru} / {self.title_uz}'

    def get_price(self, is_small=False, is_big=False):
        """Возвращает цену в зависимости от размера."""
        if is_small:
            return self.small_price
        elif is_big:
            return self.big_price
        return 0


class Cart(models.Model):
    client = models.ForeignKey(
        Client,
        on_delete=models.SET_NULL,
        verbose_name=_('Client'),
        help_text=_('Client'),
        null=True
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        verbose_name=_('Product'),
        help_text=_('Product'),
        null=True
    )
    quantity = models.IntegerField(
        verbose_name=_('Quantity'),
        help_text=_('Quantity'),
        default=1
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created At'),
        help_text=_('Time of cart creation')
    )
    is_small = models.BooleanField(default=False, verbose_name='Маленький размер')
    is_big = models.BooleanField(default=False, verbose_name='Большой размер')
    is_hot = models.BooleanField(default=False, verbose_name='Горячий')
    is_cold = models.BooleanField(default=False, verbose_name='Холодный')

    class Meta:
        verbose_name = _('Cart')
        verbose_name_plural = _('Carts')
        unique_together = ('client', 'product', 'is_small', 'is_big', 'is_hot', 'is_cold')

    def __str__(self):
        return f"{self.product.title_ru} - {self.quantity}"


class Order(models.Model):
    client = models.ForeignKey('Client', on_delete=models.SET_NULL, null=True)
    total_price = models.FloatField()
    courier_name = models.CharField(max_length=255, blank=True, null=True, verbose_name="Имя курьера")
    car_number = models.CharField(max_length=50, blank=True, null=True, verbose_name="Номер машины")
    car_model = models.CharField(max_length=100, blank=True, null=True, verbose_name="Модель машины")
    delivery_cost = models.IntegerField(default=0)
    delivery_address = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('in_progress', _('In Progress')),
        ('delivering', _('Delivering')),
        ('completed', _('Completed')),
        ('canceled', _('Canceled')),
        ('closed', _('Closed')),
    ]
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='pending')
    cart_data_json = models.JSONField(null=True, blank=True)

    def save_cart_data(self, cart_data):
        self.cart_data_json = cart_data
        self.save()

    def get_cart_data(self):
        return self.cart_data_json

# class OrderHistory(models.Model):
#     order = models.ForeignKey(
#         Order,
#         on_delete=models.CASCADE,
#         verbose_name=_('Order'),
#         help_text=_('Related order')
#     )
#     updated_at = models.DateTimeField(
#         auto_now=True,
#         verbose_name=_('Updated At'),
#         help_text=_('Time of last status update')
#     )
#     previous_status = models.CharField(
#         max_length=50,
#         verbose_name=_('Previous Status'),
#         help_text=_('Previous order status')
#     )
#     new_status = models.CharField(
#         max_length=50,
#         verbose_name=_('New Status'),
#         help_text=_('New order status')
#     )

#     class Meta:
#         verbose_name = _('Order History')
#         verbose_name_plural = _('Order Histories')

#     def __str__(self):
#         return f'History for Order #{self.order.id}'


# class StoreLocation(models.Model):
#     name = models.CharField(
#         max_length=255,
#         verbose_name=_("Store Name"),
#         help_text=_("Name of the store")
#     )
#     latitude = models.FloatField(
#         verbose_name=_("Latitude"),
#         help_text=_("Latitude of the store location")
#     )
#     longitude = models.FloatField(
#         verbose_name=_("Longitude"),
#         help_text=_("Longitude of the store location")
#     )
#     group_id = models.IntegerField(
#         verbose_name=_("Group ID"),
#         help_text=_("Group ID of the store location")
#     )

#     class Meta:
#         verbose_name = _("Store Location")
#         verbose_name_plural = _("Store Locations")

#     def __str__(self):
#         return self.name


# class Review(models.Model):
#     client = models.ForeignKey(
#         Client,
#         on_delete=models.CASCADE,
#         verbose_name=_('Client'),
#         help_text=_('Client who left the review')
#     )
#     text = models.TextField(
#         verbose_name=_('Review Text'),
#         help_text=_('Text of the review')
#     )
#     created_at = models.DateTimeField(
#         auto_now_add=True,
#         verbose_name=_('Created At'),
#         help_text=_('Time when the review was created')
#     )

#     class Meta:
#         verbose_name = _('Review')
#         verbose_name_plural = _('Reviews')

#     def __str__(self):
#         return f"Review by {self.client.name or _('Unnamed Client')}"
