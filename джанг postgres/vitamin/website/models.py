from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser

class Category(models.Model):
    name = models.CharField("Название", max_length=100)
    slug = models.SlugField(unique=True)

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"

    def __str__(self):
        return self.name

class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    title = models.CharField("Название", max_length=255)
    description = models.TextField("Описание")
    composition = models.TextField("Состав")
    usage_instructions = models.TextField("Дозировки и применение")
    
    AGE_CHOICES = [
        ('0-3', '0-3 года'),
        ('3-7', '3-7 лет'),
        ('7+', '7 лет и старше'),
    ]
    age_category = models.CharField("Возрастная группа", max_length=10, choices=AGE_CHOICES)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Товар (базовая модель)"
        verbose_name_plural = "Товары"

    def __str__(self):
        return self.title

class ProductVariant(models.Model):
    """Конкретная вариация: форма выпуска + вкус"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    
    FORMS = [
        ('gummies', 'Мишки'),
        ('syrup', 'Сироп'),
        ('capsules', 'Капсулы'),
        ('drops', 'Капли'),
    ]
    form = models.CharField("Форма выпуска", max_length=20, choices=FORMS)
    flavor = models.CharField("Вкус", max_length=50, blank=True, null=True)
    
    price = models.DecimalField("Цена", max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField("Остаток на складе", default=0)
    sku = models.CharField("Артикул", max_length=50, unique=True)
    image = models.ImageField("Изображение варианта", upload_to='products/', blank=True, null=True)
    
    class Meta:
        verbose_name = "Вариант товара"
        verbose_name_plural = "Варианты товаров"

    def __str__(self):
        return f"{self.product.title} ({self.get_form_display()} - {self.flavor})"


class User(AbstractUser):
    # Убираем username, если логинимся по email/phone (нужна доп. настройка backend)
    email = models.EmailField("Email", unique=True)
    phone = models.CharField("Телефон", max_length=20, blank=True, null=True)
    
    # Для кастомной авторизации (СМС)
    is_phone_verified = models.BooleanField(default=False)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

class Cart(models.Model):
    """Корзина, привязанная к пользователю"""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='cart',
        verbose_name="Владелец корзины"
    )
    created_at = models.DateTimeField("Создана", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлена", auto_now=True)

    class Meta:
        verbose_name = "Корзина"
        verbose_name_plural = "Корзины"

    def __str__(self):
        return f"Корзина {self.user.email}"

    @property
    def total_price(self):
        """Оптимизированный подсчет общей стоимости корзины"""
        return sum(item.total_price for item in self.items.all())


class CartItem(models.Model):
    """Элемент корзины: конкретный вкус/форма и количество"""
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items', verbose_name="Корзина")
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, verbose_name="Вариант витамина")
    quantity = models.PositiveIntegerField("Количество", default=1)

    class Meta:
        verbose_name = "Предмет корзины"
        verbose_name_plural = "Предметы корзины"
        # Не позволяем дублировать один и тот же SKU в одной корзине
        unique_together = ('cart', 'variant') 

    def __str__(self):
        return f"{self.variant} x {self.quantity}"

    @property
    def total_price(self):
        # Защита от пустых значений при рендеринге форм
        if not self.variant or self.variant.price is None:
            return 0
        return self.variant.price * self.quantity


class Order(models.Model):
    """Модель оформленного заказа"""
    STATUS_CHOICES = [
        ('new', 'Новый'),
        ('paid', 'Оплачен'),
        ('assembling', 'Сборка заказа (проверка срока годности)'),
        ('sent', 'Передан в доставку'),
        ('completed', 'Доставлен'),
        ('canceled', 'Отменен'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.PROTECT, 
        related_name='orders',
        verbose_name="Покупатель"
    )
    status = models.CharField("Статус", max_length=20, choices=STATUS_CHOICES, default='new')
    
    # Данные для доставки детских товаров (часто заказывают мамы, нужен точный адрес)
    delivery_address = models.TextField("Адрес доставки")
    receiver_name = models.CharField("Имя получателя", max_length=255)
    receiver_phone = models.CharField("Телефон получателя", max_length=20)
    
    # Комментарий (например: «оставить у двери, спит ребенок»)
    comment = models.TextField("Комментарий к заказу", blank=True, null=True)
    
    total_cost = models.DecimalField("Итоговая стоимость", max_digits=10, decimal_places=2, default=0.00)
    
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)
    updated_at = models.DateTimeField("Дата изменения", auto_now=True)

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        ordering = ['-created_at']

    def __str__(self):
        return f"Заказ №{self.id} от {self.created_at.strftime('%d.%m.%Y')}"


class OrderItem(models.Model):
    """Фиксация купленного товара, его цены и количества на момент заказа"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items', verbose_name="Заказ")
    variant = models.ForeignKey(ProductVariant, on_delete=models.PROTECT, verbose_name="Вариант витамина")
    
    # Фиксируем цену на момент покупки (защита от изменения цен в каталоге)
    price = models.DecimalField("Цена при покупке", max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField("Количество", default=1)

    class Meta:
        verbose_name = "Товар в заказе"
        verbose_name_plural = "Товары в заказе"

    def __str__(self):
        return f"{self.variant} в Заказе №{self.order.id}"

    @property
    def total_price(self):
        # Если цена еще не задана (например, в пустой строке админки), возвращаем 0
        if self.price is None:
            return 0
        return self.price * self.quantity