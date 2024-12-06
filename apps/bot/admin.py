from django.contrib import admin
from .models import Client, Category, Product,  Order, Cart


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('id', 'client', 'product', 'quantity', 'created_at')
    list_filter = ('client', 'created_at')
    search_fields = ('client__name', 'product__title')

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('id', 'telegram_id', 'name', 'phone_number', 'city', 'preferred_language')
    list_filter = ('city', 'preferred_language')
    search_fields = ('name', 'phone_number', 'telegram_id')
    readonly_fields = ('telegram_id', 'name', 'phone_number')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'title_ru', 'title_uz', 'title')
    search_fields = ('title_ru', 'title_uz', 'title')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'title_ru', 'title_uz', 'title', 'price', 'category')
    list_filter = ('category',)
    search_fields = ('title_ru', 'title_uz', 'title')




@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'client', 'total_price', 'status', 'created_at')
    list_filter = ('status',  'created_at')
    search_fields = ('client__name', 'delivery_address')
    autocomplete_fields = ('client',)


# @admin.register(OrderHistory)
# class OrderHistoryAdmin(admin.ModelAdmin):
#     list_display = ('id', 'order', 'previous_status', 'new_status', 'updated_at')
#     list_filter = ('updated_at', 'new_status')
#     search_fields = ('order__id',)


# @admin.register(StoreLocation)
# class StoreLocationAdmin(admin.ModelAdmin):
#     list_display = ('id', 'name', 'latitude', 'longitude', 'group_id')
#     search_fields = ('name',)


# @admin.register(Review)
# class ReviewAdmin(admin.ModelAdmin):
#     list_display = ('id', 'client', 'text', 'created_at')
#     list_filter = ('created_at',)
#     search_fields = ('client__name', 'text')
