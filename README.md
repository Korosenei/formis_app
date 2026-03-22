# 🎓 FORMIS — Application de Gestion des Établissements de Formation

> **FORMIS** (**FOR**mation et **MIS**e en œuvre) est une application web complète de gestion des établissements de formation professionnelle, développée par **TUNKA TECH SARL**. Elle centralise et automatise les processus administratifs, pédagogiques et financiers.

---

## 📋 Présentation du projet

Les établissements de formation font face à de nombreux défis : gestion manuelle des inscriptions, suivi pédagogique limité, organisation complexe des cours et examens, et absence de centralisation des paiements. FORMIS répond à ces problématiques en proposant une solution numérique intégrée.

### Fonctionnalités principales

- 👤 **Gestion des utilisateurs** — Création et administration des comptes Administrateurs, Enseignants et Apprenants
- 📚 **Gestion des formations & cours** — Organisation des formations, modules, cours et supports pédagogiques (PDF, vidéos)
- 📝 **Évaluations & examens** — Création d'évaluations, gestion des plannings et des résultats d'examens
- 💳 **Paiements en ligne** — Intégration de **Ligdicash** pour les frais de formation, avec génération automatique de reçus
- 📋 **Gestion des inscriptions** — Inscriptions administratives et pédagogiques avec validation par l'administration
- 🎥 **Streaming & vidéos** — Accès aux cours en direct et en différé via stockage cloud (AWS S3 / Vimeo / YouTube API)
- 📊 **Suivi pédagogique** — Suivi des performances, des présences et des notes des apprenants

---

## 🛠️ Stack technique

| Composant | Technologie |
|---|---|
| Framework | Python / Django (Full Stack) |
| Frontend | Django Templates + HTML / CSS / JS |
| Base de données | PostgreSQL |
| ORM | Django ORM |
| Authentification | JWT (via `djangorestframework-simplejwt`) |
| Paiement | Ligdicash API |
| Stockage vidéo | AWS S3 / Vimeo / YouTube API |
| Notifications | Email (SMTP Django) |
| Versioning | Git / GitHub |

---

## 🚀 Installation & Setup

### Prérequis

- Python **3.10+**
- PostgreSQL **14+**
- `pip` et `virtualenv`
- Git

### 1. Cloner le dépôt

```bash
git clone https://github.com/<votre-username>/formis.git
cd formis
```

### 2. Créer et activer l'environnement virtuel

```bash
python -m venv venv

# Sur Linux / macOS
source venv/bin/activate

# Sur Windows
venv\Scripts\activate
```

### 3. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 4. Configurer les variables d'environnement

Créez un fichier `.env` à la racine en vous basant sur `.env.example` :

```env
SECRET_KEY=your_django_secret_key
DEBUG=True

# Base de données
DB_NAME=formis_db
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=localhost
DB_PORT=5432

# Email
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_HOST_USER=your_email@example.com
EMAIL_HOST_PASSWORD=your_email_password
EMAIL_USE_TLS=True

# Paiement Ligdicash
LIGDICASH_API_KEY=your_ligdicash_api_key
LIGDICASH_BASE_URL=https://api.ligdicash.com

# Stockage vidéo (AWS S3 - optionnel)
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
AWS_STORAGE_BUCKET_NAME=your_bucket_name
AWS_S3_REGION_NAME=your_region
```

### 5. Créer la base de données PostgreSQL

```bash
psql -U postgres
CREATE DATABASE formis_db;
\q
```

### 6. Appliquer les migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 7. Créer un compte administrateur

```bash
python manage.py createsuperuser
```

### 8. Lancer le serveur de développement

```bash
python manage.py runserver
```

L'application est accessible sur : [http://127.0.0.1:8000](http://127.0.0.1:8000)

---

## 🏗️ Architecture & Structure du projet

```
formis/
│
├── config/                      # Configuration principale Django
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
│
├── users/                       # Gestion des utilisateurs et rôles
│   ├── models.py                # Administrateur, Enseignant, Apprenant
│   ├── views.py
│   ├── forms.py
│   └── urls.py
│
├── formations/                  # Formations, modules et cours
│   ├── models.py                # Formation, Module, Cours
│   ├── views.py
│   ├── forms.py
│   └── urls.py
│
├── evaluations/                 # Évaluations et examens
│   ├── models.py                # Evaluation, Examen, Note
│   ├── views.py
│   └── urls.py
│
├── inscriptions/                # Inscriptions administratives et pédagogiques
│   ├── models.py                # InscriptionAdmin, InscriptionPedagogique
│   ├── views.py
│   └── urls.py
│
├── paiements/                   # Gestion des paiements et reçus
│   ├── models.py                # Transaction, Reçu
│   ├── ligdicash.py             # Intégration API Ligdicash
│   ├── views.py
│   └── urls.py
│
├── videos/                      # Stockage et diffusion des cours vidéo
│   ├── models.py
│   ├── storage.py               # Intégration AWS S3 / Vimeo
│   └── views.py
│
├── notifications/               # Envoi d'emails et alertes
│   ├── tasks.py
│   └── utils.py
│
├── templates/                   # Templates Django (HTML)
│   ├── base.html
│   ├── users/
│   ├── formations/
│   ├── evaluations/
│   ├── inscriptions/
│   └── paiements/
│
├── static/                      # Fichiers statiques (CSS, JS, images)
│
├── .env.example
├── manage.py
└── requirements.txt
```

### Rôles et responsabilités

| Rôle | Description |
|---|---|
| `Administrateur` | Gestion globale de la plateforme : établissements, utilisateurs, formations, inscriptions, paiements |
| `Enseignant` | Création et gestion des cours, dépôt de supports, correction des exercices et attribution des notes |
| `Apprenant` | Consultation des cours, réalisation des exercices, paiement et suivi de ses performances |

### Cas d'utilisation clés

| Code | Fonctionnalité | Acteur |
|---|---|---|
| CU04 | Authentification (email / mot de passe) | Tous |
| CU06 | Ajouter une formation | Administrateur |
| CU09 | Créer et gérer un cours | Enseignant |
| CU12 | Créer des évaluations | Enseignant |
| CU14 | Payer une formation via Ligdicash | Apprenant |
| CU17 | Inscription administrative | Apprenant |
| CU18 | Valider / rejeter une inscription | Administrateur |
| CU19 | Inscription pédagogique | Apprenant / Enseignant |
| CU21 | Accès aux cours vidéo en ligne | Tous |

---

## 📄 Licence

Ce projet est développé et maintenu par **TUNKA TECH SARL** — Burkina Faso.
Tous droits réservés.

---

> Développé avec ❤️ par TUNKA TECH SARL — Burkina Faso 🇧🇫