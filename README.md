# ✂️ Auto Shorts

Ton application perso pour transformer une longue vidéo YouTube en **5 à 15 shorts verticaux**, prêts à publier sur **TikTok** et **YouTube Shorts**.

Tu colles un lien, et l'application :

1. **télécharge** la vidéo ;
2. **écrit tout ce qui est dit** (transcription automatique, sur ton ordinateur) ;
3. demande à une **IA** de trouver les meilleurs moments (de 15 à 60 secondes) ;
4. **recadre en vertical 9:16** en suivant le visage de la personne qui parle ;
5. ajoute des **sous-titres animés mot par mot** (le mot prononcé s'allume en jaune) ;
6. te propose un **titre, une description et des hashtags** pour chaque short ;
7. te laisse **regarder, corriger, puis publier** en un clic sur TikTok et YouTube.

> ⚖️ **Important :** utilise uniquement des vidéos dont tu as les droits (tes propres vidéos, ou avec l'accord de l'auteur). Republier le contenu de quelqu'un d'autre peut faire supprimer tes vidéos ou bloquer ton compte.

L'application tourne **sur ton ordinateur** (gratuit, rien à héberger). Elle s'ouvre dans ton navigateur à l'adresse http://localhost:8000.

---

## 📋 Sommaire

- [1. Installer (une seule fois)](#1-installer-une-seule-fois)
- [2. Lancer l'application](#2-lancer-lapplication)
- [3. Ajouter la clé de l'IA](#3-ajouter-la-clé-de-lia-recommandé)
- [4. Brancher YouTube](#4-brancher-youtube-shorts)
- [5. Brancher TikTok](#5-brancher-tiktok)
- [6. Utiliser l'application](#6-utiliser-lapplication)
- [7. Problèmes fréquents](#7-problèmes-fréquents)

---

## 1. Installer (une seule fois)

### a) Installer Python

1. Va sur https://www.python.org/downloads/ et télécharge **Python 3.12**.
2. Lance l'installation.
   - **Sur Windows : coche absolument la case « Add python.exe to PATH »** en bas de la première fenêtre, puis clique sur « Install Now ».
   - Sur Mac : clique sur « Continuer » jusqu'au bout.

### b) Installer Deno (aide à télécharger depuis YouTube)

YouTube change souvent ses protections ; le petit programme Deno permet au téléchargeur de suivre.

- **Windows** : ouvre le menu Démarrer, tape `PowerShell`, ouvre-le et colle :
  ```
  winget install DenoLand.Deno
  ```
- **Mac** : ouvre l'application **Terminal** et colle :
  ```
  curl -fsSL https://deno.land/install.sh | sh
  ```

### c) Récupérer l'application

1. Sur la page GitHub du projet, clique sur le bouton vert **« Code »** puis **« Download ZIP »**.
2. Décompresse le fichier ZIP (clic droit → « Extraire tout » sur Windows, double-clic sur Mac).
3. Range le dossier `auto-shorts` où tu veux (par exemple dans « Documents »).

---

## 2. Lancer l'application

- **Windows** : double-clique sur **`lancer-windows.bat`**.
  Si Windows affiche « Windows a protégé votre ordinateur », clique sur « Informations complémentaires » puis « Exécuter quand même ».
- **Mac** : fais un **clic droit** sur **`lancer-mac.command`** → **Ouvrir** → **Ouvrir**.
  (Si ça ne marche pas : ouvre le Terminal, tape `bash ` avec un espace, glisse le fichier dans la fenêtre, puis appuie sur Entrée.)

La **première fois**, l'installation prend 5 à 10 minutes (une fenêtre noire affiche des lignes, c'est normal). Ensuite, ton navigateur s'ouvre tout seul sur **http://localhost:8000**.

⚠️ **Laisse la fenêtre noire ouverte** tant que tu utilises l'application. Pour arrêter, ferme-la.

> La première vidéo est un peu plus longue : l'outil de transcription télécharge son « cerveau » (environ 500 Mo) une seule fois.

---

## 3. Ajouter la clé de l'IA (recommandé)

Sans clé, l'application marche quand même, mais choisit les moments « au hasard intelligent » et écrit des titres très basiques. Avec la clé, c'est l'IA Claude qui repère les vrais moments forts et rédige titres, descriptions et hashtags.

1. Va sur https://console.anthropic.com et crée un compte.
2. Dans **« Billing »**, ajoute quelques euros de crédit (5 € suffisent pour commencer : une vidéo d'une heure coûte environ quelques dizaines de centimes).
3. Va dans **« API Keys »** → **« Create Key »** → copie la clé (elle commence par `sk-ant-`).
4. Dans le dossier `auto-shorts`, ouvre le fichier **`.env`** avec le Bloc-notes (Windows) ou TextEdit (Mac).
   - Le fichier `.env` est créé au premier lancement. Si tu ne le vois pas, c'est un fichier « caché » : sur Mac, appuie sur `Cmd + Maj + .` dans le Finder pour l'afficher.
5. Colle ta clé après `ANTHROPIC_API_KEY=` :
   ```
   ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxx
   ```
6. Enregistre, ferme la fenêtre noire et relance l'application.

---

## 4. Brancher YouTube Shorts

Pour publier directement, YouTube demande que tu crées une « application » gratuite chez Google. Ça prend environ 15 minutes, une seule fois.

1. Va sur https://console.cloud.google.com et connecte-toi avec le compte Google de ta chaîne.
2. En haut, clique sur le sélecteur de projet → **« Nouveau projet »** → nom : `auto-shorts` → **Créer**.
3. Dans la barre de recherche en haut, tape **« YouTube Data API v3 »**, ouvre-la et clique sur **« Activer »**.
4. Menu ☰ → **« API et services »** → **« Écran de consentement OAuth »** (ou « Google Auth Platform ») :
   - Type d'utilisateur : **Externe** → Créer.
   - Nom de l'application : `Auto Shorts`, ton adresse e-mail dans les deux champs demandés → Enregistrer et continuer jusqu'au bout.
   - Dans **« Audience »** / **« Utilisateurs test »**, clique sur **« Ajouter des utilisateurs »** et mets **ton adresse Gmail**.
5. Menu → **« API et services »** → **« Identifiants »** → **« Créer des identifiants »** → **« ID client OAuth »** :
   - Type d'application : **Application Web**.
   - Dans **« URI de redirection autorisés »**, clique sur « Ajouter un URI » et colle exactement :
     ```
     http://localhost:8000/auth/youtube/callback
     ```
   - Clique sur **Créer**, puis sur **« Télécharger le JSON »**.
6. Renomme le fichier téléchargé en **`client_secret.json`** et mets-le dans le dossier `auto-shorts` (à côté de `lancer-windows.bat`).
7. Relance l'application, clique sur **« YouTube : connecter »** en haut à droite et accepte.
   Google affichera « Google n'a pas validé cette application » : c'est normal, c'est **ta** application. Clique sur « Continuer ».

**Ce qu'il faut savoir :**
- Tant que ton application Google n'est pas « vérifiée » par YouTube, **les vidéos publiées par l'API restent en privé**. Tu peux les regarder dans YouTube Studio. Pour publier en public directement, il faut demander un audit gratuit à YouTube via ce formulaire : https://support.google.com/youtube/contact/yt_api_form (ça peut prendre quelques semaines).
- En mode « Test », Google te déconnecte tous les 7 jours : il suffit de recliquer sur « connecter ».
- YouTube limite à environ **6 publications par jour** via l'API (quota gratuit).

---

## 5. Brancher TikTok

TikTok demande aussi une « application développeur » gratuite.

1. Va sur https://developers.tiktok.com et connecte-toi (avec ton compte TikTok ou une adresse e-mail).
2. En haut à droite : **« Manage apps »** → **« Connect an app »** → donne un nom (`Auto Shorts`) → **Confirm**.
3. Dans la page de l'application :
   - **Platforms** : coche **Desktop**.
   - **Products** → **« Add products »** : ajoute **Login Kit** et **Content Posting API**.
   - Dans **Content Posting API**, active **« Direct Post »**.
   - **Scopes** : vérifie que `user.info.basic` et `video.publish` sont cochés.
   - Dans **Login Kit**, ajoute ce **Redirect URI** (exactement, avec le `/` à la fin) :
     ```
     http://localhost:8000/auth/tiktok/callback/
     ```
4. En haut de la page, passe en **Sandbox** (bac à sable) et, dans **« Target users »**, ajoute **ton compte TikTok**.
5. Copie le **Client key** et le **Client secret** et colle-les dans le fichier `.env` :
   ```
   TIKTOK_CLIENT_KEY=xxxxxxxx
   TIKTOK_CLIENT_SECRET=xxxxxxxx
   ```
6. Relance l'application et clique sur **« TikTok : connecter »**.

**Ce qu'il faut savoir :**
- Tant que TikTok n'a pas validé (« audité ») ton application, **ton compte TikTok doit être en mode privé** pendant la publication, et les vidéos sont publiées en **« Moi uniquement »**. Ensuite, tu peux les passer en public depuis l'application TikTok, sur ton téléphone.
- Pour publier en public directement, il faut soumettre l'application à TikTok (bouton **« Submit for review »**). TikTok demande alors une vidéo de démonstration et peut refuser les outils d'usage purement personnel.
- TikTok limite à quelques publications par jour via l'API.

---

## 6. Utiliser l'application

1. Colle le lien de la vidéo YouTube (ou choisis un fichier vidéo de ton ordinateur avec l'onglet « Fichier »).
2. Choisis le nombre de shorts (5 à 15) et la langue (ou « Détection automatique »).
3. Clique sur **« Créer mes shorts ✨ »**.
4. Patiente : la barre montre où en est le travail. Pour une vidéo de 30 minutes, compte environ 10 à 30 minutes selon ton ordinateur.
5. Pour chaque short :
   - regarde l'aperçu ;
   - corrige le titre, la description ou les hashtags si tu veux, puis **💾 Enregistrer** ;
   - **⬇️ Télécharger** pour garder le fichier ;
   - ou publie directement avec **▶️ YouTube Shorts** et **🎵 TikTok**.

Tous tes projets restent dans la liste « Mes projets » (les fichiers sont dans le dossier `data/`).

---

## 7. Problèmes fréquents

| Problème | Solution |
|---|---|
| La fenêtre noire se ferme tout de suite | Python n'est pas installé ou la case « Add to PATH » n'était pas cochée. Réinstalle Python en cochant la case. |
| « Erreur : … Sign in to confirm you're not a bot » ou échec du téléchargement | Installe Deno (étape 1b), relance l'application (elle met à jour le téléchargeur à chaque lancement). Sinon, télécharge la vidéo toi-même et utilise l'onglet « Fichier ». |
| C'est très lent | Normal sans carte graphique. Mets `WHISPER_MODEL=base` dans `.env` pour aller plus vite (un peu moins précis). |
| Les sous-titres ont des fautes | Indique la langue au lieu de « Détection automatique », ou mets `WHISPER_MODEL=medium` dans `.env`. Tu peux aussi corriger le texte dans la description. |
| Le cadrage ne suit pas bien la personne | Le suivi fonctionne mieux quand le visage est bien visible et de face. |
| « Connecte d'abord ton compte » | Clique sur « connecter » en haut à droite de l'application. |
| YouTube : « redirect_uri_mismatch » | L'adresse de redirection dans Google Cloud doit être exactement `http://localhost:8000/auth/youtube/callback`. |
| TikTok : « unaudited_client_can_only_post_to_private_accounts » | Passe ton compte TikTok en privé (Paramètres → Confidentialité → Compte privé) le temps de publier. |

---

### Pour les curieux (technique)

- Serveur : Python + FastAPI (`app/`), interface : HTML/JS (`static/`).
- Téléchargement : `yt-dlp` · Transcription : `faster-whisper` · IA : API Claude d'Anthropic.
- Recadrage : détection de visages OpenCV + caméra lissée · Montage : `ffmpeg` (fourni automatiquement).
- Publication : YouTube Data API v3 (OAuth Google) et TikTok Content Posting API (OAuth + PKCE).
- Tes clés et connexions restent sur ton ordinateur (`.env`, `client_secret.json`, `data/tokens/`), jamais envoyées sur GitHub.
