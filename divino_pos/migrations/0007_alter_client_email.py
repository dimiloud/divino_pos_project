# Generated by Django 5.1.1 on 2024-10-15 08:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('divino_pos', '0006_alter_client_options_alter_product_options_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='client',
            name='email',
            field=models.EmailField(blank=True, help_text='Adresse email unique du client.', max_length=255, null=True, unique=True),
        ),
    ]