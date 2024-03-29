# Generated by Django 5.0.3 on 2024-03-29 05:44

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0002_product_image_variation_image'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='variations_ids',
            field=models.CharField(blank=True, max_length=150, null=True),
        ),
        migrations.AlterField(
            model_name='variation',
            name='product',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='variations', to='shop.product'),
        ),
    ]