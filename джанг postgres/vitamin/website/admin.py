from django.contrib import admin
from .models import Category, Product, ProductVariant, Cart, CartItem, Order, OrderItem


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    # Автоматическая генерация slug при вводе названия на латинице
    prepopulated_fields = {'slug': ('name',)}


class ProductVariantInline(admin.TabularInline):
    """Позволяет добавлять вкусы и формы выпуска прямо внутри карточки товара"""
    model = ProductVariant
    extra = 1  # Количество пустых строк для новых вариаций по умолчанию
    fields = ('form', 'flavor', 'price', 'stock', 'sku', 'image')
    min_num = 1  # У витамина должен быть как минимум один вариант


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'age_category', 'created_at')
    list_filter = ('category', 'age_category')
    search_fields = ('title', 'composition')
    
    # Группируем поля в удобные блоки (Fieldsets)
    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'category', 'age_category')
        }),
        ('Описание и характеристики', {
            'fields': ('description', 'composition', 'usage_instructions')
        }),
    )
    
    # Включаем управление вариациями на этой же странице
    inlines = [ProductVariantInline]


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1  # Даем одну пустую строку для добавления
    fields = ('variant', 'price', 'quantity', 'total_price')
    
    def get_readonly_fields(self, request, obj=None):
        """Динамически управляет доступностью полей"""
        if obj is None:
            # Если obj равен None, значит это создание нового заказа.
            # Оставляем доступным только подсчет суммы (total_price), остальные поля можно заполнять!
            return ('total_price',)
        
        # Если obj существует, значит заказ уже сохранен в БД.
        # Блокируем все поля для редактирования, чтобы защитить историю.
        return ('variant', 'price', 'quantity', 'total_price')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'status', 'total_cost', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('id', 'receiver_name', 'receiver_phone', 'user__email')
    
    # Менеджер может быстро менять статус заказа прямо из списка
    list_editable = ('status',)
    
    def get_readonly_fields(self, request, obj=None):
        """Динамически блокирует поля в зависимости от того, создается заказ или редактируется"""
        if obj is None:
            # При создании нового заказа вручную:
            # Итоговую стоимость и даты менять нельзя (их посчитает система),
            # но поле 'user' (Покупатель) должно быть открыто для выбора!
            return ('total_cost', 'created_at', 'updated_at')
        
        # При просмотре существующего заказа:
        # Полностью блокируем покупателя, стоимость и даты от случайных изменений
        return ('user', 'total_cost', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Статус заказа', {
            'fields': ('status', 'total_cost')
        }),
        ('Данные покупателя', {
            'fields': ('user', 'receiver_name', 'receiver_phone')
        }),
        ('Доставка', {
            'fields': ('delivery_address', 'comment')
        }),
        ('Служебная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',), # Сворачиваемый блок
        }),
    )
    
    inlines = [OrderItemInline]

# Админка для контроля брошенных корзин
class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    readonly_fields = ('variant', 'quantity')

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at', 'updated_at')
    inlines = [CartItemInline]