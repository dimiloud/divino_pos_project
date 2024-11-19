from django.urls import path
from . import views
from django.views.decorators.csrf import csrf_exempt

urlpatterns = [
    # Page principale du POS
    path('pos/', views.pos_view, name='pos'),

    # Importation des produits et des clients
    path('import-products/', views.import_products, name='import_products'),
    path('import-clients/', views.import_clients, name='import_clients'),

    # Gestion des clients
    path('clients/', views.client_list, name='client_list'),
    path('clients/<int:client_id>/', views.client_detail, name='client_detail'),  # Détails d'un client
    path('clients/<int:client_id>/historique/', views.client_history_view, name='client_history'),  # Historique du client

    # Gestion du panier
    path('add-to-cart/', views.add_product_to_cart, name='add_to_cart'),  # Ajout au panier
    path('remove-from-cart/<str:code_ean>/', views.remove_from_cart, name='remove_from_cart'),  # Retrait du panier
    path('add_product/', views.add_product, name='add_product'),

    # Finalisation et annulation de la vente
    path('finalize-sale/', views.finalize_sale, name='finalize_sale'),
    path('cancel-sale/', views.cancel_sale, name='cancel_sale'),

    # Application des réductions
    path('apply-discount/', views.apply_discount, name='apply_discount'),
    path('apply-global-discount/', views.apply_global_discount, name='apply_global_discount'),

    # Gestion des produits
    path('products/', views.list_products, name='list_products'),

    # Gestion des transactions
    path('transactions/add/', views.add_transaction, name='add_transaction'),  # Ajout d'une transaction
    path('transaction/<uuid:transaction_pk>/', views.transaction_detail, name='transaction_detail'),  # Détails d'une transaction

    # Historique des ventes et rapports
    path('sales-history/', views.sales_history_view, name='sales_history'),
    path('sales-report/', views.sales_report_view, name='sales_report'),
    path('sales-report/pdf/', views.generate_pdf_report, name='sales_report_pdf'),

    # Gestion des retours
    path('returns/manage/<uuid:transaction_pk>/', views.manage_return, name='manage_return'),  # UUID pour les transactions
    path('returns/item/<int:transaction_item_id>/', views.return_item_view, name='return_item_view'),

    # Ajustement du stock
    path('update-stock/', views.update_stock, name='update_stock'),

    # Génération du ticket de caisse
    path('ticket/<uuid:transaction_pk>/', views.generate_ticket_de_caisse, name='generate_ticket'),

    # Fonction de lecteur eid
    path('api/read-eid/', views.read_eid_data, name='read_eid_data'),
    path('api/search-client-eid/', views.search_client_eid, name='search_client_eid'),

]
