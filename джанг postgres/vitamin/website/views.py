import re
from django.views.generic import ListView, DetailView
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.contrib.auth import login, logout
from django.contrib import messages
from .models import Order, OrderItem, Product, ProductVariant, Category, User, Cart, CartItem
import random
from django.db import transaction
from .forms import OrderCreateForm, AuthRequestForm, VerifyCodeForm

class IndexView(ListView):
    """Контроллер главной страницы с оптимизацией запросов к БД"""
    model = Product
    template_name = 'index.html'
    context_object_name = 'top_products'

    def get_queryset(self):
        """Избегаем N+1: подтягиваем связанные категории и варианты товаров за 2 запроса"""
        return Product.objects.select_related('category').prefetch_related('variants').order_by('-created_at')[:3]

class CatalogView(ListView):
    """Страница каталога с динамической фильтрацией и защитой от N+1"""
    model = Product
    template_name = 'catalog.html'
    context_object_name = 'products'
    
    def get_queryset(self):
        """Получаем товары, фильтруем их и оптимизируем запросы к БД"""
        # Базовый запрос с оптимизацией
        queryset = Product.objects.select_related('category').prefetch_related('variants').order_by('-created_at')
        
        # Получаем параметры фильтрации из GET-запроса URL
        form_filter = self.request.GET.get('form')
        flavor_filter = self.request.GET.get('flavor')
        age_filter = self.request.GET.get('age')
        
        # Фильтруем по форме выпуска (связано через варианты)
        if form_filter:
            queryset = queryset.filter(variants__form=form_filter).distinct()
            
        # Фильтруем по вкусу (связано через варианты)
        if flavor_filter:
            queryset = queryset.filter(variants__flavor=flavor_filter).distinct()
            
        # Фильтруем по возрастной группе (поле в самом продукте)
        if age_filter:
            queryset = queryset.filter(age_category=age_filter)
            
        return queryset

    def get_context_data(self, **kwargs):
        """Передаем списки фильтров в шаблон, чтобы выпадающие списки заполнялись сами"""
        context = super().get_context_data(**kwargs)
        
        # Получаем все уникальные вкусы, которые реально есть на складе
        context['available_flavors'] = ProductVariant.objects.values_list('flavor', flat=True).exclude(flavor__isnull=True).distinct()
        
        # Список форм берем из статичного choices нашей модели
        context['available_forms'] = ProductVariant.FORMS
        
        # Список возрастов берем из choices модели Product
        context['available_ages'] = Product.AGE_CHOICES
        
        # Сохраняем текущие выбранные фильтры, чтобы форма не сбрасывалась при перезагрузке
        context['current_form'] = self.request.GET.get('form', '')
        context['current_flavor'] = self.request.GET.get('flavor', '')
        context['current_age'] = self.request.GET.get('age', '')
        
        return context

class ProductDetailView(DetailView):
    """Детальная страница витамина с подгрузкой всех его вкусов и форм"""
    model = Product
    template_name = 'product_detail.html'
    context_object_name = 'product'

    def get_queryset(self):
        """Оптимизация: подтягиваем категории и все варианты в один заход"""
        return Product.objects.select_related('category').prefetch_related('variants')
    

def fake_send_code(contact_info, code):
    """Имитация отправки кода. В продакшене тут будет вызов API СМС-шлюза или send_mail()"""
    print("\n" + "="*50)
    print(f" СЛУЖЕБНОЕ СООБЩЕНИЕ ДЛЯ МАГАЗИНА ВИТАМИШЕК")
    print(f"Отправка кода {code} на адрес/телефон: {contact_info['value']}")
    print("="*50 + "\n")

class AuthRequestView(View):
    """Шаг 1: Запрос контакта и генерация кода"""
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('index')
        form = AuthRequestForm()
        return render(request, 'auth_request.html', {'form': form})

    def post(self, request):
        form = AuthRequestForm(request.POST)
        if form.is_valid():
            contact_info = form.cleaned_data['contact']
            
            # Генерируем случайный 4-значный проверочный код
            code = str(random.randint(1000, 9999))
            
            # Сохраняем данные во временную сессию Django (хранится в БД SQLite)
            request.session['auth_contact_type'] = contact_info['type']
            request.session['auth_contact_value'] = contact_info['value']
            request.session['auth_verify_code'] = code
            
            # Отправляем код (в консоль)
            fake_send_code(contact_info, code)
            
            messages.success(request, f"Код успешно отправлен на {contact_info['value']}")
            return redirect('auth_verify')
        
        return render(request, 'auth_request.html', {'form': form})


class AuthVerifyView(View):
    """Шаг 2: Проверка кода и создание/авторизация пользователя"""
    def get(self, request):
        if 'auth_verify_code' not in request.session:
            return redirect('auth_request')
        form = VerifyCodeForm()
        return render(request, 'auth_verify.html', {'form': form})

    def post(self, request):
        form = VerifyCodeForm(request.POST)
        if form.is_valid():
            input_code = form.cleaned_data['code']
            session_code = request.session.get('auth_verify_code')
            
            if input_code == session_code:
                contact_type = request.session.get('auth_contact_type')
                contact_value = request.session.get('auth_contact_value')
                
                # Ищем пользователя или регистрируем нового (Up-to-Date e-commerce подход)
                if contact_type == 'email':
                    user, created = User.objects.get_or_create(
                        email=contact_value,
                        defaults={'username': contact_value.split('@')[0]}
                    )
                else:  # phone
                    # Если вошел по телефону, генерируем фейковый email для системных нужд Django
                    clean_phone = re.sub(r"\D", "", contact_value)
                    user, created = User.objects.get_or_create(
                        phone=contact_value,
                        defaults={
                            'username': f"user_{clean_phone}",
                            'email': f"{clean_phone}@vitamishki.local",
                            'is_phone_verified': True
                        }
                    )
                
                # Авторизуем пользователя в системе
                login(request, user)
                
                # Очищаем данные авторизации из сессии
                del request.session['auth_verify_code']
                
                if created:
                    messages.success(request, "Добро пожаловать! Вы успешно зарегистрировались.")
                else:
                    messages.success(request, "С возвращением! Успешный вход.")
                    
                return redirect('index')
            else:
                form.add_error('code', 'Неверный код подтверждения. Попробуйте еще раз.')
                
        return render(request, 'auth_verify.html', {'form': form})

class LogoutView(View):
    """Выход из профиля"""
    def get(self, request):
        logout(request)
        return redirect('index')
    
class CartDetailView(LoginRequiredMixin, ListView):
    """Страница корзины с оптимизированной подгрузкой товаров"""
    model = CartItem
    template_name = 'cart.html'
    context_object_name = 'cart_items'
    login_url = 'auth_request'  # Перенаправим на вход, если не авторизован

    def get_queryset(self):
        """Избегаем N+1: подтягиваем варианты товаров и сами товары через '__'"""
        # Сначала получаем или создаем корзину для текущего пользователя
        self.cart, _ = Cart.objects.get_or_create(user=self.request.user)
        return self.cart.items.select_related('variant__product')

    def get_context_data(self, **kwargs):
        """Передаем саму корзину, чтобы в шаблоне была доступна общая стоимость"""
        context = super().get_context_data(**kwargs)
        context['cart'] = self.cart
        return context


class AddToCartView(LoginRequiredMixin, View):
    """Контроллер добавления витаминов в корзину"""
    login_url = 'auth_request'

    def post(self, request, product_id): # Принимаем id продукта из URL
        # Получаем id конкретного вкуса/варианта из отправленной формы
        variant_id = request.POST.get('variant_id')
        try:
            quantity = int(request.POST.get('quantity', 1))
        except (ValueError, TypeError):
            messages.error(request, "Некорректное количество товара.")
            return redirect('product_detail', pk=product_id)


        if not variant_id or quantity < 1:
            return redirect('cart_detail')

        # Ищем вариант товара
        variant = get_object_or_404(ProductVariant, id=variant_id)
        
        # Получаем или создаем корзину
        cart, _ = Cart.objects.get_or_create(user=request.user)

        existing_item = CartItem.objects.filter(cart=cart, variant=variant).first()
        already_in_cart = existing_item.quantity if existing_item else 0
        
        # Общее запрашиваемое количество
        total_requested = already_in_cart + quantity

        # Главная проверка: превышает ли сумма остаток на складе?
        if total_requested > variant.stock:
            available_to_add = variant.stock - already_in_cart
            
            if available_to_add > 0:
                messages.error(
                    request, 
                    f"Нельзя добавить {quantity} шт. На складе всего {variant.stock} шт. "
                    f"(В вашей корзине уже есть {already_in_cart} шт., вы можете добавить еще максимум {available_to_add} шт.)."
                )
            else:
                messages.error(
                    request, 
                    f"Вы не можете добавить этот товар. Все доступные единицы ({variant.stock} шт.) "
                    f"уже находятся в вашей корзине."
                )
            return redirect('product_detail', pk=product_id)

        # Если проверка пройдена — сохраняем/обновляем в БД
        if existing_item:
            existing_item.quantity = total_requested
            existing_item.save()
        else:
            CartItem.objects.create(cart=cart, variant=variant, quantity=quantity)

        messages.success(request, f"«{variant.product.title}» ({variant.get_form_display()}) добавлен в корзину.")
        return redirect('cart_detail')

class RemoveFromCartView(LoginRequiredMixin, View):
    """Контроллер удаления позиции из корзины"""
    def post(self, request, item_id):
        # Удаляем элемент, только если он принадлежит корзине текущего пользователя
        cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
        cart_item.delete()
        messages.success(request, "Товар удален из корзины.")
        return redirect('cart_detail')
    
class OrderCreateView(LoginRequiredMixin, View):
    """Контроллер создания заказа из корзины пользователя"""
    login_url = 'auth_request'

    def get(self, request):
        cart = getattr(request.user, 'cart', None)
        # Если корзина пуста или её нет — оформлять нечего
        if not cart or not cart.items.exists():
            messages.warning(request, "Ваша корзина пуста.")
            return redirect('cart_detail')
            
        form = OrderCreateForm()
        return render(request, 'order_create.html', {'cart': cart, 'form': form})

    def post(self, request):
        cart = request.user.cart
        form = OrderCreateForm(request.POST)

        if form.is_valid():
            # Обертываем операцию в транзакцию: если на каком-то этапе произойдет сбой,
            with transaction.atomic():
                # 1. Создаем объект заказа, но пока не сохраняем его финально
                order = form.save(commit=False)
                order.user = request.user
                order.total_cost = cart.total_price
                order.save() # Сохраняем, чтобы получить ID заказа

                # 2. Переносим позиции из корзины в заказ
                for item in cart.items.select_related('variant'):
                    variant = item.variant
                    
                    # Проверяем физическое наличие витаминов на складе
                    if variant.stock < item.quantity:
                        messages.error(request, f"К сожалению, витамин «{variant}» закончился или его недостаточно на складе.")
                        # Вызываем принудительный откат транзакции
                        raise transaction.TransactionManagementError

                    # Фиксируем историческую цену и уменьшаем складские остатки
                    OrderItem.objects.create(
                        order=order,
                        variant=variant,
                        price=variant.price,
                        quantity=item.quantity
                    )
                    
                    variant.stock -= item.quantity
                    variant.save()

                # 3. Полностью очищаем корзину покупателя
                cart.items.all().delete()

            messages.success(request, f"Заказ №{order.id} успешно оформлен! Наш менеджер уже собирает его.")
            return redirect('index')

        return render(request, 'order_create.html', {'cart': cart, 'form': form})
    
class ProfileOrdersView(LoginRequiredMixin, ListView):
    """Личный кабинет пользователя со списком его заказов"""
    model = Order
    template_name = 'profile.html'
    context_object_name = 'orders'
    login_url = 'auth_request'

    def get_queryset(self):
       
        return (Order.objects
                .filter(user=self.request.user)
                .prefetch_related('items__variant__product')
                .order_by('-created_at'))
    
class VitaminQuizView(View):
    """Контроллер интерактивного теста по подбору витаминов"""
    
    def get(self, request):
        # При каждом заходе на страницу с нуля сбрасываем прошлые ответы в сессии
        request.session['quiz_step'] = 1
        request.session['quiz_data'] = {}
        return render(request, 'quiz.html', {'step': 1})

    def post(self, request):
        current_step = request.session.get('quiz_step', 1)
        quiz_data = request.session.get('quiz_data', {})

        if current_step == 1:
            # Шаг 1: Возраст ребенка
            quiz_data['age'] = request.POST.get('age')
            request.session['quiz_step'] = 2
            request.session['quiz_data'] = quiz_data
            return render(request, 'quiz.html', {'step': 2})

        elif current_step == 2:
            # Шаг 2: Главная цель / проблема
            quiz_data['goal'] = request.POST.get('goal')
            request.session['quiz_step'] = 3
            request.session['quiz_data'] = quiz_data
            return render(request, 'quiz.html', {'step': 3})

        elif current_step == 3:
            # Шаг 3: Форма выпуска, которую предпочитает ребенок
            quiz_data['form'] = request.POST.get('form')
            
            age_group = quiz_data.get('age')
            goal = quiz_data.get('goal')     
            preferred_form = quiz_data.get('form')

            # Делаем выборку базовых продуктов по возрасту
            recommended_products = Product.objects.filter(
                age_category=age_group
            ).select_related('category').prefetch_related('variants')

            # Умная фильтрация по целям
            if goal == 'immunity':
                recommended_products = recommended_products.filter(title__icontains='иммун')
            elif goal == 'energy':
                recommended_products = recommended_products.filter(description__icontains='памят')
            elif goal == 'growth':
                recommended_products = recommended_products.filter(description__icontains='рост')

            # Фильтруем по предпочитаемой форме выпуска через связанные варианты
            if preferred_form:
                recommended_products = recommended_products.filter(variants__form=preferred_form).distinct()

            if not recommended_products.exists():
                recommended_products = Product.objects.filter(age_category=age_group)[:2]

            # Очищаем сессию теста после завершения
            del request.session['quiz_step']
            del request.session['quiz_data']

            return render(request, 'quiz_result.html', {
                'products': recommended_products,
                'quiz_summary': quiz_data
            })

class OrderRepeatView(LoginRequiredMixin, View):
    """Контроллер для быстрого копирования товаров из старого заказа в корзину"""
    login_url = 'auth_request'

    def post(self, request, order_id):
        # Ищем прошлый заказ строго текущего пользователя
        old_order = get_object_or_404(Order, id=order_id, user=request.user)
        
        # Получаем или создаем корзину покупателя
        cart, _ = Cart.objects.get_or_create(user=request.user)
        
        items_added_count = 0
        items_out_of_stock = []

        # Пробегаемся по всем позициям старого заказа
        for order_item in old_order.items.select_related('variant__product'):
            variant = order_item.variant
            
            # Проверяем, есть ли вообще этот вкус/форма сейчас на складе
            if variant.stock <= 0:
                items_out_of_stock.append(f"{variant.product.title} ({variant.get_form_display()})")
                continue
                
            # Считаем, сколько нужно добавить (не больше, чем есть на складе)
            quantity_to_add = min(order_item.quantity, variant.stock)
            
            # Ищем, не лежит ли уже этот товар в корзине
            cart_item, created = CartItem.objects.get_or_create(
                cart=cart,
                variant=variant,
                defaults={'quantity': quantity_to_add}
            )
            
            # If товар уже был в корзине, обновляем количество, но не превышая складской остаток
            if not created:
                new_quantity = min(cart_item.quantity + quantity_to_add, variant.stock)
                cart_item.quantity = new_quantity
                cart_item.save()
                
            items_added_count += 1

        # Формируем понятные уведомления для мамы
        if items_added_count > 0:
            messages.success(request, f"Товары из заказа №{old_order.id} успешно добавлены в вашу корзину! 🛒")
        
        if items_out_of_stock:
            names = ", ".join(items_out_of_stock)
            messages.warning(request, f"Некоторые позиции сейчас отсутствуют на складе и не были добавлены: {names}.")

        return redirect('cart_detail')