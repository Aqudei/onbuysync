from django.db import models
from django.urls import reverse
from django.utils.translation import gettext as _

# Create your models here.


class Category(models.Model):
    name = models.CharField(max_length=50)
    
    class Meta:
        verbose_name = _("category")
        verbose_name_plural = _("categorys")

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("category_detail", kwargs={"pk": self.pk})


class Product(models.Model):

    external_id = models.PositiveBigIntegerField(default=0)
    name = models.CharField(max_length=200)
    status = models.CharField(max_length=50)
    sku = models.CharField(max_length=50)
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0.0)
    regular_price = models.DecimalField(max_digits=8, decimal_places=2, default=0.0)
    sale_price = models.DecimalField(max_digits=8, decimal_places=2, default=0.0)
    stock_quantity = models.PositiveIntegerField(default=0)
    brand = models.CharField(max_length=50, null=True,blank=True)
    categories = models.ManyToManyField("shop.Category")
    image = models.URLField(max_length=400, null=True,blank=True)
    variations_ids = models.CharField(max_length=150,null=True,blank=True)
    
    class Meta:
        verbose_name = _("product")
        verbose_name_plural = _("products")

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("product_detail", kwargs={"pk": self.pk})

class Variation(models.Model):

    product = models.ForeignKey("shop.Product", on_delete=models.CASCADE,related_name='variations')
    name = models.CharField(max_length=300)
    external_id = models.PositiveBigIntegerField(default=0)
    sku = models.CharField(max_length=50)
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0.0)
    regular_price = models.DecimalField(max_digits=8, decimal_places=2, default=0.0)
    sale_price = models.DecimalField(max_digits=8, decimal_places=2, default=0.0)
    stock_quantity = models.PositiveIntegerField(default=0)
    image = models.URLField(max_length=400, null=True,blank=True)
    
    class Meta:
        verbose_name = _("variation")
        verbose_name_plural = _("variations")

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("variation_detail", kwargs={"pk": self.pk})
