# Generated by Django 5.1.1 on 2024-10-02 18:06

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Client',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('n_carte', models.CharField(max_length=20, unique=True)),
                ('nom', models.CharField(max_length=100)),
                ('prenom', models.CharField(max_length=100)),
                ('date_anniversaire', models.DateField(blank=True, null=True)),
                ('email', models.EmailField(max_length=255)),
                ('numero_rue', models.CharField(max_length=100)),
                ('code_postal', models.CharField(max_length=10)),
                ('ville', models.CharField(max_length=100)),
                ('pays', models.CharField(max_length=100)),
                ('telephone', models.CharField(max_length=20)),
            ],
        ),
        migrations.CreateModel(
            name='Product',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code_ean', models.CharField(max_length=13, unique=True)),
                ('code_article', models.CharField(max_length=100, unique=True)),
                ('nom_article', models.CharField(max_length=255)),
                ('prix_achat', models.DecimalField(decimal_places=2, max_digits=10)),
                ('prix_vente', models.DecimalField(decimal_places=2, max_digits=10)),
                ('categorie', models.CharField(max_length=100)),
                ('couleurs', models.CharField(max_length=100)),
                ('tailles', models.CharField(max_length=50)),
                ('quantite', models.PositiveIntegerField(default=0)),
            ],
        ),
    ]