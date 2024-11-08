# divino_pos/forms.py

from decimal import Decimal
from django import forms
from .models import Return, TransactionItem, Product, Client

class ReturnForm(forms.ModelForm):
    """
    Formulaire pour gérer les retours d'articles.
    """
    class Meta:
        model = Return
        fields = ['quantity_returned', 'reason']

    def __init__(self, *args, **kwargs):
        transaction_item = kwargs.pop('transaction_item', None)
        super().__init__(*args, **kwargs)
        if transaction_item:
            max_quantity = transaction_item.get_returnable_quantity()
            self.fields['quantity_returned'].widget.attrs['max'] = max_quantity
            self.fields['quantity_returned'].validators.append(forms.validators.MaxValueValidator(max_quantity))
            self.fields['quantity_returned'].validators.append(forms.validators.MinValueValidator(1))

class StockUpdateForm(forms.ModelForm):
    """
    Formulaire pour mettre à jour le stock d'un produit.
    """
    class Meta:
        model = Product
        fields = ['quantite']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Ajout d'un attribut HTML pour empêcher les valeurs négatives
        self.fields['quantite'].widget.attrs.update({'min': '0'})

class DiscountForm(forms.Form):
    """
    Formulaire pour appliquer une réduction à un article du panier.
    """
    code_ean = forms.CharField(widget=forms.HiddenInput())
    discount_percentage = forms.DecimalField(
        max_digits=5, decimal_places=2,
        min_value=Decimal('0.01'), max_value=Decimal('100.00'),
        label="Pourcentage de réduction"
    )

class GlobalDiscountForm(forms.Form):
    """
    Formulaire pour appliquer une réduction globale au panier.
    """
    global_discount_percentage = forms.DecimalField(
        max_digits=5, decimal_places=2,
        min_value=Decimal('0.01'), max_value=Decimal('100.00'),
        label="Réduction globale (%)"
    )

class ProductForm(forms.ModelForm):
    # Champ personnalisé déjà existant
    quantite_panier = forms.IntegerField(
        initial=1,
        min_value=1,
        required=True,
        label='Quantité à ajouter au panier',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'value': '1', 'required': True})
    )

    class Meta:
        model = Product
        fields = ['code_ean', 'code_article', 'nom_article', 'tailles', 'prix_vente', 'quantite']
        widgets = {
            'code_ean': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Code EAN (laisser vide pour générer automatiquement)'
            }),
            'code_article': forms.TextInput(attrs={'class': 'form-control'}),
            'nom_article': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'tailles': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'prix_vente': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'required': True}),
            'quantite': forms.NumberInput(attrs={'class': 'form-control', 'required': True, 'min': '1'}),
        }

    def __init__(self, *args, **kwargs):
        super(ProductForm, self).__init__(*args, **kwargs)
        self.fields['code_ean'].required = False  # Rendre le champ optionnel

class ClientCreationForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ['nom', 'prenom', 'date_anniversaire', 'email', 'numero_rue', 'code_postal', 'ville', 'pays', 'telephone']
        widgets = {
            'date_anniversaire': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            if Client.objects.filter(email=email).exists():
                raise forms.ValidationError("Un client avec cet email existe déjà.")
        return email
    def clean_n_carte(self):
        n_carte = self.cleaned_data.get('n_carte')
        if n_carte:
            if Client.objects.filter(n_carte=n_carte).exists():
                raise forms.ValidationError("Un client avec ce numéro de carte existe déjà.")
        return n_carte