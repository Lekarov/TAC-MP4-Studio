# TAC MP4 Studio

<div align="center">

**Générateur de vidéos musicales réactives — local, rapide, sans abonnement.**

Transforme n'importe quel fichier audio en vidéo visualisée frame par frame,  
synchronisée beat par beat, exportée en qualité broadcast.

![Version](https://img.shields.io/badge/version-1.11.0-7c3aed?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)
![OpenCV](https://img.shields.io/badge/OpenCV-4.8+-5C3EE8?style=flat-square&logo=opencv&logoColor=white)
![CustomTkinter](https://img.shields.io/badge/UI-CustomTkinter-1F6AA5?style=flat-square)
![FFmpeg](https://img.shields.io/badge/Export-FFmpeg-007808?style=flat-square&logo=ffmpeg&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-0078D4?style=flat-square&logo=windows&logoColor=white)

</div>

---

## Pipeline

```
Audio ──► Analyse librosa ──► Features (bass / kick / rms / spec / raw)
                                        │
                               Rendu OpenCV + PIL  30 fps
                   ┌────────────────────┼────────────────────┐
                   │        Spectre     │     Atmosphère      │
                   │        Pochette    │     Particules      │
                   │        Texte       │     Vinyle          │
                   │        Fond        │     Glow / Vignette │
                   └────────────────────┴────────────────────┘
                                        │
                         FFmpeg ──► MP4  (NVENC GPU · libx264 CPU · encodage 1 passe)
```

---

## Fonctionnalités

### Visuels

| Composant | Détail |
|---|---|
| **10 styles de spectre** | Barres premium · Barres néon · Symétrie miroir · Cercle radial · Arc plasma · Onde plasma · Waveform miroir · Oscilloscope · Ligne fine · Cercle + barres |
| **Spectre tricolor** | 3 bandes indépendantes (bass · mid · high) avec flash réactif aux kicks |
| **7 effets atmosphère** | Aucune · Légère · Cinématique · Dense · Voiles · Lueur ambiante · Traces plasma |
| **Particules** | 5 presets · cycle de vie · fade in/out · drift organique · bloom two-pass |
| **Disque vinyle** | Rotatif · réactif aux beats · pochette image ou noir classique |
| **Fond** | Photo floue · Dégradé · **Image perso** · Fond flottant · Micro-oscillation |
| **Texte** | Artiste + Titre + Sous-titre · 12+ polices · taille · position XY · ombre paramétrable |

### Fond — 3 modes

| Mode | Comportement |
|---|---|
| `📷 Photo floue` | La pochette album est utilisée comme fond, floutée et assombrie |
| `🌈 Dégradé` | Fond uni deux couleurs, personnalisable via color pickers |
| `📂 Image perso` | Image de fond indépendante de la pochette, avec flou et luminosité |

### Export — 4 modes

| Mode | Résolution | Durée | Usage |
|---|---|---|---|
| **SHORT** | 1080 × 1920 | ~1 min (centre audio) | Reel · Story · Short |
| **VERTICAL** | 1080 × 1920 | Fichier entier | Vertical complet |
| **COMPLET** | 1920 × 1080 | Fichier entier | Publication finale |
| **DUAL** | 1920×1080 + 1080×1920 | Complet + ~1 min | Les deux en un seul export |

- Encodage **GPU automatique** (NVIDIA NVENC) si disponible, sinon CPU libx264
- Preview **live 30 fps** dans l'éditeur avant export
- Historique des exports avec miniatures

### Bibliothèque de presets

| Preset | Style | Ambiance |
|---|---|---|
| Dark Premium | Cercle radial | Cinématique sombre |
| Clean White | Barres premium | Épuré lumineux |
| Neon Club | Barres néon | Club · Énergie |
| Reggae Smoke | Arc plasma tricolor | Rouge · Jaune · Vert |
| Chill Lo-Fi | Onde plasma | Doux · Relaxant |
| Short Vertical | Symétrie miroir | Format 9:16 |
| Vinyl Classic | Barres premium | Vinyle noir · Dégradé |
| Vinyl Gold | Cercle + barres | Vinyle doré · Flottant |
| Acid Wave | Oscilloscope | Vert néon · Dégradé |
| Purple Dream | Cercle radial | Vinyle · Violet |
| Midnight Vinyl | Symétrie miroir | Vinyle · Bleu nuit |
| Neon Tricolor | Barres néon | Rose · Violet · Cyan |
| Sunrise | Symétrie miroir | Orange · Or |

Les presets intégrés sont **cachables individuellement** et restaurables en un clic.  
Les presets personnels sont sauvegardables, étoilables (★) et supprimables.

---

## Publication YouTube

Depuis l'accueil, bouton **📺 Publier sur YouTube** — trois entrées :

| Entrée | Usage |
|---|---|
| 🎬 **Upload manuel** | Sélectionne un fichier vidéo précis à publier |
| 📁 **Upload dossier** | Scanne un dossier ; seules les vidéos jamais publiées (anti-doublon nom + taille) sont proposées |
| 📚 **Mes vidéos** | Parcourt playlists et vidéos déjà en ligne (filtrable par visibilité), édition titre/description/tags/visibilité, et réorganisation du planning |

### Upload programmé
- File d'attente éditable : titre (pré-rempli depuis le nom de fichier), tags, description (fenêtre dédiée), date de publication
- **Dates automatiques J+1** : une date de départ est choisie, chaque vidéo suivante de la file prend +1 jour ; la session suivante repart du lendemain de la dernière vidéo réellement publiée (mémorisé dans la config)
- **Profils** (👤) : nom + tags par défaut + description par défaut, réutilisables en un clic sur toute la file

### Bibliothèque (📚 Mes vidéos)
- Menu playlists à gauche (dont « Toutes les vidéos »), liste de vidéos à droite avec miniature, badge de statut (🌍 Publique · 🔗 Non répertoriée · 🔒 Privée · ⏰ Programmée + date), aperçu des tags
- Filtre par statut de visibilité
- Édition complète par vidéo (titre, tags, description, visibilité, date de programmation) écrite directement sur YouTube

### 🔀 Réorganiser (diversifier)
Ré-planifie toutes les vidéos privées programmées à venir pour éviter d'enchaîner plusieurs vidéos de la même playlist quand d'autres sont disponibles :
1. Regroupe les vidéos programmées par playlist d'appartenance (les vidéos hors playlist forment un groupe « Sans playlist »)
2. Calcule un nouvel ordre par algorithme glouton (type *Reorganize String*) — n'impose une répétition consécutive que si elle est mathématiquement inévitable (une playlist trop dominante)
3. Réassigne les dates en conservant exactement le même pool de jours déjà programmés (aucune vidéo n'est avancée/retardée dans le temps) et l'heure d'origine de chaque vidéo
4. Affiche un **aperçu** (ancienne date → nouvelle date, playlist, titre) avant tout envoi — rien n'est appliqué sans validation

### Authentification
OAuth2 Google via **Device Authorization Grant** (comme autoriser une app sur une smart TV) — pas de serveur web local requis. L'écran d'autorisation affiche un lien et un code copiables individuellement (📋). Le refresh token ne périme jamais ; toute réponse 401/403 de l'API (scope insuffisant, token révoqué) déclenche automatiquement une proposition de ré-autorisation.

**⚠️ Aucun identifiant n'est fourni avec ce dépôt** — chacun doit créer son propre client OAuth Google (gratuit, ~5 minutes) :

<details>
<summary><b>Créer ses identifiants OAuth YouTube (étapes)</b></summary>

1. Aller sur [console.cloud.google.com](https://console.cloud.google.com/), créer un nouveau projet
2. **APIs et services → Bibliothèque** → chercher *YouTube Data API v3* → l'activer
3. **APIs et services → Écran de consentement OAuth** → type *Externe* → renseigner un nom d'app, se rajouter soi-même comme *utilisateur test* (pas besoin de publier l'app)
4. **APIs et services → Identifiants → Créer des identifiants → ID client OAuth**
   - Type d'application : **TV et appareils à entrée limitée** (indispensable pour le Device Flow utilisé ici — pas "Application de bureau")
5. Récupérer le **ID client** et le **code secret du client** affichés
6. Lancer TAC MP4 Studio une première fois pour qu'il crée `%APPDATA%\DoktorP3st\TAC_MP4\config.json`, puis y ajouter ces deux clés :
   ```json
   "youtube_oauth_client_id": "VOTRE_ID_CLIENT.apps.googleusercontent.com",
   "youtube_oauth_client_secret": "VOTRE_CODE_SECRET"
   ```
7. Dans l'app : **📺 Publier sur YouTube → Autoriser** → ouvrir le lien affiché, entrer le code, valider avec son compte Google

**Ne jamais commiter ni partager `config.json`** (déjà exclu par `.gitignore`) ni le fichier `youtube_token.json` du même dossier — ce sont vos identifiants et jeton d'accès personnels.

</details>

---

## Démarrage rapide

### Prérequis

- **Windows 10 / 11**
- **Python 3.11+** — [python.org](https://www.python.org/downloads/)
- **FFmpeg** (avec `ffplay`) — [gyan.dev/ffmpeg/builds](https://www.gyan.dev/ffmpeg/builds/)

<details>
<summary><b>Installer FFmpeg (étapes)</b></summary>

1. Télécharger `ffmpeg-release-essentials.zip`
2. Extraire dans `C:\ffmpeg\`
3. Ajouter `C:\ffmpeg\bin` au PATH Windows :
   - `Démarrer` → *Variables d'environnement* → `Path` → Nouveau → `C:\ffmpeg\bin`
4. Vérifier dans un terminal : `ffmpeg -version`

</details>

### Installation

```bash
git clone https://github.com/Lekarov/TAC-MP4-Studio
cd TAC-MP4-Studio
pip install -r requirements.txt
python main.py
```

Ou via le lanceur Windows :

```
double-clic sur TAC.bat
```

`TAC.bat` ne réinstalle les dépendances que si `requirements.txt` a changé depuis le dernier lancement (hash SHA256 comparé à `.requirements.hash`) — pas de `pip install` inutile à chaque démarrage.

---

## Utilisation

```
1.  ✦ NOUVELLE CRÉATION
2.  Importer un fichier audio     MP3 · WAV · FLAC · OGG · M4A · AAC · WMA
3.  Importer une pochette         PNG · JPG · WEBP · BMP
4.  Régler les visuels
5.  🚀 Export → nommer → choisir le mode → GÉNÉRER
```

### Onglets de l'éditeur

| Onglet | Contenu |
|---|---|
| ⚡ **Presets** | Bibliothèque unifiée intégrés + perso · favoris · sauvegarde · suppression |
| 📸 **Image** | Taille pochette · Réactivité · Vinyle · Fond (flou · luminosité · dégradé · image perso · oscillation) |
| ✨ **Effets** | Particules · Atmosphère · Couleur atmosphère |
| 📊 **Spectre** | Style · Taille · Position · Couleur mono ou 3 bandes · Flash beats |
| 📝 **Texte** | Artiste · Titre · Sous-titre · Police · Taille · Position · Ombre |
| 🚀 **Export** | Dossier de sortie · Mode (grille 2×2) · Génération |

### Raccourcis clavier

| Touche | Action |
|---|---|
| `Espace` | Play / Pause preview audio |
| `R` | Recharger la preview |
| `F11` | Preview plein écran |
| `Échap` | Quitter le plein écran |

---

## Architecture

```
TAC-MP4-Studio/
│
├── main.py                    Point d'entrée
├── TAC.bat                    Lanceur Windows
├── requirements.txt
│
├── img/                       Assets (logo, disque vinyle, icône)
├── fonts/                     Polices TTF incluses (Liberation, Carlito, Caladea)
│
└── app/
    ├── audio.py               Analyse audio — librosa · soundfile · scipy
    ├── config.py              Persistance JSON — AppData (écriture atomique)
    ├── errors.py              Exceptions métier — TACError et sous-classes
    ├── exporter.py            Pipeline export — rendu + FFmpeg
    ├── loading.py             Écran de chargement animé
    ├── logger.py              Logging centralisé — fichier rotatif + console
    ├── models.py              RenderSettings (dataclass)
    ├── particles.py           Particules · Fumée · Voiles · Plasma · Lueur
    ├── presets.py             Constantes · Presets visuels · Palettes
    ├── renderer.py            Rendu frame — image · texte · fond · vignette · glow
    ├── spectrum.py            10 styles de spectre + orbe audio
    ├── vinyl.py               Disque vinyle rotatif + pochette
    ├── youtube_auth.py        OAuth2 Google — Device Authorization Grant
    ├── youtube_api.py         Lecture/édition playlists + vidéos (API Data v3, HTTP brut)
    ├── youtube_upload.py      Upload résumable de vidéos (API Data v3, HTTP brut)
    │
    └── ui/
        ├── app.py             App — état · lifecycle · navigation · construction éditeur
        ├── editor.py          EditorMixin — onglets + callbacks + gestion presets
        ├── export_ui.py       ExportMixin — projet · settings courants · export simple/DUAL/test
        ├── pages.py           PagesMixin — accueil · historique · turbo
        ├── preview.py         PreviewMixin — preview live · waveform · audio
        ├── turbo.py           TurboMixin — export par lot (mode Turbo)
        ├── youtube_ui.py      YoutubeMixin — upload programmé · bibliothèque · réorganisation
        └── widgets.py         Widgets réutilisables
```

### Flux de dépendances

```
App
 ├─ EditorMixin · PagesMixin · PreviewMixin · TurboMixin · ExportMixin
 ├─ renderer ──► spectrum · vinyl · particles
 ├─ exporter ──► renderer · audio
 ├─ errors · logger
 └─ config · models · presets
```

---

## Gestion des erreurs

Chaque composant utilise des exceptions métier typées. Les messages utilisateur sont affichés en popup, les détails techniques sont loggués dans :

```
%APPDATA%\DoktorP3st\TAC_MP4\logs\tac.log
```

| Exception | Déclencheur |
|---|---|
| `AudioImportError` | Fichier absent · format invalide · lecture librosa échouée |
| `ImageImportError` | Image absente · corrompue · format non supporté |
| `FFmpegError` | FFmpeg introuvable · crash encodage |
| `ExportError` | Dossier absent · permission refusée · export interrompu |
| `ConfigError` | Config JSON corrompue · écriture impossible |
| `PreviewError` | Crash preview · widget détruit · callback tardif |
| `RenderError` | Dimensions invalides · erreur OpenCV frame |
| `PresetError` | Preset invalide ou incomplet |
| `YoutubeError` | Échec API YouTube (upload, lecture/édition playlists ou vidéos) |
| `YoutubeAuthError` | Réponse 401/403 — jeton absent, expiré ou scope OAuth insuffisant (déclenche une proposition de ré-autorisation) |

---

## Configuration

Sauvegarde automatique dans :

```
%APPDATA%\DoktorP3st\TAC_MP4\config.json
```

Dossier de sortie par défaut (modifiable dans l'app) :

```
%APPDATA%\DoktorP3st\TAC_MP4\Creations\
```

Jeton OAuth YouTube (Device Authorization Grant, ne périme jamais) :

```
%APPDATA%\DoktorP3st\TAC_MP4\youtube_token.json
```

Identifiants du client OAuth (`youtube_oauth_client_id` / `youtube_oauth_client_secret`), historique d'upload anti-doublon (`youtube_history`), profils (`youtube_profiles`) et dernière date programmée (`youtube_last_scheduled_date`) sont stockés dans le `config.json` ci-dessus.

---

## Packaging .exe

```bash
pip install pyinstaller

pyinstaller --onefile --windowed --name "TAC_MP4_Studio" ^
  --add-data "img;img" ^
  --add-data "fonts;fonts" ^
  --collect-data customtkinter ^
  --collect-data tkinterdnd2 ^
  --icon "img/icone.ico" ^
  main.py
```

Le `.exe` se trouve dans `dist/TAC_MP4_Studio.exe`.  
FFmpeg doit être installé séparément sur la machine cible.

---

## Stack technique

| Lib | Rôle |
|---|---|
| `numpy` | Calcul vectorisé — audio et rendu |
| `opencv-python` | Pipeline vidéo frame par frame |
| `Pillow` | Traitement image · texte · polices |
| `librosa` | Analyse audio (STFT · onset · RMS) |
| `soundfile` | Chargement WAV/FLAC/OGG (fast path) |
| `scipy` | Resampling audio · interpolation |
| `customtkinter` | Interface dark theme moderne |
| `tkinterdnd2` | Drag & drop fichiers (optionnel) |
| `requests` | Appels API YouTube (OAuth, upload résumable, lecture/édition) |
| `FFmpeg` | Encodage MP4 (NVENC / libx264) |

---

## Changelog

### v1.11.0 — Publication YouTube (upload, bibliothèque, réorganisation)
- **Upload programmé** vers YouTube depuis l'accueil : upload manuel (fichier) ou upload dossier (scan + anti-doublon nom+taille), file d'attente éditable (titre · tags · description · date), dates automatiques J+1, profils réutilisables (tags + description par défaut)
- **Bibliothèque (📚 Mes vidéos)** : parcours des playlists et vidéos déjà en ligne, filtre par visibilité (publique · non répertoriée · privée · programmée), édition complète (titre/description/tags/visibilité/date) écrite directement sur YouTube
- **🔀 Réorganiser (diversifier)** : ré-planifie les vidéos privées programmées à venir pour éviter d'enchaîner plusieurs vidéos de la même playlist (algorithme glouton type *Reorganize String*), sans changer le pool de dates déjà utilisées ; aperçu obligatoire avant application
- Authentification OAuth2 Google par **Device Authorization Grant** (lien + code copiables individuellement), scope complet `youtube`, ré-autorisation automatique proposée sur toute réponse 401/403
- `TAC.bat` : mise à jour des dépendances (`pip install`) uniquement si `requirements.txt` a changé (hash SHA256), plus de réinstallation à chaque lancement

### v1.10.0 — Turbo V2 + conversion Short depuis l'historique
- **Turbo V2** : nouveau mode d'export en série à partir d'un dossier. Les musiques et pochettes de même nom de fichier sont appariées automatiquement (`Titre.mp3` + `Titre.png`), avec une image de fond commune optionnelle et un aperçu aléatoire.
- Les vidéos Turbo V2 sont exportées directement dans le dossier source, nommées comme l'audio d'origine (pas de sous-dossier, pas de copie de la pochette) ; rendu écrit dans un dossier temporaire puis déplacé en une opération atomique pour ne jamais laisser de fichier partiel.
- Historique persistant : les paires déjà rendues (empreinte taille + date de modif) sont mémorisées entre deux lancements de l'appli et ne sont pas ré-exportées ; un bouton 🔁 permet de rescanner le dossier.
- Sécurités : vérification d'écriture du dossier, estimation d'espace disque libre, détection des noms ambigus (deux audios/images de même nom), anti-collision de nom de sortie, limite de longueur de chemin Windows.
- Écran de choix au clic sur ⚡ TURBO : Interface originale ou Turbo V2.
- Historique : bouton « 🎬 Convertir en Short » pour régénérer une création existante au format 1 min · 9:16 avec exactement les mêmes réglages visuels.

### v1.9.1 — Export en une passe + perf + maintenabilité
- **Export vidéo en une seule passe** : les frames sont pipées directement vers FFmpeg (`stdin` rawvideo) au lieu de passer par un fichier temporaire `cv2.VideoWriter` (mp4v) ré-encodé ensuite. Plus rapide, et supprime une perte de qualité intermédiaire.
- Erreurs FFmpeg lues depuis un fichier log dédié (au lieu d'un pipe stderr non lu, qui pouvait bloquer)
- Waveform de la preview : le curseur de lecture se déplace sans redessiner toutes les barres (`_update_waveform_cursor`), au lieu d'un redraw complet 5x/seconde
- `app/ui/app.py` découpé : extraction de `TurboMixin` (`turbo.py`) et `ExportMixin` (`export_ui.py`) — 2237 → ~1460 lignes
- Exceptions silencieuses de `audio.py`/`exporter.py` désormais tracées (niveau debug) dans `tac.log`
- Bornes de version ajoutées dans `requirements.txt`
- **Correctif** : la preview restait noire (pochette et effets absents, seul le spectre s'affichait) — imports partagés (`PREVIEW_W`, `FPS`, `RenderSettings`...) supprimés par erreur lors du découpage de `app.py`, restaurés

### v1.9 — Bibliothèque de presets unifiée + export cards
- Onglet ⚡ refactorisé : bibliothèque unifiée intégrés + perso dans une seule liste
- Presets intégrés cachables individuellement (✕) et restaurables en un clic
- Badge **intégré** / **perso** · bande couleur · favoris (★) remontent en tête
- Modes d'export redessinés en **grille 2×2** : icône + résolution + badge durée
- Sélection d'export colorée par mode (chaque mode a sa propre couleur de bordure)

### v1.8 — Texte amélioré
- Taille de police ajustable par curseur
- Sous-titre indépendant
- Ombre paramétrable : intensité · couleur · décalage XY

### v1.7 — Fond image personnalisé + robustesse
- Nouveau mode fond `Image perso` : image de fond indépendante de la pochette album
- Couche d'erreurs centralisée (`errors.py`) avec 8 exceptions métier typées
- Logger rotatif (`logger.py`) — trace complète dans `tac.log`

### v1.6 — Optimisations performances
- Cache LRU sur `compute_audio_features` — refresh preview instantané
- Cache disque vinyle (~12 ms/frame économisés)
- Vectorisation numpy de l'oscilloscope
- Redimensionnement preview BILINEAR (~2.5 ms/tick)

### v1.5 — Spectre tricolor + réactivité beats
- 3 couleurs indépendantes par bande (bass · mid · high)
- Flash couleur synchronisé sur les kicks

### v1.4 — Disque vinyle
- Vinyle rotatif réactif aux beats
- Choix image pochette ou noir classique

### v1.3 — Fond dégradé + historique
- Fond dégradé avec color pickers
- Historique des exports avec miniatures
- Mode plein écran preview

---

<div align="center">

Développé par **DoktorP3st**

</div>
