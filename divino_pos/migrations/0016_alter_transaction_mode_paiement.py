# Generated by Django 5.1.1 on 2024-10-16 21:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('divino_pos', '0015_transaction_mode_paiement'),
    ]

    operations = [
        migrations.AlterField(
            model_name='transaction',
            name='mode_paiement',
            field=models.CharField(choices=[('carte', 'Carte Bancaire'), ('especes', 'Espèces')], default='especes', max_length=20),
        ),
    ]