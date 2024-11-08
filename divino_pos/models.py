from decimal import Decimal
from django.db.models import Sum
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, IntegrityError
from django.db.models.signals import pre_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
import uuid
import random

class Product(models.Model):
    code_ean = models.CharField(max_length=13, unique=True, blank=True, null=True)
    code_article = models.CharField(max_length=100, unique=False, null=True, blank=True)
    nom_article = models.CharField(max_length=255)
    prix_vente = models.DecimalField(max_digits=10, decimal_places=2)
    prix_achat = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    categorie = models.CharField(max_length=100, blank=True, null=True)
    couleurs = models.CharField(max_length=100, blank=True, null=True)
    tailles = models.CharField(max_length=100, blank=True, null=True)
    quantite = models.IntegerField(default=0)
    

    def __str__(self):
        return self.nom_article

    def adjust_stock(self, quantity):
        """
        Ajuste le stock du produit en fonction de la quantité donnée.
        La quantité peut être positive (ajout de stock) ou négative (retrait de stock).

        :param quantity: int
        """
        if self.quantite + quantity < 0:
            raise ValidationError('Stock insuffisant pour le produit.')
        self.quantite += quantity
        self.save()
    
    def save(self, *args, **kwargs):
        if not self.code_article:
            self.code_article = str(uuid.uuid4())
        if not self.code_ean:
            self.code_ean = self.generate_unique_ean()
        super(Product, self).save(*args, **kwargs)

    def generate_unique_ean(self):
        for _ in range(100):  # Limite le nombre de tentatives à 100
            ean = ''.join([str(random.randint(0, 9)) for _ in range(12)])
            ean_with_checksum = self.calculate_ean13_checksum(ean)
            if not Product.objects.filter(code_ean=ean_with_checksum).exists():
                return ean_with_checksum
        raise IntegrityError('Impossible de générer un code EAN unique.')
    
    def calculate_ean13_checksum(self, ean):
        total = 0
        for i, digit in enumerate(ean):
            n = int(digit)
            if i % 2 == 0:
                total += n
            else:
                total += n * 3
        checksum = (10 - (total % 10)) % 10
        return ean + str(checksum)
    
    class Meta:
        verbose_name = "Produit"
        verbose_name_plural = "Produits"

class Client(models.Model):
    n_carte = models.CharField(
        max_length=100,
        unique=True,
        blank=True,
        null=True,
        help_text="Numéro de carte unique pour chaque client."
    )
    nom = models.CharField(max_length=100, help_text="Nom de famille du client.")
    prenom = models.CharField(max_length=100, help_text="Prénom du client.")
    date_anniversaire = models.DateField(
        null=True, blank=True, help_text="Date d'anniversaire du client."
    )
    email = models.EmailField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Adresse email du client."
    )
    numero_rue = models.CharField(max_length=100, help_text="Numéro et nom de rue du client.", null=True, blank=True)
    code_postal = models.CharField(max_length=10, help_text="Code postal du client.", null=True, blank=True)
    ville = models.CharField(max_length=100, help_text="Ville du client.", null=True, blank=True)
    pays = models.CharField(max_length=100, help_text="Pays du client.", null=True, blank=True)
    telephone = models.CharField(max_length=20, help_text="Numéro de téléphone du client.", null=True, blank=True)
    credit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Crédit disponible pour le client après retour d'articles."
    )
    fidelity_points = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Points de fidélité accumulés par le client."
    )
    n_carte = models.CharField(max_length=50, blank=True, null=True, unique=True)  # Ajouté

    def __str__(self):
        return f"{self.prenom} {self.nom}"

    def save(self, *args, **kwargs):
        if not self.n_carte:
            # Générer un identifiant unique avec un préfixe 'C' pour 'Client'
            self.n_carte = 'C' + uuid.uuid4().hex[:8].upper()
        super(Client, self).save(*args, **kwargs)

    def adjust_credit(self, amount):
        """
        Ajuste le crédit du client.

        :param amount: Decimal
        """
        self.credit += amount
        if self.credit < Decimal('0.00'):
            self.credit = Decimal('0.00')
        self.save()

    def adjust_fidelity_points(self, points):
        """
        Ajuste les points de fidélité du client.

        :param points: Decimal
        """
        self.fidelity_points += points
        if self.fidelity_points < Decimal('0.00'):
            self.fidelity_points = Decimal('0.00')
        self.save()

    class Meta:
        ordering = ['nom', 'prenom']
        verbose_name = "Client"
        verbose_name_plural = "Clients"

class Transaction(models.Model):
    MODE_PAIEMENT_CHOICES = [
        ('carte', 'Carte Bancaire'),
        ('cash', 'Espèces'),
    ]

    client = models.ForeignKey(
        Client, null=True, blank=True, on_delete=models.SET_NULL, related_name='transactions'
    )
    total_price = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Montant total de la transaction après réductions et applications des crédits/points."
    )
    total_reduction = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        help_text="Total des réductions appliquées."
    )
    total_items = models.PositiveIntegerField(default=0)
    credit_applied = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Montant du crédit appliqué à cette transaction."
    )
    points_applied = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Montant des points de fidélité appliqués à cette transaction."
    )
    points_gagnes = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Points gagnés lors de cette transaction."
    )
    date = models.DateTimeField(default=timezone.now)
    mode_paiement = models.CharField(max_length=20, choices=MODE_PAIEMENT_CHOICES)

    def __str__(self):
        client_name = f"{self.client.prenom} {self.client.nom}" if self.client else "Anonyme"
        return f"Transaction {self.id} - Client: {client_name}"

    def calculate_totals(self):
        """
        Calcule et met à jour les totaux de la transaction en fonction des articles associés.
        """
        items = self.items.all()
        self.total_price = sum(
            (item.price - item.reduction) * item.quantity for item in items
        ) - self.credit_applied - self.points_applied
        self.total_reduction = sum(
            (item.reduction * item.quantity) for item in items
        ) + self.credit_applied + self.points_applied
        self.total_items = sum(item.quantity for item in items)
        self.save()

    def calculate_total_adjusted(self):
        """
        Calcule le total ajusté de la transaction après les retours d'articles.
        """
        total_returned_amount = self.items.aggregate(
            total=Sum('returns__refund_amount')
        )['total'] or Decimal('0.00')

        return self.total_price - total_returned_amount

    class Meta:
        verbose_name = "Transaction"
        verbose_name_plural = "Transactions"


class TransactionItem(models.Model):
    transaction = models.ForeignKey(
        Transaction, related_name='items', on_delete=models.CASCADE
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Prix unitaire de l'article."
    )
    reduction = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        help_text="Réduction unitaire appliquée à l'article."
    )
    points_gagnes = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Points gagnés sur cet article."
    )
    returned_quantity = models.PositiveIntegerField(
        default=0,
        help_text="Quantité déjà retournée pour cet article."
    )
    promotion_applied = models.BooleanField(
        default=False,
        help_text="Indique si une promotion a été appliquée sur cet article."
    )

    def __str__(self):
        return f"{self.quantity} x {self.product.nom_article}"

    def is_on_sale(self):
        """
        Vérifie si l'article est en promotion.

        :return: bool
        """
        return self.reduction > Decimal('0.00')

    def get_total_price(self):
        """
        Calcule le prix total pour cet article, en tenant compte de la réduction.

        :return: Decimal
        """
        return (self.price - self.reduction) * self.quantity

    def get_returnable_quantity(self):
        """
        Calcule la quantité qui peut encore être retournée pour cet article.

        :return: int
        """
        return self.quantity - self.returned_quantity

    def calculate_adjusted_total(self):
        """
        Calcule le total ajusté de cet article après avoir pris en compte la quantité retournée.

        :return: Decimal
        """
        total_quantity = self.quantity - self.returned_quantity
        return (self.price - self.reduction) * total_quantity

    class Meta:
        verbose_name = "Article de Transaction"
        verbose_name_plural = "Articles de Transaction"


class Return(models.Model):
    transaction_item = models.ForeignKey(
        TransactionItem, on_delete=models.CASCADE, related_name='returns'
    )
    quantity_returned = models.PositiveIntegerField(default=1)
    reason = models.TextField(null=True, blank=True)
    date_returned = models.DateTimeField(auto_now_add=True)
    refund_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        help_text="Montant remboursé au client pour ce retour."
    )
    points_removed = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        help_text="Points retirés lors du retour."
    )

    def __str__(self):
        return f"Retour de {self.transaction_item.product.nom_article} ({self.quantity_returned})"

    class Meta:
        verbose_name = "Retour"
        verbose_name_plural = "Retours"


class Voucher(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='vouchers')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date_issued = models.DateTimeField(auto_now_add=True)
    valid_until = models.DateTimeField(help_text="Date d'expiration du bon.")
    code = models.CharField(max_length=50, unique=True, help_text="Code unique du bon.")

    def __str__(self):
        return f"Bon d'achat de {self.amount} € pour {self.client}"

    class Meta:
        verbose_name = "Bon d'Achat"
        verbose_name_plural = "Bons d'Achat"


# Signaux pour gérer la mise à jour des stocks lors des transactions
@receiver(pre_save, sender=TransactionItem)
def update_stock_on_transaction_item_save(sender, instance, **kwargs):
    """
    Met à jour le stock du produit avant de sauvegarder un article de transaction.
    Si l'article existe déjà, ajuste le stock en fonction de la différence de quantité.
    """
    if instance.pk:
        old_item = TransactionItem.objects.get(pk=instance.pk)
        quantity_diff = instance.quantity - old_item.quantity
    else:
        quantity_diff = instance.quantity

    if instance.product.quantite < quantity_diff:
        raise ValidationError('La quantité demandée dépasse le stock disponible.')

    # Ajuster le stock du produit
    instance.product.adjust_stock(-quantity_diff)


@receiver(post_delete, sender=TransactionItem)
def update_stock_on_transaction_item_delete(sender, instance, **kwargs):
    """
    Restaure le stock du produit lorsqu'un article de transaction est supprimé.
    """
    instance.product.adjust_stock(instance.quantity)
