// static/divino_pos/js/eid_reader.js

function readEIDCard() {
    // Vérifier que le Middleware eID est installé
    if (typeof window.eID === 'undefined') {
        alert('Le Middleware eID n\'est pas installé ou n\'est pas activé dans votre navigateur.');
        console.error('Middleware eID non détecté. Assurez-vous que l\'extension est bien installée et activée.');
        return;
    }

    // Fonction pour lire les données de la carte
    window.eID.readIdentity(function(success, data) {
        if (success) {
            console.log('Données eID lues avec succès :', data);

            // Envoyer les données au serveur pour les traiter
            fetch('/read_eid/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken'),
                },
                body: JSON.stringify(data),
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Erreur réseau ou problème avec la réponse du serveur.');
                }
                return response.json();
            })
            .then(result => {
                if (result.success) {
                    console.log('Données traitées avec succès sur le serveur:', result);
                    // Pré-remplir les champs du formulaire avec les données reçues
                    document.getElementById('id_nom').value = result.nom || '';
                    document.getElementById('id_prenom').value = result.prenom || '';
                    document.getElementById('id_date_anniversaire').value = result.date_naissance || '';
                    document.getElementById('id_numero_rue').value = result.adresse || '';
                    document.getElementById('id_code_postal').value = result.code_postal || '';
                    document.getElementById('id_ville').value = result.ville || '';
                    document.getElementById('id_pays').value = result.pays || 'Belgique';
                    document.getElementById('id_n_carte').value = result.n_carte || '';
                } else {
                    console.error('Erreur côté serveur :', result.error || 'Aucune erreur spécifique retournée.');
                    alert('Erreur lors de la lecture des données de la carte eID sur le serveur.');
                }
            })
            .catch(error => {
                console.error('Erreur lors de la communication avec le serveur :', error);
                alert('Une erreur est survenue lors de la communication avec le serveur.');
            });
        } else {
            console.error('Échec de la lecture de la carte eID :', data.error || 'Erreur non spécifiée.');
            alert('Impossible de lire la carte eID. Veuillez vérifier la carte et réessayer.');
        }
    });
}

// Fonction pour obtenir le cookie CSRF
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        let cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            let cookie = cookies[i].trim();
            // Vérifier que ce cookie commence par le nom recherché
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Ajouter un événement de chargement pour vérifier la disponibilité de eID dès le démarrage
document.addEventListener('DOMContentLoaded', () => {
    if (typeof window.eID === 'undefined') {
        console.warn('Middleware eID non détecté au chargement de la page.');
    } else {
        console.log('Middleware eID détecté.');
    }
});
