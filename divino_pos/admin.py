from django.contrib import admin
from django import forms
from django.contrib.admin.widgets import AdminDateWidget
from .models import Product, Client, Transaction, TransactionItem, Return, PaymentDetail
from django.db.models import Sum
from decimal import Decimal

# Affichage des informations de retour dans Django Admin
@admin.register(Return)
class ReturnAdmin(admin.ModelAdmin):
    list_display = ('transaction_item', 'quantity_returned', 'refund_amount', 'points_removed', 'date_returned')

# Formulaire personnalisé pour le modèle Client
class ClientAdminForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = '__all__'
        widgets = {
            'date_anniversaire': AdminDateWidget(attrs={'placeholder': 'dd.mm.yyyy'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['date_anniversaire'].input_formats = ['%d.%m.%Y']

# Inline générique pour les éléments de transaction
class TransactionItemInline(admin.TabularInline):
    model = TransactionItem
    extra = 0
    readonly_fields = ('product', 'quantity', 'original_price' , 'price', 'reduction', 'returned_quantity', 'points_gagnes')
    can_delete = False
    show_change_link = True
    fields = ('product', 'quantity', 'original_price' , 'price', 'reduction', 'returned_quantity', 'points_gagnes')

class PaymentDetailInline(admin.TabularInline):
    model = PaymentDetail
    extra = 0  # Pas de formulaires supplémentaires par défaut

# Administration du modèle Client
class ClientAdmin(admin.ModelAdmin):
    form = ClientAdminForm
    list_display = ('n_carte', 'nom', 'prenom', 'date_anniversaire', 'email', 'ville', 'telephone', 'fidelity_points')
    search_fields = ('n_carte', 'nom', 'prenom', 'email', 'telephone')
    list_filter = ('ville', 'pays')
    ordering = ('nom', 'prenom')
    list_per_page = 20

# Inline pour afficher les éléments de transaction associés à un produit
class TransactionProductInline(admin.TabularInline):
    model = TransactionItem
    extra = 0
    readonly_fields = ('quantity', 'price', 'reduction')
    can_delete = False
    show_change_link = True
    fields = ('quantity', 'price', 'reduction')

# Administration du modèle Product
class ProductAdmin(admin.ModelAdmin):
    list_display = ('code_ean', 'code_article', 'nom_article', 'prix_achat', 'prix_vente', 'categorie', 'couleurs', 'tailles', 'quantite')
    search_fields = ('code_ean', 'code_article', 'nom_article')
    list_filter = ('categorie', 'couleurs', 'tailles')
    ordering = ('nom_article',)
    list_per_page = 20
    # Vous pouvez retirer l'inline suivant si cela cause une surcharge :
    inlines = [TransactionProductInline]  # Afficher les transactions associées aux produits

# Administration du modèle Transaction
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'client', 'total_price', 'total_reduction', 'points_applied', 'credit_applied', 'get_payment_methods', 'date')
    list_filter = ('date', 'client')
    search_fields = ('client__prenom', 'client__nom', 'client__n_carte')
    date_hierarchy = 'date'
    ordering = ('-date',)
    readonly_fields = ('total_price', 'total_reduction', 'points_applied', 'credit_applied', 'date', 'total_items')
    list_select_related = ('client',)
    list_per_page = 20
    inlines = [TransactionItemInline, PaymentDetailInline]  # Ajoutez PaymentDetailInline ici

    def get_payment_methods(self, obj):
        return ', '.join(obj.payment_methods_used)
    get_payment_methods.short_description = 'Méthodes de Paiement'

# Enregistrement des modèles dans l'admin
admin.site.register(Client, ClientAdmin)
admin.site.register(Product, ProductAdmin)
admin.site.register(Transaction, TransactionAdmin)
