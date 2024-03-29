from django.contrib import admin
from .models import Product, Variation,Category
# Register your models here.


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name','sku','stock_quantity','status','brand', 'category')
    

    def category(self, obj):
        cats = ', '.join([c.name for c in obj.categories.all()]).strip(", ")
        return cats
        

@admin.register(Variation)
class VariationAdmin(admin.ModelAdmin):
    list_display = ('name','sku','stock_quantity')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    pass


