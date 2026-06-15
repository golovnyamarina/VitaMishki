# website/forms.py
from django import forms
from django.core.exceptions import ValidationError
import re
from .models import Order

class AuthRequestForm(forms.Form):
    contact = forms.CharField(
        label="Email или Номер телефона", 
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg rounded-pill px-4',
            'placeholder': 'example@mail.ru или +79991112233'
        })
    )

    def clean_contact(self):
        """Метод clean_ИМЯПОЛЯ автоматически наполняет form.cleaned_data['contact']"""
        contact = self.cleaned_data['contact'].strip()
        
        # Проверяем на Email
        if '@' in contact:
            if not re.match(r"[^@]+@[^@]+\.[^@]+", contact):
                raise ValidationError("Введите корректный Email адрес.")
            return {'type': 'email', 'value': contact}
        
        # Проверяем на Телефон
        phone_digits = re.sub(r"\D", "", contact)
        if len(phone_digits) == 11 and (phone_digits.startswith('7') or phone_digits.startswith('8')):
            normalized_phone = f"+7{phone_digits[1:]}"
            return {'type': 'phone', 'value': normalized_phone}
        elif len(phone_digits) == 10:
            return {'type': 'phone', 'value': f"+7{phone_digits}"}
        
        raise ValidationError("Введите правильный Email или мобильный телефон.")


class VerifyCodeForm(forms.Form):
    """Форма второго шага: ввод 4-значного кода"""
    code = forms.CharField(
        label="Код из СМС или Email",
        max_length=4,
        min_length=4,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg text-center fw-bold letter-spacing-lg rounded-3',
            'placeholder': '0000',
            'autocomplete': 'off'
        })
    )

    def clean_code(self):
        code = self.cleaned_data['code']
        if not code.isdigit():
            raise ValidationError("Код должен состоять только из цифр.")
        return code

class OrderCreateForm(forms.ModelForm):
    """Форма для сбора данных доставки при оформлении заказа"""
    class Meta:
        model = Order
        fields = ['receiver_name', 'receiver_phone', 'delivery_address', 'comment']
        widgets = {
            'receiver_name': forms.TextInput(attrs={
                'class': 'form-control rounded-3', 'placeholder': 'Имя мамы или папы'
            }),
            'receiver_phone': forms.TextInput(attrs={
                'class': 'form-control rounded-3', 'placeholder': '+7 (999) 111-22-33'
            }),
            'delivery_address': forms.Textarea(attrs={
                'class': 'form-control rounded-3', 'rows': 3, 'placeholder': 'Город, улица, дом, квартира / ПВЗ СДЭК'
            }),
            'comment': forms.Textarea(attrs={
                'class': 'form-control rounded-3', 'rows': 2, 'placeholder': 'Например: не звонить в домофон, спит ребенок'
            }),
        }