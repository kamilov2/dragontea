from django.contrib import admin
from .models import Client, Category, Product, Cart, Order
from django.utils.html import format_html


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'telegram_id', 'telegram_username', 'phone_number', 'city', 'preferred_language')
    search_fields = ('name', 'telegram_id', 'telegram_username', 'phone_number')
    list_filter = ('preferred_language', 'city')
    ordering = ('name',)
    readonly_fields = ('telegram_id', 'telegram_username')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('title_ru', 'title_uz', 'title')
    search_fields = ('title_ru', 'title_uz', 'title')
    ordering = ('title_ru',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'title_ru', 'title_uz', 'category',
        'small_price', 'big_price',
        'is_small', 'is_big', 'is_hot', 'is_cold'
    )
    search_fields = ('title_ru', 'title_uz')
    list_filter = ('category', 'is_small', 'is_big', 'is_hot', 'is_cold')
    ordering = ('title_ru',)
    # Если хотите отображать картинку в админке (миниатюру):
    # def product_image(self, obj):
    #     if obj.image:
    #         return format_html('<img src="{}" style="height:50px; width:auto;">', obj.image.url)
    #     return "-"
    # product_image.short_description = "Изображение"


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = (
        'client', 'product', 'quantity',
        'is_small', 'is_big', 'is_hot', 'is_cold', 'created_at'
    )
    search_fields = ('client__name', 'product__title_ru', 'product__title_uz')
    list_filter = ('is_small', 'is_big', 'is_hot', 'is_cold', 'created_at')
    ordering = ('-created_at',)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'client', 'total_price', 'status',
        'delivery_address', 'courier_name', 'car_number', 'car_model', 'created_at'
    )
    search_fields = (
        'client__name', 'client__phone_number',
        'courier_name', 'car_number', 'car_model'
    )
    list_filter = ('status', 'created_at')
    ordering = ('-created_at',)
    readonly_fields = ('cart_data_json', 'created_at')

    # Дополнительно можно отформатировать cart_data_json для удобства чтения
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == 'cart_data_json':
            field.widget.attrs['style'] = 'height: 200px;'
        return field
