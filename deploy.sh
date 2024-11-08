#!/bin/bash

# Activer l'environnement virtuel
source ~/divino_pos_project/venv/bin/activate

# Naviguer dans le répertoire du projet
cd ~/divino_pos_project

# Tirer les dernières modifications
git pull origin master  # ou main

# Mettre à jour pip et installer les dépendances
pip install --upgrade pip
pip install -r requirements.txt

# Appliquer les migrations
python manage.py migrate --settings=divino_pos_project.settings.production

# Collecter les fichiers statiques
python manage.py collectstatic --noinput --settings=divino_pos_project.settings.production

# Redémarrer les services
sudo systemctl restart gunicorn
sudo systemctl restart nginx

echo "Déploiement terminé avec succès."
#!/bin/bash

# Activer l'environnement virtuel
source ~/divino_pos_project/venv/bin/activate

# Naviguer dans le répertoire du projet
cd ~/divino_pos_project

# Tirer les dernières modifications
git pull origin master  # ou main

# Mettre à jour pip et installer les dépendances
pip install --upgrade pip
pip install -r requirements.txt

# Appliquer les migrations
python manage.py migrate --settings=divino_pos_project.settings.production

# Collecter les fichiers statiques
python manage.py collectstatic --noinput --settings=divino_pos_project.settings.production

# Redémarrer les services
sudo systemctl restart gunicorn
sudo systemctl restart nginx

echo "Déploiement terminé avec succès."
