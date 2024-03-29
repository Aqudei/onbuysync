from django.contrib import admin
from .models import Product, Variation,Category
# Register your models here.


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    pass

@admin.register(Variation)
class VariationAdmin(admin.ModelAdmin):
    pass

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    pass


