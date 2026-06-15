# website/tests/test_cart.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import Category, Product, ProductVariant
from .models import Cart, CartItem
from django.urls import reverse

User = get_user_model()

class CartBusinessLogicTestCase(TestCase):
    """Тестирование расчетов стоимости в корзине детских витаминов"""

    def setUp(self):
        """Создаем пользователя, товар и два разных вкуса с разной ценой"""
        self.user = User.objects.create_user(username="testmother", email="mom@mail.ru", password="testpassword123")
        self.category = Category.objects.create(name="Омега", slug="omega")
        self.product = Product.objects.create(category=self.category, title="Детская Омега-3", age_category="7+")
        self.variant_tutti = ProductVariant.objects.create(product=self.product, form="capsules", flavor="Тутти-Фрутти",
            price=1000.00, stock=5, sku="OM-TUT-7")
        self.variant_orange = ProductVariant.objects.create(product=self.product, form="capsules", flavor="Апельсин",
            price=1200.00, stock=5, sku="OM-ORG-7")
        self.cart = Cart.objects.create(user=self.user)

    def test_cart_item_total_price_calculation(self):
        """Проверяем математику одной строки корзины: цена * количество"""
        cart_item = CartItem.objects.create( cart=self.cart,  variant=self.variant_tutti, quantity=3)
        self.assertEqual(cart_item.total_price, 3000.00)

    def test_cart_global_total_price(self):
        """Проверяем общую сумму всей корзины при добавлении разных вкусов"""
        CartItem.objects.create(cart=self.cart, variant=self.variant_tutti, quantity=2)
        CartItem.objects.create(cart=self.cart, variant=self.variant_orange, quantity=1)
        # Общая стоимость корзины: 2000 + 1200 = 3200
        self.assertEqual(self.cart.total_price, 3200.00)

class PasswordlessAuthTestCase(TestCase):
    """Тестирование системы беспарольной регистрации и авторизации по Email"""

    def test_registration_and_login_flow(self):
        test_email = "testmother@mail.ru"
        response_step1 = self.client.post(reverse('auth_request'), {'contact': test_email})
        self.assertEqual(response_step1.status_code, 302)
        self.assertRedirects(response_step1, reverse('auth_verify'))
        self.assertIn('auth_verify_code', self.client.session)
        session_code = self.client.session['auth_verify_code']
        response_step2 = self.client.post(reverse('auth_verify'), {'code': session_code})
        self.assertEqual(response_step2.status_code, 302)
        self.assertRedirects(response_step2, reverse('index'))
        self.assertTrue(User.objects.filter(email=test_email).exists())
        user = User.objects.get(email=test_email)
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)

class CartRemoveTestCase(TestCase):
    """Короткий тест удаления позиции из корзины покупателя"""

    def test_remove_item_from_cart_successfully(self):
        user = User.objects.create_user(username="mom", email="mom@mail.ru")
        self.client.force_login(user)
        category = Category.objects.create(name="Витамины", slug="vits")
        product = Product.objects.create(category=category, title="Мульти-Мишки", age_category="3-7")
        variant = ProductVariant.objects.create(product=product, form="gummies", price=500.00, stock=5, sku="TST-DEL")
        cart = Cart.objects.create(user=user)
        cart_item = CartItem.objects.create(cart=cart, variant=variant, quantity=2)
        self.assertEqual(cart.items.count(), 1)
        response = self.client.post(reverse('cart_remove', kwargs={'item_id': cart_item.id}))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('cart_detail'))
        self.assertEqual(cart.items.count(), 0)