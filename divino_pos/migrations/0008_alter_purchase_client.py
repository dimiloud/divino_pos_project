# Generated by Django 5.1.1 on 2024-10-15 16:16

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('divino_pos', '0007_alter_client_email'),
    ]

    operations = [
        migrations.AlterField(
            model_name='purchase',
            name='client',
            field=models.ForeignKey(blank=True, help_text="Client ayant effectué l'achat.", null=True, on_delete=django.db.models.deletion.CASCADE, related_name='purchases', to='divino_pos.client'),
        ),
    ]