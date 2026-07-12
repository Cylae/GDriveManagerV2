# GDrive Space Manager

*A robust, dependency-minimal desktop application for managing Google Drive space with an emphasis on data safety, reliability, and clean architecture.*

---

## 🇬🇧 English Documentation

### 1. Overview
GDrive Space Manager is a Python 3.11+ desktop application designed for Windows, Linux, and macOS. It utilizes Tkinter for its graphical interface, the Python standard library, Google OAuth 2.0 Authorization Code with PKCE, and the Google Drive API v3.

The core philosophy of this project is to maintain a virtually dependency-free footprint while providing enterprise-grade reliability and strict safety guarantees.

### 2. Architecture
The codebase is fully refactored into a clean, strictly layered architecture:
- **`domain/`**: Core business entities and models.
- **`services/`**: Application logic and orchestrations. Must never import from `ui/`.
- **`storage/`**: Local caching, file system interactions, and secret persistence.
- **`ui/`**: Tkinter-based user interface components. Must only communicate with `services/` via `view_models.py`. Business logic and network I/O are strictly forbidden on the Tkinter UI thread.
- **`utils/`**: Shared utilities (logging, decorators, etc.).

### 3. Technical Features

#### 🛡️ Data Safety & Trash Protection
- **Strict Trash Verification:** Binary Drive files are moved to the Trash *only after* an explicit user confirmation (Yes / Yes to all) and a successful local size and Drive MD5 checksum validation.
- **No Overwriting:** Existing local files are never overwritten; names are automatically disambiguated.
- **Safe Cancellation:** Long-running network operations can be accurately interrupted via a `threading.Event` cancellation token without triggering false trash calls.

#### 🔐 Authentication & Secret Storage
- **Secure Persistence:** OAuth refresh tokens are securely stored using Windows DPAPI or macOS/Linux `keyring` (with encrypted file fallback).
- **No Plaintext Secrets:** Secrets are removed from plaintext configuration files. (Legacy config files are automatically migrated on launch).
- **Security Rule:** Client IDs, secrets, tokens, or credentials are never written to logs, standard output, or the repository.

#### 🌐 HTTP Reliability & Concurrency
- **Advanced Retry Mechanism:** Implements a retry decorator with bounded exponential backoff and jitter. It parses `Retry-After` headers for seamless recovery from 408, 425, 429, and 500+ errors, plus 403 quota-exceeded handling.
- **Download Resumption:** Interrupted binary downloads use `.gdsm.partial` files and HTTP Range headers to resume seamlessly.
- **Thread-safe Event Loop:** UI progress bars and ETA analytics are powered by a thread-safe event loop, avoiding UI freezes during network operations.

#### 📂 Drive Path Resolution & Workspace Export
- **Path Resolution:** Full Drive path resolution for nested folders. Handles orphaned files smoothly, prevents cycle loops via max-depth checks, and seamlessly determines shortcut targets via API `shortcutDetails`.
- **Workspace Documents:** Native Google Workspace documents are export-only. They are exported with appropriate MIME-to-extension mappings (.docx, .xlsx, .pptx, .png, .pdf fallbacks) respecting Google's size limits. They are *never* auto-trashed because a comparable Drive MD5 is unavailable.

#### ⚡ Caching, Logging & Exports
- **Inventory Cache:** A robust local `.cache.json` caching mechanism for Drive API inventories featuring atomic writes, version mismatch tracking, and TTL checking for instant UI loading.
- **Dual Logging:** Combines human-readable `.log` output with structural `.jsonl` data, featuring reliable log rotation based on byte thresholds.
- **Data Exports:** Supports exporting transfer queues, rich text session reports, and CSV item dumps (UTF-8 BOM supported).

### 4. Known Limitations
- Designed as a practical v2.0 desktop baseline, not an enterprise identity product.
- The built-in UI is intentionally conservative and does not claim to be a full visual analytics dashboard.
- Workspace files export formats are limited to CSV functionality inside the application unless extended dependencies are integrated.
- UI elements like progress bars require accurate HTTP `Content-Length` headers; if missing, an indeterminate progress loading may be displayed.
- Shared Drive support requires explicitly enabling it in the API query and adding tests with a real Shared Drive account.

---

### 5. Comprehensive Setup Guide

This guide will walk you through setting up the environment, configuring Google Cloud, and running the application.

#### Step 1: Prerequisites
- **Python 3.11 or higher**: Ensure Python and `pip` are installed on your system.
- **Git**: To clone the repository.

#### Step 2: Google Cloud Platform (GCP) Configuration
To connect to Google Drive, you need to create your own OAuth client credentials.
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (e.g., `GDrive Space Manager`).
3. Navigate to **APIs & Services > Library** and search for **Google Drive API**. Click **Enable**.
4. Navigate to **APIs & Services > OAuth consent screen**.
   - Choose **External** (or Internal if you have a Google Workspace organization).
   - Fill in the required application details (App name, User support email, Developer contact information).
   - Add the scopes required for Google Drive (e.g., `.../auth/drive`).
   - Add your Google account email as a **Test user** if the app is in testing mode.
5. Navigate to **APIs & Services > Credentials**.
   - Click **Create Credentials > OAuth client ID**.
   - Choose **Desktop app** as the Application type.
   - Name it (e.g., `GDSM Desktop Client`) and click **Create**.
6. Copy the **Client ID** (you will not need the Client Secret for this PKCE implementation).

#### Step 3: Local Installation
1. Clone the repository and navigate into the folder.
2. Install the minimal dependencies required (primarily `keyring` for secure token storage, plus dev tools):
   ```bash
   pip install -r requirements.txt
   ```
   *(Note: Add external dependencies only if explicitly justified, tested, and declared in `requirements.txt`.)*

#### Step 4: Running the Application
Run the application using Python:
```bash
python main.py
```
Upon the first launch:
1. Open the **Settings** dialog in the UI.
2. Paste your **Client ID** (obtained in Step 2).
3. The application will prompt you to authenticate via your web browser.

#### Step 5: Developer Quality Gates (Before Committing)
The repository enforces strict quality gates. Before submitting any changes, you **must** ensure a green state by running the following commands:
```bash
# 1. Check for compilation errors
python -m compileall -q .

# 2. Run unit tests
python -m unittest discover -s tests -v

# 3. Code formatting and linting
ruff check .

# 4. Static type checking
mypy gdsm
```
Never silently skip failing tests or tools.

---
---

## 🇫🇷 Documentation en Français

### 1. Aperçu
GDrive Space Manager est une application de bureau Python 3.11+ conçue pour Windows, Linux et macOS. Elle utilise Tkinter pour son interface graphique, la bibliothèque standard Python, le flux d'autorisation Google OAuth 2.0 avec PKCE, et l'API Google Drive v3.

La philosophie de base de ce projet est de maintenir une empreinte quasiment sans dépendance, tout en offrant une fiabilité de niveau entreprise et des garanties de sécurité strictes pour vos données.

### 2. Architecture
Le code source est entièrement refactorisé selon une architecture propre et strictement en couches :
- **`domain/`** : Entités métier et modèles de base.
- **`services/`** : Logique applicative et orchestration. Ne doit jamais importer depuis `ui/`.
- **`storage/`** : Mise en cache locale, interactions avec le système de fichiers et persistance des secrets.
- **`ui/`** : Composants de l'interface utilisateur basés sur Tkinter. Ne doit communiquer avec `services/` que via `view_models.py`. La logique métier et les entrées/sorties réseau sont strictement interdites sur le thread de l'interface graphique.
- **`utils/`** : Utilitaires partagés (journalisation, décorateurs, etc.).

### 3. Fonctionnalités Techniques

#### 🛡️ Sécurité des Données & Protection de la Corbeille
- **Vérification Stricte :** Les fichiers binaires de Drive ne sont déplacés vers la corbeille *qu'après* une confirmation explicite de l'utilisateur (Oui / Oui pour tout) et une validation réussie de la taille locale ainsi que de la somme de contrôle MD5 de Drive.
- **Aucun Écrasement :** Les fichiers locaux existants ne sont jamais écrasés ; les noms sont automatiquement désambiguïsés.
- **Annulation Sécurisée :** Les opérations réseau longues peuvent être interrompues avec précision via un jeton d'annulation `threading.Event`, sans déclencher de faux appels à la corbeille.

#### 🔐 Authentification & Stockage des Secrets
- **Persistance Sécurisée :** Les jetons de rafraîchissement OAuth sont stockés de manière sécurisée en utilisant Windows DPAPI ou `keyring` sur macOS/Linux (avec un fichier chiffré en solution de repli).
- **Pas de Secrets en Texte Clair :** Les secrets sont retirés des fichiers de configuration en texte clair. (Les anciens fichiers de configuration sont migrés automatiquement au lancement).
- **Règle de Sécurité :** Les identifiants clients (Client ID), secrets, jetons ou accréditations ne sont jamais écrits dans les journaux (logs), sur la sortie standard, ou dans le dépôt.

#### 🌐 Fiabilité HTTP & Concurrence
- **Mécanisme de Réessai Avancé :** Implémente un décorateur de réessai avec un délai d'attente exponentiel borné et une gigue (jitter). Il analyse les en-têtes `Retry-After` pour une récupération transparente des erreurs 408, 425, 429 et 500+, ainsi que la gestion des dépassements de quota 403.
- **Reprise des Téléchargements :** Les téléchargements binaires interrompus utilisent des fichiers `.gdsm.partial` et les en-têtes HTTP Range pour reprendre de manière transparente.
- **Boucle d'Événements Thread-Safe :** Les barres de progression de l'interface utilisateur et les analyses de temps estimé (ETA) sont alimentées par une boucle d'événements "thread-safe", évitant ainsi le gel de l'interface pendant les opérations réseau.

#### 📂 Résolution des Chemins Drive & Exportation Workspace
- **Résolution de Chemin :** Résolution complète des chemins Drive pour les dossiers imbriqués. Gère les fichiers orphelins en douceur, empêche les boucles infinies via des vérifications de profondeur maximale, et détermine de manière transparente les cibles des raccourcis via `shortcutDetails`.
- **Documents Workspace :** Les documents natifs Google Workspace sont en exportation seule. Ils sont exportés avec des correspondances MIME vers extension appropriées (.docx, .xlsx, .pptx, .png, .pdf en solution de repli) en respectant les limites de taille de Google. Ils ne sont *jamais* mis à la corbeille automatiquement car un MD5 Drive comparable n'est pas disponible.

#### ⚡ Mise en Cache, Journalisation & Exportations
- **Cache d'Inventaire :** Un mécanisme de cache local robuste (`.cache.json`) pour les inventaires de l'API Drive, offrant des écritures atomiques, le suivi des discordances de version, et une vérification du temps de vie (TTL) pour un chargement instantané de l'interface utilisateur.
- **Journalisation Double :** Combine une sortie lisible `.log` avec des données structurelles `.jsonl`, incluant une rotation fiable des journaux basée sur des seuils d'octets.
- **Exportations de Données :** Prend en charge l'exportation des files d'attente de transfert, des rapports de session en texte enrichi, et des vidages d'éléments au format CSV (prise en charge du BOM UTF-8).

### 4. Limites Connues
- Conçu comme une base pratique pour un bureau v2.0, et non comme un produit d'identité d'entreprise.
- L'interface utilisateur intégrée est intentionnellement conservatrice et ne prétend pas être un tableau de bord analytique visuel complet.
- Les formats d'exportation pour les fichiers Workspace sont limités à la fonctionnalité CSV dans l'application, à moins que des dépendances étendues ne soient intégrées.
- Les éléments de l'interface utilisateur tels que les barres de progression nécessitent des en-têtes HTTP `Content-Length` précis ; en leur absence, une progression de chargement indéterminée peut s'afficher.
- La prise en charge des disques partagés (Shared Drives) nécessite de l'activer explicitement dans la requête API et d'ajouter des tests avec un véritable compte de disque partagé.

---

### 5. Guide de Mise en Service Super Complet

Ce guide vous accompagnera pas à pas dans la préparation de l'environnement, la configuration de Google Cloud, et l'exécution de l'application.

#### Étape 1 : Prérequis
- **Python 3.11 ou supérieur** : Assurez-vous que Python et `pip` sont installés sur votre système.
- **Git** : Pour cloner le dépôt.

#### Étape 2 : Configuration de Google Cloud Platform (GCP)
Pour vous connecter à Google Drive, vous devez créer vos propres identifiants client OAuth.
1. Allez sur la [Console Google Cloud](https://console.cloud.google.com/).
2. Créez un nouveau projet (par exemple, `GDrive Space Manager`).
3. Naviguez vers **API et services > Bibliothèque** et recherchez **Google Drive API**. Cliquez sur **Activer**.
4. Naviguez vers **API et services > Écran de consentement OAuth**.
   - Choisissez **Externe** (ou Interne si vous avez une organisation Google Workspace).
   - Remplissez les détails requis de l'application (Nom de l'application, Adresse e-mail d'assistance, Coordonnées du développeur).
   - Ajoutez les portées (scopes) requises pour Google Drive (par exemple, `.../auth/drive`).
   - Ajoutez votre adresse e-mail Google en tant qu'**Utilisateur test** si l'application est en mode test.
5. Naviguez vers **API et services > Identifiants**.
   - Cliquez sur **Créer des identifiants > ID client OAuth**.
   - Choisissez **Application de bureau** comme type d'application.
   - Nommez-la (par exemple, `Client Bureau GDSM`) et cliquez sur **Créer**.
6. Copiez l'**ID client** (Client ID). (Vous n'aurez pas besoin du Code secret du client pour cette implémentation PKCE).

#### Étape 3 : Installation Locale
1. Clonez le dépôt et naviguez dans le dossier.
2. Installez les dépendances minimales requises (principalement `keyring` pour le stockage sécurisé des jetons, plus les outils de développement) :
   ```bash
   pip install -r requirements.txt
   ```
   *(Note : N'ajoutez des dépendances externes que si elles sont explicitement justifiées, testées et déclarées dans `requirements.txt`.)*

#### Étape 4 : Exécution de l'Application
Lancez l'application en utilisant Python :
```bash
python main.py
```
Lors du premier lancement :
1. Ouvrez la boîte de dialogue **Settings** (Paramètres) dans l'interface utilisateur.
2. Collez votre **ID client** (obtenu à l'Étape 2).
3. L'application vous invitera à vous authentifier via votre navigateur web.

#### Étape 5 : Portes de Qualité pour Développeurs (Avant de Commiter)
Le dépôt impose des règles de qualité strictes. Avant de soumettre toute modification, vous **devez** vous assurer que tout est au vert en exécutant les commandes suivantes :
```bash
# 1. Vérification des erreurs de compilation
python -m compileall -q .

# 2. Exécution des tests unitaires
python -m unittest discover -s tests -v

# 3. Formatage du code et linting
ruff check .

# 4. Vérification statique des types
mypy gdsm
```
Ne sautez jamais silencieusement les tests ou les outils en échec.