"""
URL configuration for main project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from products.urls import product_urlpatterns, cart_urlpatterns, order_urlpatterns


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/accounts/', include('authentication.urls')),
    path("ckeditor5/", include("django_ckeditor_5.urls")),

    path("api/v1/products/", include((product_urlpatterns, "products"))),
    path("api/v1/cart/",     include((cart_urlpatterns, "cart"))),
    path("api/v1/orders/",   include((order_urlpatterns, "orders"))),

]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
