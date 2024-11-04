from smartcard.System import readers
from smartcard.util import toHexString
import sys

def read_eid_data():
    # Étape 1 : Obtenez la liste des lecteurs disponibles
    available_readers = readers()
    if not available_readers:
        print("Aucun lecteur de carte détecté.")
        sys.exit()

    # Utilisez le premier lecteur disponible
    reader = available_readers[0]
    print(f"Utilisation du lecteur : {reader}")

    # Étape 2 : Connectez-vous au lecteur
    connection = reader.createConnection()
    connection.connect()

    # Étape 3 : Envoyez une commande APDU pour lire la carte
    # Remarque : Les commandes APDU dépendent du type de carte.
    # Voici une commande APDU simulée (à remplacer par les vraies commandes pour votre carte eID).
    SELECT_EID_COMMAND = [0x00, 0xA4, 0x04, 0x00, 0x0A]  # Exemple de commande APDU
    data, sw1, sw2 = connection.transmit(SELECT_EID_COMMAND)

    if sw1 == 0x90 and sw2 == 0x00:
        print("Commande APDU réussie.")
        print("Données de la carte :", toHexString(data))
    else:
        print(f"Erreur de lecture de la carte : SW1={sw1} SW2={sw2}")

    # Étape 4 : Simulation de données
    # Cette section est une simulation ; remplacez-la avec des données lues de la carte eID.
    eid_data = {
        "nom": "Dupont",
        "prenom": "Jean",
        "date_naissance": "1980-01-01",
        "adresse": "123 Rue de Exemple",
        "ville": "Exempleville",
        "code_postal": "12345",
        "pays": "France"
    }
    return eid_data

# Appeler la fonction et afficher les données
if __name__ == "__main__":
    data = read_eid_data()
    print("Données extraites de la carte eID :", data)
