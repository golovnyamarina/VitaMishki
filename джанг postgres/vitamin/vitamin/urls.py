from django.contrib import admin
from django.urls import path, include
from website.views import ProfileOrdersView, IndexView, OrderCreateView, CatalogView, ProductDetailView, AuthRequestView, AuthVerifyView, LogoutView, AddToCartView, RemoveFromCartView, CartDetailView, VitaminQuizView, OrderRepeatView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', IndexView.as_view(), name='index'),
    path('catalog/', CatalogView.as_view(), name='catalog'),
    path('catalog/<int:pk>/', ProductDetailView.as_view(), name='product_detail'),
    path('auth/', AuthRequestView.as_view(), name='auth_request'),
    path('auth/verify/', AuthVerifyView.as_view(), name='auth_verify'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),
    path('cart/', CartDetailView.as_view(), name='cart_detail'),
    path('cart/add/<int:product_id>/', AddToCartView.as_view(), name='cart_add'),
    path('cart/remove/<int:item_id>/', RemoveFromCartView.as_view(), name='cart_remove'),
    path('cart/', CartDetailView.as_view(), name='cart_detail'),
    path('cart/checkout/', OrderCreateView.as_view(), name='order_create'),
    path('profile/', ProfileOrdersView.as_view(), name='profile'),
    path('quiz/', VitaminQuizView.as_view(), name='quiz'),
    path('profile/order-repeat/<int:order_id>/', OrderRepeatView.as_view(), name='order_repeat'),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)