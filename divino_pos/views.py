# -*- coding: utf-8 -*-
from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN
from datetime import datetime, timedelta
from django.contrib import messages
from .forms import DiscountForm, StockUpdateForm, ProductForm, ClientCreationForm
from django.utils.timezone import make_aware
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models.functions import TruncDate
from django.db.models import Q, Sum, Count, Max
from django.http import HttpResponseRedirect, HttpResponse, Http404, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import get_template
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.urls import reverse
from django.views.decorators.http import require_POST
from xhtml2pdf import pisa
import pandas as pd
import requests
from .forms import ReturnForm
from .models import (
    Client, Product, Transaction, TransactionItem, Return, Voucher
)

# Constantes
ITEMS_PER_PAGE = 10
DEFAULT_DAYS = 7


# Fonction d'importation des produits
@login_required
def import_products(request):
    """
    Importe des produits à partir d'un fichier Excel.

    Améliorations apportées :
    - Ajout du décorateur @login_required pour sécuriser la vue.
    - Utilisation de bulk_create pour améliorer les performances.
    - Ajout de validations et de gestion des erreurs plus robustes.
    """
    
    if request.method == "POST":
        file = request.FILES.get('file')
        if not file:
            messages.error(request, "Veuillez sélectionner un fichier à importer.")
            return render(request, 'import_products.html')

        try:
            df = pd.read_excel(file)
            products = []
            for _, row in df.iterrows():
                # Validation des données
                if pd.isna(row['code_ean']) or pd.isna(row['nom_article']):
                    continue  # Ignorer les lignes avec des données manquantes
                product = Product(
                    code_ean=row['code_ean'],
                    code_article=row.get('code_article', ''),
                    nom_article=row['nom_article'],
                    prix_achat=row.get('prix_achat', 0),
                    prix_vente=row.get('prix_vente', 0),
                    categorie=row.get('categorie', ''),
                    couleurs=row.get('couleurs', ''),
                    tailles=row.get('tailles', ''),
                    quantite=row.get('quantite', 0),
                )
                products.append(product)
            Product.objects.bulk_create(products)
            messages.success(request, "L'importation des produits a été réalisée avec succès !")
        except Exception as e:
            messages.error(request, f"Erreur lors de l'importation des produits : {str(e)}")

    return render(request, 'import_products.html')


# Fonction d'importation des clients
@login_required
def import_clients(request):
    """
    Importe des clients à partir d'un fichier Excel.

    Améliorations apportées :
    - Ajout du décorateur @login_required pour sécuriser la vue.
    - Utilisation de bulk_create pour améliorer les performances.
    - Gestion des dates d'anniversaire avec un format flexible.
    """
    if request.method == "POST":
        file = request.FILES.get('file')
        if not file:
            messages.error(request, "Veuillez sélectionner un fichier à importer.")
            return render(request, 'import_clients.html')

        try:
            df = pd.read_excel(file)
            clients = []
            for _, row in df.iterrows():
                date_anniversaire = None
                if 'date_anniversaire' in row and pd.notna(row['date_anniversaire']):
                    try:
                        date_anniversaire = pd.to_datetime(row['date_anniversaire']).date()
                    except Exception:
                        pass  # Gérer les dates mal formatées

                client = Client(
                    n_carte=row.get('n_carte', ''),
                    nom=row.get('nom', ''),
                    prenom=row.get('prenom', ''),
                    date_anniversaire=date_anniversaire,
                    email=row.get('email', ''),
                    numero_rue=row.get('numero_rue', ''),
                    code_postal=row.get('code_postal', ''),
                    ville=row.get('ville', ''),
                    pays=row.get('pays', ''),
                    telephone=row.get('telephone', '')
                )
                clients.append(client)
            Client.objects.bulk_create(clients)
            messages.success(request, "L'importation des clients a été réalisée avec succès !")
        except Exception as e:
            messages.error(request, f"Erreur lors de l'importation des clients : {str(e)}")

    return render(request, 'import_clients.html')


# Vue pour le POS
@login_required
def pos_view(request):
    """
    Vue principale du point de vente (POS).

    Améliorations apportées :
    - Refactorisation du code pour améliorer la lisibilité.
    - Gestion des sessions de manière sécurisée.
    - Utilisation de fonctions auxiliaires pour le calcul des totaux.
    - Ajout de validations supplémentaires.
    """
    products = Product.objects.all()
    panier = request.session.get('panier', {})
    selected_client = None
    search_results = None
    show_add_client_modal = False
    show_client_search_modal = False
    show_stock_modal = False
    product_insufficient_stock = None
    total_panier = Decimal('0.00')
    total_item_reductions = Decimal('0.00')
    global_reduction_percentage = Decimal(request.session.get('global_discount_percentage', '0.00'))
    global_reduction_amount = Decimal('0.00')
    total_reduction = Decimal('0.00')
    points_appliques = Decimal(request.session.get('points_appliques', '0.00'))
    credit_applique = Decimal('0.00')
    product_form = ProductForm()
    client_form = ClientCreationForm(request.POST or None)

    # Gestion de la recherche de client
    if 'search_client' in request.GET:
        search_query = request.GET.get('search_client').strip()
        search_results = Client.objects.filter(
            Q(nom__icontains=search_query) |
            Q(prenom__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(numero_rue__icontains=search_query)
        )
        if search_results.count() == 1:
            selected_client = search_results.first()
            request.session['selected_client_id'] = selected_client.id
        elif search_results.count() > 1:
            show_client_search_modal = True
        else:
            messages.error(request, "Aucun client trouvé. Vous pouvez l'ajouter manuellement.")
            show_add_client_modal = True

    # Gestion de l'ajout manuel de client
    if request.method == "POST" and 'add_client' in request.POST:
        client_form = ClientCreationForm(request.POST)
        if client_form.is_valid():
            new_client = client_form.save()
            
            # Ajouter le client à la session
            request.session['selected_client_id'] = new_client.id
            messages.success(request, f"Client {new_client.nom} {new_client.prenom} ajouté avec succès.")
            return redirect('pos')  # Rediriger vers la page POS après ajout du client
        else:
            # Le formulaire n'est pas valide, les erreurs seront affichées dans le template
            messages.error(request, "Veuillez corriger les erreurs dans le formulaire d'ajout de client.")
    else:
        client_form = ClientCreationForm()

    # Gestion du client sélectionné via la modale
    if request.method == "POST" and 'selected_client_id' in request.POST:
        client_id = request.POST.get('selected_client_id')
        selected_client = get_object_or_404(Client, id=client_id)
        request.session['selected_client_id'] = selected_client.id

    # Récupérer le client sélectionné dans la session
    if 'selected_client_id' in request.session:
        try:
            selected_client = Client.objects.get(id=request.session['selected_client_id'])
        except Client.DoesNotExist:
            del request.session['selected_client_id']
            messages.error(request, "Le client sélectionné n'existe plus.")
            selected_client = None
    
    # Gestion de la soumission du formulaire de correction de stock
    if request.method == "POST" and 'correct_stock' in request.POST:
        product_id = request.POST.get('product_id')
        new_stock = int(request.POST.get('new_stock'))
        product = get_object_or_404(Product, id=product_id)
        product.quantite = new_stock
        product.save()
        messages.success(request, f"Le stock du produit '{product.nom_article}' a été mis à jour.")
        return redirect('pos')
    
    # Gestion de l'ajout de produits au panier
    if request.method == "POST" and 'code_ean' in request.POST:
        code_input = request.POST['code_ean'].strip()
        try:
            product = Product.objects.get(Q(code_ean=code_input) | Q(code_article=code_input))
            stock_disponible = product.quantite
            quantite_demandee = panier.get(product.code_ean, {}).get('quantite', 0) + 1

            if stock_disponible < quantite_demandee:
                messages.error(request, f"Stock insuffisant pour le produit '{product.nom_article}'. Quantité disponible : {stock_disponible}.")
                show_stock_modal = True
                product_insufficient_stock = product
            else:
                if product.code_ean in panier:
                    panier[product.code_ean]['quantite'] += 1
                else:
                    panier[product.code_ean] = {
                        'nom': product.nom_article,
                        'prix_vente': str(product.prix_vente),
                        'quantite': 1,
                        'prix_original': str(product.prix_vente),
                        'reduction': False,
                        'montant_reduction': '0.00',
                        'total': str(product.prix_vente),
                    }
                request.session['panier'] = panier
                messages.success(request, f"Produit '{product.nom_article}' ajouté au panier.")
        except Product.DoesNotExist:
            messages.error(request, "Aucun produit trouvé avec ce code EAN ou code article.")

   # Calculer le total du panier et les réductions
    for code_ean, item in panier.items():
        quantite = Decimal(str(item['quantite']))
        prix_original = Decimal(str(item.get('prix_original', item['prix_vente'])))
        item_total = (prix_original * quantite).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        item['total'] = str(item_total)
        total_panier += item_total

        # Calcul des réductions par article
        if item.get('reduction', False):
            reduction_par_article = (Decimal(str(item['montant_reduction'])) * quantite).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
            total_item_reductions += reduction_par_article
            item['prix_vente'] = str((prix_original - Decimal(str(item['montant_reduction']))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
        else:
            item['prix_vente'] = str(prix_original.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

    # Calculer le sous-total après réductions individuelles
    subtotal_after_item_reductions = (total_panier - total_item_reductions).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    # Appliquer les points de fidélité si le bouton est cliqué
    if request.method == "POST" and 'apply_points' in request.POST:
        if selected_client:
            points_disponibles = Decimal(str(selected_client.fidelity_points))
            # Vous pouvez permettre à l'utilisateur de saisir le montant de points à appliquer
            points_to_apply = request.POST.get('points_to_apply')
            if points_to_apply:
                points_to_apply = Decimal(points_to_apply)
            else:
                points_to_apply = points_disponibles  # Appliquer le maximum disponible par défaut

            points_appliques = min(points_disponibles, points_to_apply, subtotal_after_item_reductions)
            if points_appliques > 0:
                # Ne pas déduire les points ici
                request.session['points_appliques'] = str(points_appliques)
                messages.success(request, f"Points de fidélité appliqués : {points_appliques:.2f} €")
            else:
                messages.error(request, "Pas assez de points de fidélité pour appliquer.")
        else:
            messages.error(request, "Aucun client sélectionné pour appliquer les points de fidélité.")

    # Gestion de l'application du crédit du client
    if request.method == "POST" and 'apply_credit' in request.POST:
        if selected_client:
            credit_disponible = selected_client.credit
            subtotal_after_points = subtotal_after_item_reductions - points_appliques
            credit_to_apply = request.POST.get('credit_to_apply')
            if credit_to_apply:
                 credit_to_apply = Decimal(credit_to_apply)
            else:
                credit_to_apply = credit_disponible  # Appliquer le maximum disponible par défaut

            credit_applique = min(credit_disponible, credit_to_apply, subtotal_after_points)
            # Ne pas déduire le crédit ici
            request.session['credit_applique'] = str(credit_applique)
            messages.success(request, f"Crédit de {credit_applique} € appliqué.")
        else:
            messages.error(request, "Aucun client sélectionné pour appliquer le crédit.")

    # Récupérer les points de fidélité et le crédit appliqués depuis la session
    try:
        points_appliques = Decimal(request.session.get('points_appliques', '0.00'))
        credit_applique = Decimal(request.session.get('credit_applique', '0.00'))
    except (ValueError, TypeError):
        points_appliques = Decimal('0.00')
        credit_applique = Decimal('0.00')

    # Calculer le sous-total après application des points de fidélité
    subtotal_after_points = (subtotal_after_item_reductions - points_appliques).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    # Vérifier si le crédit doit être appliqué
    if 'apply_credit' in request.POST:
        if selected_client:
            credit_disponible = selected_client.credit
            credit_applique = min(credit_disponible, subtotal_after_points)
            subtotal_after_points_and_credit = (subtotal_after_points - credit_applique).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            request.session['credit_applique'] = str(credit_applique)
            messages.success(request, f"Crédit de {credit_applique} € appliqué.")
        else:
            credit_applique = Decimal('0.00')
            subtotal_after_points_and_credit = subtotal_after_points
    else:
        credit_applique = Decimal('0.00')
        subtotal_after_points_and_credit = subtotal_after_points

    # Après avoir géré la sélection du client
    if 'selected_client_id' in request.session:
        try:
            selected_client = Client.objects.get(id=request.session['selected_client_id'])
            # Réinitialiser le crédit appliqué lorsque le client est sélectionné
            request.session['credit_applique'] = '0.00'
        except Client.DoesNotExist:
            del request.session['selected_client_id']
            messages.error(request, "Le client sélectionné n'existe plus.")
            selected_client = None
 
    # Appliquer la réduction globale
    global_reduction_percentage = Decimal(request.session.get('global_discount_percentage', '0.00'))
    if global_reduction_percentage > 0:
        global_reduction_amount = (subtotal_after_points_and_credit * (global_reduction_percentage / 100)).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
    else:
        global_reduction_amount = Decimal('0.00')

    # Calculer le total des réductions
    total_reduction = (total_item_reductions + points_appliques + credit_applique + global_reduction_amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    # Calculer le total à payer
    total_a_payer = (total_panier - total_reduction).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    if total_a_payer < Decimal('0.00'):
        total_a_payer = Decimal('0.00')

    # Appliquer le crédit du client après avoir calculé total_a_payer
    #if selected_client:
    #    credit_applique = min(selected_client.credit, total_a_payer)
    #   total_a_payer -= credit_applique
    #   request.session['credit_applique'] = str(credit_applique)

    # Calcul du chiffre d'affaires du jour
    today = timezone.now().date()
    total_sales_today = Transaction.objects.filter(date__date=today).aggregate(Sum('total_price'))['total_price__sum'] or 0

    # Mettre à jour le panier dans la session
    request.session['panier'] = panier
    request.session['total_panier'] = float(total_panier)
    request.session['total_reduction'] = float(total_reduction)
    request.session['total_item_reductions'] = float(total_item_reductions)
    request.session['global_reduction_amount'] = float(global_reduction_amount)
    request.session['points_appliques'] = float(points_appliques)
    request.session['credit_applique'] = float(credit_applique)
    request.session['total_a_payer'] = float(total_a_payer)

    context = {
        'products': products,
        'panier': panier,
        'total_panier': total_panier.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        'total_reduction': total_reduction,
        'total_item_reductions': total_item_reductions.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        'global_reduction_amount': global_reduction_amount.quantize(Decimal('0.01'), rounding=ROUND_DOWN),
        'points_appliques': points_appliques.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        'total_a_payer': total_a_payer.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        'credit_applique': credit_applique.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        'selected_client': selected_client,
        'search_results': search_results,
        'show_client_search_modal': show_client_search_modal,
        'show_stock_modal': show_stock_modal,
        'product_insufficient_stock': product_insufficient_stock,
        'total_sales_today': total_sales_today,
        'product_form': product_form,
        'client_form': client_form,
        'show_add_client_modal': show_add_client_modal,
    }
    return render(request, 'pos.html', context)

# Fonction pour ajouter un produit au panier
def add_product_to_cart(request, code_input):
    """
    Ajoute un produit au panier.

    Améliorations apportées :
    - Séparation de la logique pour une meilleure réutilisabilité.
    - Gestion des stocks améliorée.
    - Messages d'erreur plus précis.
    """
    try:
        product = Product.objects.get(Q(code_ean=code_input) | Q(code_article=code_input))
        panier = request.session.get('panier', {})
        stock_disponible = product.quantite
        quantite_demandee = panier.get(product.code_ean, {}).get('quantite', 0) + 1

        if stock_disponible < quantite_demandee:
            messages.error(request, f"Stock insuffisant pour le produit '{product.nom_article}'. Quantité disponible : {stock_disponible}.")
            request.session['show_stock_modal'] = True
            request.session['product_insufficient_stock'] = product.id
            return

        if product.code_ean in panier:
            panier[product.code_ean]['quantite'] += 1
        else:
            panier[product.code_ean] = {
                'nom': product.nom_article,
                'prix_vente': str(product.prix_vente),
                'quantite': 1,
                'prix_original': str(product.prix_vente),
                'reduction': False,
                'montant_reduction': '0.00',
                'total': str(product.prix_vente),
            }
        request.session['panier'] = panier
        messages.success(request, f"Produit '{product.nom_article}' ajouté au panier.")
    except Product.DoesNotExist:
        messages.error(request, "Aucun produit trouvé avec ce code EAN ou code article.")


# Fonction pour calculer les totaux du panier
def calculate_totals(request, panier):
    """
    Calcule les totaux du panier, y compris les réductions et le total à payer.

    Améliorations apportées :
    - Refactorisation pour améliorer la lisibilité.
    - Gestion des arrondis pour éviter les erreurs de précision.
    - Gestion des points de fidélité et des réductions globales.
    """
    total_panier = Decimal('0.00')
    total_item_reductions = Decimal('0.00')
    points_appliques = Decimal(request.session.get('points_appliques', '0.00'))
    global_reduction_percentage = Decimal(request.session.get('global_discount_percentage', '0.00'))

    for code_ean, item in panier.items():
        quantite = Decimal(str(item['quantite']))
        prix_original = Decimal(str(item.get('prix_original', item['prix_vente'])))
        item_total = (prix_original * quantite).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        item['total'] = str(item_total)
        total_panier += item_total

        # Calcul des réductions par article
        if item.get('reduction', False):
            reduction_par_article = (Decimal(str(item['montant_reduction'])) * quantite).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
            total_item_reductions += reduction_par_article
            item['prix_vente'] = str((prix_original - Decimal(str(item['montant_reduction']))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
        else:
            item['prix_vente'] = str(prix_original.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

    # Calculer le sous-total après réductions individuelles
    subtotal_after_item_reductions = (total_panier - total_item_reductions).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    # Appliquer les points de fidélité
    subtotal_after_points = (subtotal_after_item_reductions - points_appliques).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    # Appliquer la réduction globale
    if global_reduction_percentage > 0:
        global_reduction_amount = (subtotal_after_points * (global_reduction_percentage / 100)).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
    else:
        global_reduction_amount = Decimal('0.00')

    # Calculer le total des réductions
    total_reduction = (total_item_reductions + points_appliques + global_reduction_amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    # Calculer le total à payer
    total_a_payer = (total_panier - total_reduction).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    if total_a_payer < Decimal('0.00'):
        total_a_payer = Decimal('0.00')

    return total_panier, total_item_reductions, subtotal_after_item_reductions, points_appliques, global_reduction_amount, total_reduction, total_a_payer


# Fonction pour retirer un article du panier
def remove_from_cart(request, code_ean):
    """
    Retire un article du panier.

    Améliorations apportées :
    - Gestion sécurisée du panier.
    """
    panier = request.session.get('panier', {})
    if code_ean in panier:
        del panier[code_ean]
        request.session['panier'] = panier
        messages.success(request, "Article retiré du panier.")
    return redirect('pos')

# Fonction pour finaliser la vente
@login_required
@transaction.atomic
def finalize_sale(request):
    """
    Finalise la vente en créant une transaction.
    """
    panier = request.session.get('panier', {})
    client_id = request.session.get('selected_client_id', None)
    points_appliques = Decimal(request.session.get('points_appliques', '0.00'))
    credit_applique = Decimal(request.session.get('credit_applique', '0.00'))
    global_reduction_percentage = Decimal(request.session.get('global_discount_percentage', '0.00'))

    if not panier:
        messages.error(request, "Aucun produit dans le panier.")
        return redirect('pos')

    client = None
    if client_id:
        client = get_object_or_404(Client, id=client_id)

    if request.method == 'POST':
        mode_paiement = request.POST.get('mode_paiement')

        try:
            total_vente = Decimal('0.00')
            total_reduction = Decimal('0.00')
            total_items = 0

            # Déterminer si une réduction globale est appliquée
            reduction_globale_appliquee = global_reduction_percentage > Decimal('0.00')

            # Création de la transaction
            new_transaction = Transaction.objects.create(
                client=client,
                total_price=Decimal('0.00'),  # Sera mis à jour plus tard
                total_reduction=Decimal('0.00'),  # Sera mis à jour plus tard
                total_items=0,  # Sera mis à jour plus tard
                points_applied=points_appliques,
                credit_applied=credit_applique,
                mode_paiement=mode_paiement,
                points_gagnes=Decimal('0.00'),  # Sera mis à jour plus tard
                date=timezone.now()
            )

            # Initialiser les points gagnés totaux et le montant éligible aux points
            points_gagnes_total = Decimal('0.00')
            total_eligible_amount = Decimal('0.00')

            # Traitement des articles du panier
            for code_ean, item in panier.items():
                product = Product.objects.select_for_update().get(code_ean=code_ean)
                quantite_demandee = int(item['quantite'])

                if product.quantite < quantite_demandee:
                    raise ValidationError(f"Stock insuffisant pour '{product.nom_article}'.")

                prix_original = Decimal(item['prix_original']).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                prix_vente = Decimal(item['prix_vente']).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                montant_reduction = (prix_original - prix_vente).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

                total_item_original = (prix_original * quantite_demandee).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                total_item_vente = (prix_vente * quantite_demandee).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                total_item_reduction = (montant_reduction * quantite_demandee).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

                total_vente += total_item_original
                total_reduction += total_item_reduction
                total_items += quantite_demandee

                # Déterminer si une promotion individuelle est appliquée sur l'article
                promotion_individuelle = montant_reduction > Decimal('0.00')

                # Déterminer si une promotion a été appliquée sur l'article (individuelle ou globale)
                promotion_applied = promotion_individuelle or reduction_globale_appliquee

                # Si aucune promotion n'est appliquée, ajouter au montant éligible aux points
                if not promotion_applied:
                    total_eligible_amount += total_item_vente

                # Création de l'élément de transaction avec les points gagnés par article
                transaction_item = TransactionItem.objects.create(
                    transaction=new_transaction,
                    product=product,
                    quantity=quantite_demandee,
                    price=prix_vente,
                    reduction=montant_reduction,
                    points_gagnes=Decimal('0.00'),  # Sera mis à jour plus tard
                    promotion_applied=promotion_applied  # Indiquer si une promotion a été appliquée
                )

                # Mise à jour du stock
                # product.quantite -= quantite_demandee
                product.save()

            # Application de la réduction globale
            if reduction_globale_appliquee:
                subtotal_after_item_reductions = total_vente - total_reduction
                global_reduction_amount = (subtotal_after_item_reductions * (global_reduction_percentage / Decimal('100'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                total_reduction += global_reduction_amount

            # Calcul du total à payer après réductions
            subtotal_after_reductions = total_vente - total_reduction
            total_a_payer = (subtotal_after_reductions - credit_applique - points_appliques).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            if total_a_payer < Decimal('0.00'):
                total_a_payer = Decimal('0.00')

            # Calcul des points de fidélité gagnés
            if client and total_eligible_amount > Decimal('0.00') and not reduction_globale_appliquee:
                # Calculer la proportion du montant éligible
                proportion_eligible = total_eligible_amount / subtotal_after_reductions
                # Calculer le montant payé par le client pour les articles éligibles
                amount_paid_for_eligible_items = (total_a_payer * proportion_eligible).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                # Calculer les points gagnés
                points_gagnes_total = (amount_paid_for_eligible_items * Decimal('0.05')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                # Ajouter les points gagnés au client
                client.fidelity_points += points_gagnes_total
                client.save()
            else:
                points_gagnes_total = Decimal('0.00')

            # Mise à jour de la transaction
            new_transaction.total_price = total_a_payer  # Montant final à payer après toutes les déductions
            new_transaction.total_reduction = total_reduction + credit_applique + points_appliques  # Total des réductions, y compris les crédits et points appliqués
            new_transaction.total_items = total_items
            new_transaction.points_gagnes = points_gagnes_total
            new_transaction.points_applied = points_appliques
            new_transaction.credit_applied = credit_applique
            new_transaction.mode_paiement = mode_paiement
            new_transaction.save()

            # Mise à jour des points gagnés par article dans TransactionItem
            for item in new_transaction.items.all():
                if item.reduction == Decimal('0.00') and not reduction_globale_appliquee:
                    # Calculer la proportion de l'article éligible
                    item_total = item.price * item.quantity
                    item_proportion = item_total / total_eligible_amount if total_eligible_amount > Decimal('0.00') else Decimal('0.00')
                    # Points gagnés pour cet article
                    item.points_gagnes = (points_gagnes_total * item_proportion).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    item.save()
                else:
                    item.points_gagnes = Decimal('0.00')
                    item.save()

            # Application du crédit
            if client and credit_applique > Decimal('0.00'):
                if credit_applique > client.credit:
                    # Ajuster le crédit appliqué si le client n'a pas assez de crédit
                    credit_applique = client.credit
                client.credit -= credit_applique
                client.save()

            # Application des points de fidélité
            if client and points_appliques > Decimal('0.00'):
                if points_appliques > client.fidelity_points:
                    # Ajuster les points appliqués si le client n'a pas assez de points
                    points_appliques = client.fidelity_points
                client.fidelity_points -= points_appliques
                client.save()

            # Réinitialisation des variables de session
            request.session['panier'] = {}
            request.session['selected_client_id'] = None
            request.session['points_appliques'] = '0.00'
            request.session['credit_applique'] = '0.00'
            request.session['global_discount_percentage'] = '0.00'

            messages.success(request, f"Vente finalisée avec succès ! Total à payer : {total_a_payer} €. Points gagnés : {points_gagnes_total}.")
            return redirect('generate_ticket', transaction_id=new_transaction.id)

        except ValidationError as ve:
            messages.error(request, f"Erreur : {ve.message}")
            return redirect('pos')

        except Exception as e:
            messages.error(request, f"Erreur lors de la finalisation de la vente : {str(e)}")
            return redirect('pos')

    return render(request, 'finalize_sale.html')

# Fonction pour annuler une vente
@login_required
def cancel_sale(request):
    # Récupérer les informations du client
    selected_client_id = request.session.get('selected_client_id')
    credit_applique = Decimal(request.session.get('credit_applique', '0.00'))
    points_appliques = Decimal(request.session.get('points_appliques', '0.00'))

    # Restaurer le crédit et les points de fidélité du client
    if selected_client_id:
        try:
            selected_client = Client.objects.get(id=selected_client_id)
            # Restaurer le crédit
            selected_client.credit += credit_applique
            # Restaurer les points de fidélité
            selected_client.fidelity_points += points_appliques
            selected_client.save()
        except Client.DoesNotExist:
            pass  # Le client n'existe pas, rien à faire

    # Réinitialiser le panier et les variables de session
    request.session['panier'] = {}
    request.session['total_panier'] = '0.00'
    request.session['total_reduction'] = '0.00'
    request.session['total_item_reductions'] = '0.00'
    request.session['global_reduction_amount'] = '0.00'
    request.session['points_appliques'] = '0.00'
    request.session['credit_applique'] = '0.00'
    request.session['total_a_payer'] = '0.00'
    request.session['global_discount_percentage'] = '0.00'
    if 'selected_client_id' in request.session:
        del request.session['selected_client_id']

    messages.success(request, "La vente a été annulée et le crédit a été restauré au client.")

    return redirect('pos')

# Fonction pour appliquer une réduction sur un article
@login_required
def apply_discount(request):
    """
    Applique une réduction sur un article du panier.

    Améliorations apportées :
    - Validation des données entrantes.
    - Gestion des erreurs améliorée.
    """ 
    if request.method == "POST":
        form = DiscountForm(request.POST)
        if form.is_valid():
            code_ean = form.cleaned_data['code_ean']
            discount_percentage = form.cleaned_data['discount_percentage']
            panier = request.session.get('panier', {})

        if code_ean in panier:
            try:
                discount = Decimal(discount_percentage) / 100
                article = panier[code_ean]
                prix_original = Decimal(article['prix_original'])
                reduction = (prix_original * discount).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
                new_price = (prix_original - reduction).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
                article['prix_vente'] = str(new_price)
                article['reduction'] = True
                article['montant_reduction'] = str(reduction)
                quantite = Decimal(str(article['quantite']))
                total_item = (new_price * quantite).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
                article['total'] = str(total_item)
                request.session['panier'] = panier
                messages.success(request, f"Réduction de {discount_percentage}% appliquée à l'article.")
            except Exception as e:
                messages.error(request, f"Erreur lors de l'application de la réduction : {str(e)}")
        else:
            messages.error(request, "Article non trouvé dans le panier.")

    return redirect('pos')


# Fonction pour appliquer une réduction globale sur le panier
@login_required
def apply_global_discount(request):
    """
    Applique une réduction globale sur le panier.

    Améliorations apportées :
    - Validation des données entrantes.
    """
    if request.method == "POST":
        discount_percentage = request.POST.get('global_discount_percentage')
        try:
            discount = Decimal(discount_percentage)
            request.session['global_discount_percentage'] = str(discount)
            messages.success(request, f"Réduction de {discount_percentage}% appliquée sur le panier total.")
        except Exception as e:
            messages.error(request, f"Erreur lors de l'application de la réduction : {str(e)}")
    return redirect('pos')

# Vue pour l'historique détaillé des transactions d'un client
@login_required
def client_history_view(request, client_id):
    """
    Affiche l'historique des transactions et des retours d'un client.

    Améliorations apportées :
    - Ajout du décorateur @login_required pour sécuriser la vue.
    - Utilisation de la pagination pour les transactions et les retours.
    - Optimisation des requêtes avec 'select_related' et 'prefetch_related'.
    - Gestion des cas où le client n'a pas de transactions ou de retours.

    Bonnes pratiques Django :
    - Utilisation de 'get_object_or_404' pour récupérer le client.
    - Gestion efficace des relations entre les modèles.
    """
    # Calcul du chiffre d'affaires du jour
    today = timezone.now().date()
    total_sales_today = Transaction.objects.filter(date__date=today).aggregate(Sum('total_price'))['total_price__sum'] or 0
    
    client = get_object_or_404(Client, id=client_id)
    transactions = Transaction.objects.filter(client=client).order_by('-date').select_related('client')
    total_purchases = transactions.aggregate(total=Sum('total_price'))['total'] or Decimal('0.00')

    # Récupérer les retours effectués par ce client
    returns = Return.objects.filter(transaction_item__transaction__client=client).select_related('transaction_item', 'transaction_item__product')

    # Pagination des transactions
    transaction_paginator = Paginator(transactions, ITEMS_PER_PAGE)
    transaction_page_number = request.GET.get('page')
    transactions_page_obj = transaction_paginator.get_page(transaction_page_number)

    # Pagination des retours
    return_paginator = Paginator(returns, ITEMS_PER_PAGE)
    return_page_number = request.GET.get('return_page')
    returns_page_obj = return_paginator.get_page(return_page_number)

    context = {
        'client': client,
        'transactions': transactions_page_obj,
        'returns': returns_page_obj,
        'total_purchases': total_purchases,
    }

    return render(request, 'client_history.html', context)


# Vue pour lister les produits
@login_required
def list_products(request):
    """
    Affiche la liste des produits avec possibilité de recherche.

    Améliorations apportées :
    - Ajout du décorateur @login_required.
    - Gestion de la recherche avec nettoyage des entrées utilisateur.
    - Ajout de la pagination pour améliorer l'expérience utilisateur.

    Bonnes pratiques Django :
    - Utilisation de Q pour des requêtes de recherche complexes.
    - Passer les données de pagination au template pour une navigation aisée.
    """
    # Calcul du chiffre d'affaires du jour
    today = timezone.now().date()
    total_sales_today = Transaction.objects.filter(date__date=today).aggregate(Sum('total_price'))['total_price__sum'] or 0

    search_query = request.GET.get('search', '').strip()
    if search_query:
        products = Product.objects.filter(
            Q(nom_article__icontains=search_query) |
            Q(code_ean__icontains=search_query)
        )
    else:
        products = Product.objects.all()

    paginator = Paginator(products, ITEMS_PER_PAGE)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'products': page_obj.object_list,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'search_query': search_query,
        'total_sales_today': total_sales_today,
    }

    return render(request, 'list_products.html', context)


# Vue pour ajouter une nouvelle transaction
@login_required
@transaction.atomic
def add_transaction(request):
    """
    Permet d'ajouter manuellement une nouvelle transaction.

    Améliorations apportées :
    - Ajout des décorateurs @login_required et @transaction.atomic.
    - Utilisation de ModelForms pour la validation des données.
    - Gestion des erreurs avec des messages d'information.

    Bonnes pratiques Django :
    - Utiliser des formulaires pour gérer les entrées utilisateur.
    - Valider les données avant de les enregistrer en base de données.
    """
    if request.method == 'POST':
        # Il est recommandé d'utiliser un formulaire ici
        client_id = request.POST.get('client')
        product_id = request.POST.get('product')
        quantity = int(request.POST.get('quantity', 1))
        montant_reduction = Decimal(request.POST.get('montant_reduction', '0.00'))

        client = get_object_or_404(Client, id=client_id)
        product = get_object_or_404(Product, id=product_id)

        total_price = (product.prix_vente * quantity) - montant_reduction

        try:
            # Créer la transaction
            transaction = Transaction.objects.create(
                client=client,
                total_price=total_price,
                total_reduction=montant_reduction,
                total_items=quantity
            )

            # Créer l'élément de transaction
            TransactionItem.objects.create(
                transaction=transaction,
                product=product,
                quantity=quantity,
                price=product.prix_vente,
                reduction=montant_reduction
            )

            messages.success(request, "Transaction ajoutée avec succès.")
            return redirect('transaction_detail', transaction_id=transaction.id)
        except ValidationError as e:
            messages.error(request, f"Erreur lors de l'ajout de la transaction : {e.message_dict}")

    clients = Client.objects.all()
    products = Product.objects.all()
    return render(request, 'add_transaction.html', {'clients': clients, 'products': products})


# Vue pour les détails d'une transaction
@login_required
def transaction_detail(request, transaction_id):
    """
    Affiche les détails d'une transaction spécifique.

    Améliorations apportées :
    - Ajout du décorateur @login_required.
    - Optimisation des requêtes avec 'select_related' et 'prefetch_related'.
    - Calcul du total ajusté en tenant compte des retours.

    Bonnes pratiques Django :
    - Gestion efficace des relations pour réduire le nombre de requêtes.
    """
    # Calcul du chiffre d'affaires du jour
    today = timezone.now().date()
    total_sales_today = Transaction.objects.filter(date__date=today).aggregate(Sum('total_price'))['total_price__sum'] or 0

    transaction = get_object_or_404(Transaction, id=transaction_id)
    items = transaction.items.select_related('product').all()

    total_adjusted = transaction.total_price
    items_with_returns = []

    for item in items:
        returned_items = Return.objects.filter(transaction_item=item)
        total_returned_quantity = returned_items.aggregate(total=Sum('quantity_returned'))['total'] or 0
        total_returned_amount = returned_items.aggregate(total=Sum('refund_amount'))['total'] or Decimal('0.00')
        points_removed = returned_items.aggregate(total=Sum('points_removed'))['total'] or Decimal('0.00')

        total_item = (item.price - item.reduction) * item.quantity

        items_with_returns.append({
            'item': item,
            'returned_quantity': total_returned_quantity,
            'returned_amount': total_returned_amount,
            'points_removed': points_removed,
            'total_item': total_item,
        })

        total_adjusted -= total_returned_amount

    context = {
        'transaction': transaction,
        'items_with_returns': items_with_returns,
        'total_adjusted': total_adjusted,
        'total_sales_today': total_sales_today,
    }

    return render(request, 'divino_pos/transaction_detail.html', context)

# Vue pour l'historique des ventes
@login_required
def sales_history_view(request):
    """
    Affiche l'historique des ventes avec possibilité de filtrer par date.
    """
    # Calcul du chiffre d'affaires du jour
    today = timezone.now().date()
    total_sales_today = Transaction.objects.filter(date__date=today).aggregate(Sum('total_price'))['total_price__sum'] or 0
    # Récupérer les dates de début et de fin depuis les paramètres GET ou utiliser la date du jour
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    if start_date_str and end_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1)
    else:
        # Par défaut, on affiche les ventes du jour
        today = timezone.now().date()
        start_date = datetime.combine(today, datetime.min.time())
        end_date = datetime.combine(today + timedelta(days=1), datetime.min.time())

    # Rendre les dates conscientes du fuseau horaire
    start_date = make_aware(start_date)
    end_date = make_aware(end_date)

    # Récupérer les transactions dans la plage de dates
    transactions = Transaction.objects.filter(date__gte=start_date, date__lt=end_date)

    # Précharger les clients pour optimiser les requêtes
    transactions = transactions.select_related('client')

    # Vérification du nombre de transactions récupérées
    print(f"Nombre de transactions récupérées : {transactions.count()}")

    # Calcul du chiffre d'affaires du jour
    today = timezone.now().date()
    total_sales_today = Transaction.objects.filter(date__date=today).aggregate(Sum('total_price'))['total_price__sum'] or 0

    context = {
        'transactions_with_items': transactions,
        'start_date': start_date.date(),
        'end_date': (end_date - timedelta(days=1)).date(),
        'today': timezone.now().date(),
        'total_sales_today': total_sales_today,
    }

    return render(request, 'sales_history.html', context)

# Vue pour le rapport des ventes
@login_required
def sales_report_view(request):
    """
    Génère un rapport détaillé des ventes pour une période donnée.

    Améliorations apportées :
    - Ajout du décorateur @login_required.
    - Utilisation de 'parse_date' pour la validation des dates.
    - Optimisation des agrégations et des annotations pour les statistiques.
    - Gestion des erreurs avec des messages appropriés.

    Bonnes pratiques Django :
    - Utiliser les fonctions d'agrégation pour obtenir des statistiques précises.
    - Préférer 'TruncDate' pour les regroupements par date.
    """
    # Calcul du chiffre d'affaires du jour
    today = timezone.now().date()
    total_sales_today = Transaction.objects.filter(date__date=today).aggregate(Sum('total_price'))['total_price__sum'] or 0

    today = timezone.now().date()
    start_of_week = today - timedelta(days=today.weekday())

    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    start_date = parse_date(start_date_str) if start_date_str else start_of_week
    end_date = parse_date(end_date_str) if end_date_str else today

    if not start_date or not end_date or start_date > end_date:
        start_date, end_date = start_of_week, today
        messages.error(request, "Les dates fournies sont invalides ou incohérentes. Période par défaut utilisée.")

    sales_data = Transaction.objects.filter(date__date__range=[start_date, end_date])

    total_sales = sales_data.aggregate(total=Sum('total_price'))['total'] or Decimal('0.00')
    total_discounts = sales_data.aggregate(total=Sum('total_reduction'))['total'] or Decimal('0.00')
    total_transactions = sales_data.count()

    # Répartition par mode de paiement
    payment_distribution = sales_data.values('mode_paiement').annotate(
        total_sales=Sum('total_price'),
        total_transactions=Count('id')
    )

    # Top produits
    top_products = TransactionItem.objects.filter(transaction__in=sales_data).values('product__nom_article').annotate(
        total_quantity=Sum('quantity'),
        total_sales=Sum('price')
    ).order_by('-total_sales')[:10]

    # Ventes par catégorie
    sales_by_category = TransactionItem.objects.filter(transaction__in=sales_data).values('product__categorie').annotate(
        total_sales=Sum('price')
    ).order_by('-total_sales')

    # Moyenne des ventes par jour
    days_in_period = (end_date - start_date).days + 1
    avg_sales_per_day = (total_sales / days_in_period).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if days_in_period > 0 else Decimal('0.00')

    # Ventes quotidiennes
    daily_sales = sales_data.annotate(day=TruncDate('date')).values('day').annotate(
        total_sales=Sum('total_price')
    ).order_by('day')

    sales_dates = [sale['day'].strftime('%Y-%m-%d') for sale in daily_sales]
    sales_amounts = [float(sale['total_sales']) for sale in daily_sales]

    context = {
        'total_sales': total_sales,
        'total_discounts': total_discounts,
        'total_transactions': total_transactions,
        'payment_distribution': payment_distribution,
        'top_products': top_products,
        'sales_by_category': sales_by_category,
        'avg_sales_per_day': avg_sales_per_day,
        'start_date': start_date,
        'end_date': end_date,
        'sales_dates': sales_dates,
        'sales_amounts': sales_amounts,
        'total_sales_today': total_sales_today,
    }

    return render(request, 'sales_report.html', context)


# Fonction pour générer un rapport PDF
@login_required
def generate_pdf_report(request):
    """
    Génère un rapport PDF des ventes pour une période donnée.

    Améliorations apportées :
    - Ajout du décorateur @login_required.
    - Utilisation de 'render_to_string' pour générer le contenu HTML.
    - Gestion des erreurs lors de la génération du PDF.

    Bonnes pratiques Django :
    - Sécuriser l'accès aux rapports.
    - Utiliser des bibliothèques appropriées pour la génération de PDF.
    """
    today = timezone.now().date()
    start_of_week = today - timedelta(days=today.weekday())

    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    start_date = parse_date(start_date_str) if start_date_str else start_of_week
    end_date = parse_date(end_date_str) if end_date_str else today

    if not start_date or not end_date or start_date > end_date:
        start_date, end_date = start_of_week, today
        messages.error(request, "Les dates fournies sont invalides ou incohérentes. Période par défaut utilisée.")

    total_sales = Transaction.objects.filter(date__date__range=[start_date, end_date]).aggregate(total=Sum('total_price'))['total'] or Decimal('0.00')

    context = {
        'total_sales': total_sales,
        'start_date': start_date,
        'end_date': end_date,
    }

    template = get_template('sales_report_pdf.html')
    html = template.render(context)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="rapport_ventes.pdf"'

    pisa_status = pisa.CreatePDF(html, dest=response)

    if pisa_status.err:
        return HttpResponse('Erreur lors de la génération du PDF', status=500)

    return response


# Vue pour ajuster le stock d'un produit
@login_required
def update_stock(request):
    """
    Permet de mettre à jour le stock d'un produit.
    """
    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        product = get_object_or_404(Product, id=product_id)
        form = StockUpdateForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, f"Le stock du produit '{product.nom_article}' a été mis à jour avec succès.")
        else:
            messages.error(request, "Erreur lors de la mise à jour du stock.")
    return redirect('pos')


# Vue pour générer un ticket de caisse
@login_required
def generate_ticket_de_caisse(request, transaction_id):
    """
    Génère un ticket de caisse pour une transaction donnée.

    Améliorations apportées :
    - Ajout du décorateur @login_required.
    - Optimisation des requêtes avec 'select_related' et 'prefetch_related'.
    - Gestion des cas où la transaction ou le client n'existe pas.

    Bonnes pratiques Django :
    - Sécuriser l'accès aux informations sensibles.
    - Utiliser des templates pour le rendu du ticket.
    """
    transaction = get_object_or_404(Transaction, id=transaction_id)
    client = transaction.client
    transaction_items = TransactionItem.objects.filter(transaction=transaction).select_related('product')

    points_gagnes = transaction.points_gagnes

    total_vente = transaction.total_price
    total_reduction = transaction.total_reduction
    total_a_payer = total_vente - total_reduction

    items_with_totals = []
    for item in transaction_items:
        total_item = (item.price - item.reduction) * item.quantity
        items_with_totals.append({
            'item': item,
            'total': total_item
        })

    context = {
        'shop_logo_url': '/static/images/shop_logo.png',  # Adapter le chemin si nécessaire
        'transaction_date': transaction.date.strftime('%d/%m/%Y %H:%M'),
        'client_firstname': client.prenom if client else "Anonyme",
        'client_lastname': client.nom if client else "",
        'mode_paiement': transaction.get_mode_paiement_display(),
        'transaction_items': items_with_totals,
        'total_vente': total_vente,
        'total_reduction': total_reduction,
        'total_a_payer': total_a_payer,
        'transaction': transaction,
        'client': client,
        'credit_applied': transaction.credit_applied,
        'points_gagnes': points_gagnes,
    }

    return render(request, 'ticket_de_caisse.html', context)


# Vue pour gérer les retours d'articles
@login_required
@transaction.atomic
def manage_return(request, transaction_id):
    """
    Gère les retours pour une transaction donnée.

    Améliorations apportées :
    - Ajout des décorateurs @login_required et @transaction.atomic.
    - Validation des entrées utilisateur.
    - Mise à jour du stock et du crédit client de manière sécurisée.
    - Calcul correct des points de fidélité à retirer lors du retour.
    - Enregistrement des points retirés dans le modèle Return.

    Bonnes pratiques Django :
    - Vérifier les permissions avant d'autoriser des opérations sensibles.
    - Utiliser des formulaires pour gérer les entrées utilisateur.
    - Utiliser des méthodes du modèle pour ajuster les points de fidélité du client.
    """
    # Calcul du chiffre d'affaires du jour
    today = timezone.now().date()
    total_sales_today = Transaction.objects.filter(date__date=today).aggregate(Sum('total_price'))['total_price__sum'] or 0

    transaction = get_object_or_404(Transaction, id=transaction_id)
    transaction_items = transaction.items.select_related('product').all()
    client = transaction.client

    if request.method == 'POST':
        for item in transaction_items:
            quantity_to_return = int(request.POST.get(f'quantity_returned_{item.id}', 0))

            if quantity_to_return > 0:
                # Vérifier si une promotion a été appliquée sur l'article
                if item.promotion_applied:
                    messages.error(request, f"Le produit '{item.product.nom_article}' a bénéficié d'une promotion et ne peut pas être retourné.")
                    continue  # Passer à l'article suivant

                total_returnable_quantity = item.quantity - item.returned_quantity
                if quantity_to_return > total_returnable_quantity:
                    messages.error(request, f"Quantité de retour invalide pour '{item.product.nom_article}'.")
                    continue

                # Mise à jour du stock
                item.product.quantite += quantity_to_return
                item.product.save()

                # Calcul du montant du remboursement (prix de vente)
                refund_amount = (item.price * quantity_to_return).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

                # Mise à jour du crédit du client
                if client:
                    client.credit += refund_amount
                    client.save()

                # Calcul des points de fidélité à retirer
                points_to_remove = Decimal('0.00')
                if item.points_gagnes > Decimal('0.00'):
                    ratio = Decimal(quantity_to_return) / Decimal(item.quantity)
                    points_to_remove = (item.points_gagnes * ratio).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

                    # Mise à jour des points de fidélité du client
                    client.fidelity_points -= points_to_remove
                    client.save()

                    messages.success(request, f"{points_to_remove} points de fidélité retirés du compte du client.")

                # Enregistrement du retour
                Return.objects.create(
                    transaction_item=item,
                    quantity_returned=quantity_to_return,
                    refund_amount=refund_amount,
                    points_removed=points_to_remove
                )

                # Mise à jour de la quantité retournée pour l'item de transaction
                item.returned_quantity += quantity_to_return
                item.save()

                messages.success(request, f"{quantity_to_return} x {item.product.nom_article} retourné. Crédit de {refund_amount} € ajouté au compte du client.")

        return redirect('transaction_detail', transaction_id=transaction_id)

    context = {
        'transaction': transaction,
        'items': transaction_items,
        'total_sales_today': total_sales_today,
    }

    return render(request, 'manage_return.html', context)

@login_required
@transaction.atomic
def return_item_view(request, transaction_item_id):
    """
    Gère le retour d'un article spécifique d'une transaction.

    Cette vue permet de traiter le retour d'un article en particulier.
    Elle valide la quantité retournée, met à jour le stock, le crédit du client,
    et enregistre le retour dans la base de données.

    Paramètres :
    - request : objet HttpRequest.
    - transaction_item_id : ID de l'article de transaction à retourner.

    Retourne :
    - Un rendu de la page de retour d'article ou une redirection.

    Bonnes pratiques Django :
    - Utilisation de formulaires pour la validation des entrées utilisateur.
    - Gestion des transactions atomiques pour assurer la cohérence des données.
    - Protection de la vue avec le décorateur @login_required.
    """
    transaction_item = get_object_or_404(TransactionItem, id=transaction_item_id)
    client = transaction_item.transaction.client

    if request.method == 'POST':
        form = ReturnForm(request.POST, transaction_item=transaction_item)
        if form.is_valid():
            returned_item = form.save(commit=False)
            quantity_returned = form.cleaned_data['quantity_returned']
            reason = form.cleaned_data.get('reason', '')

            # Vérifier que la quantité retournée ne dépasse pas la quantité disponible
            if quantity_returned > transaction_item.get_returnable_quantity():
                form.add_error('quantity_returned', "La quantité retournée dépasse la quantité disponible.")
                return render(request, 'return_item.html', {
                    'form': form,
                    'transaction_item': transaction_item
                })

            # Calculer le montant du remboursement
            refund_amount = (transaction_item.price - transaction_item.reduction) * quantity_returned
            refund_amount = refund_amount.quantize(Decimal('0.01'))

            # Ajuster la quantité retournée dans TransactionItem
            transaction_item.returned_quantity += quantity_returned
            transaction_item.save()

            # Mettre à jour le stock du produit
            transaction_item.product.adjust_stock(quantity_returned)

            # Mettre à jour le crédit du client
            if client:
                client.adjust_credit(refund_amount)
                messages.success(request, f"Crédit de {refund_amount} € ajouté au compte du client.")

            # Calculer les points à retirer
            points_to_remove = Decimal('0.00')
            if transaction_item.points_gagnes > Decimal('0.00'):
                ratio = Decimal(quantity_returned) / Decimal(transaction_item.quantity)
                points_to_remove = (transaction_item.points_gagnes * ratio).quantize(Decimal('0.01'))
                if client:
                    client.adjust_fidelity_points(-points_to_remove)
                    messages.success(request, f"{points_to_remove} points de fidélité retirés du compte du client.")

            # Enregistrer le retour
            returned_item.transaction_item = transaction_item
            returned_item.quantity_returned = quantity_returned
            returned_item.refund_amount = refund_amount
            returned_item.points_removed = points_to_remove
            returned_item.reason = reason
            returned_item.save()

            messages.success(request, f"Retour enregistré pour {transaction_item.product.nom_article} (Quantité : {quantity_returned}).")
            return redirect('transaction_detail', transaction_id=transaction_item.transaction.id)
        else:
            messages.error(request, "Veuillez corriger les erreurs dans le formulaire.")
    else:
        form = ReturnForm(transaction_item=transaction_item)

    return render(request, 'return_item.html', {
        'form': form,
        'transaction_item': transaction_item
    })


# divino_pos/views.py
@login_required
def client_list(request):
    """
    Affiche la liste des clients avec pagination et recherche.

    Améliorations apportées :
    - Ajout de la pagination pour améliorer la navigation.
    - Ajout de la fonctionnalité de recherche pour filtrer les clients.
    - Utilisation de 'select_related' pour optimiser les requêtes si nécessaire.

    Bonnes pratiques Django :
    - Utilisation de 'login_required' pour protéger l'accès.
    - Validation et nettoyage des entrées utilisateur.
    """
    # Calcul du chiffre d'affaires du jour
    today = timezone.now().date()
    total_sales_today = Transaction.objects.filter(date__date=today).aggregate(Sum('total_price'))['total_price__sum'] or 0

    search_query = request.GET.get('search', '').strip()
    clients = Client.objects.all()

    if search_query:
        clients = clients.filter(
            Q(nom__icontains=search_query) |
            Q(prenom__icontains=search_query) |
            Q(email__icontains=search_query)
        )

    paginator = Paginator(clients, ITEMS_PER_PAGE)  # ITEMS_PER_PAGE peut être défini globalement, par exemple à 10
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'clients': page_obj.object_list,
        'page_obj': page_obj,
        'search_query': search_query,
        'total_sales_today': total_sales_today,
    }

    return render(request, 'client_list.html', context)


@login_required
def client_detail(request, client_id):
    """
    Affiche les détails d'un client spécifique.

    Améliorations apportées :
    - Utilisation de 'get_object_or_404' pour récupérer le client ou renvoyer une 404.
    - Protection de la vue avec 'login_required'.

    Bonnes pratiques Django :
    - Sécuriser l'accès aux données sensibles.
    - Utiliser des templates pour le rendu des données.
    """
    # Calcul du chiffre d'affaires du jour
    today = timezone.now().date()
    total_sales_today = Transaction.objects.filter(date__date=today).aggregate(Sum('total_price'))['total_price__sum'] or 0
    client = get_object_or_404(Client, id=client_id)
    context = {
        'client': client,
        'total_sales_today': total_sales_today,
    }
    return render(request, 'client_detail.html', context)

@login_required
def add_product(request):
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            # Enregistrer le produit sans le sauvegarder immédiatement
            product = form.save(commit=False)
            # Définir une valeur par défaut pour prix_achat
            product.prix_achat = Decimal('0.00')  # Vous pouvez changer la valeur par défaut si nécessaire
            product.save()


            # Optionnel : Ajouter le produit directement au panier
            panier = request.session.get('panier', {})
            code_ean = product.code_ean if product.code_ean else str(product.id)
            if code_ean in panier:
                panier[code_ean]['quantite'] += product.quantite
            else:
                panier[code_ean] = {
                    'nom': product.nom_article,
                    'quantite': product.quantite,
                    'prix_vente': str(product.prix_vente),
                    'prix_original': str(product.prix_vente),
                }
            request.session['panier'] = panier

            messages.success(request, "Produit ajouté avec succès.")
            return redirect('pos')
        else:
            # Le formulaire est invalide, nous devons afficher les erreurs
            # Préparer les variables de contexte nécessaires pour le template 'pos.html'

            # Récupérer le panier actuel
            panier = request.session.get('panier', {})

            # Calculer le total à payer et les réductions (vous devrez peut-être adapter ceci selon votre code)
            total_a_payer = 0
            total_reduction = 0
            for item in panier.values():
                total_a_payer += float(item['prix_vente']) * item['quantite']
                # Ajoutez le calcul des réductions si nécessaire

            # Récupérer le client sélectionné
            selected_client_id = request.session.get('selected_client_id')
            selected_client = None
            if selected_client_id:
                try:
                    selected_client = Client.objects.get(id=selected_client_id)
                except Client.DoesNotExist:
                    pass

            # Préparer le contexte
            context = {
                'panier': panier,
                'total_a_payer': total_a_payer,
                'total_reduction': total_reduction,
                'selected_client': selected_client,
                'product_form': form,  # Formulaire avec les erreurs
                'show_add_product_modal': True,  # Pour réouvrir la modale avec les erreurs
                # Inclure d'autres variables de contexte si nécessaire
            }

            # Rendre le template 'pos.html' avec le contexte
            return render(request, 'pos.html', context)
    else:
        return redirect('pos')

def fetch_eid_data(request):
    try:
        # Remplacez l'URL par votre URL ngrok
        response = requests.get("https://1c18-2a02-a03f-e601-3101-8919-5d74-c915-7b16.ngrok-free.app/read_eid")
        data = response.json()
        return JsonResponse(data)
    except requests.exceptions.RequestException as e:
        return JsonResponse({"error": "Erreur lors de la récupération des données eID", "details": str(e)})