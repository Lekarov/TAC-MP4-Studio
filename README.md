# TAC MP4 Studio

<div align="center">

**Générateur de vidéos musicales réactives — local, rapide, sans abonnement.**

Transforme n'importe quel fichier audio en vidéo visualisée frame par frame,  
synchronisée beat par beat, exportée en qualité broadcast.

![Version](https://img.shields.io/badge/version-1.8.0-7c3aed?style=flat-square)
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
                         FFmpeg ──► MP4  (NVENC GPU · libx264 CPU)
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
| `📂 Image perso` | **Nouvelle** — image de fond indépendante de la pochette, avec flou et luminosité |

### Export

| Mode | Résolution | Durée | Usage |
|---|---|---|---|
| **CHECK** | 1920 × 1080 | 15 s | Vérification rapide |
| **SHORT** | 1080 × 1920 | ~1 min (centre audio) | Reel · Story · Short |
| **COMPLET** | 1920 × 1080 | Fichier entier | Publication finale |

- Encodage **GPU automatique** (NVIDIA NVENC) si disponible, sinon CPU libx264
- Preview **live 30 fps** dans l'éditeur avant export
- Historique des exports avec miniatures

### Presets intégrés

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
| Purple Dream | Cercle radial | Vinyle · Violet |
| Midnight Vinyl | Symétrie miroir | Vinyle · Bleu nuit |
| Neon Tricolor | Barres néon | Rose · Violet · Cyan |
| Sunrise | Symétrie miroir | Orange · Or |

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
git clone https://github.com/ton-repo/tac_mp4_studio
cd tac_mp4_studio
pip install -r requirements.txt
python main.py
```

Ou via le lanceur Windows :

```
double-clic sur TAC.bat
```

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
| ⚡ **Presets** | 12 presets intégrés · favoris · presets utilisateur sauvegardables |
| 📸 **Image** | Taille pochette · Réactivité · Vinyle · Fond (flou · luminosité · dégradé · image perso · oscillation) |
| ✨ **Effets** | Particules · Atmosphère · Couleur atmosphère |
| 📊 **Spectre** | Style · Taille · Position · Couleur mono ou 3 bandes · Flash beats |
| 📝 **Texte** | Artiste · Titre · Sous-titre · Police · Taille · Position · Ombre |
| 🚀 **Export** | Dossier de sortie · Mode · Génération |

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
tac_mp4_studio/
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
    │
    └── ui/
        ├── app.py             App — état · lifecycle · navigation · éditeur
        ├── editor.py          EditorMixin — onglets + callbacks
        ├── pages.py           PagesMixin — accueil · historique · turbo · presets
        ├── preview.py         PreviewMixin — preview live · waveform · audio
        └── widgets.py         Widgets réutilisables
```

### Flux de dépendances

```
App
 ├─ EditorMixin · PagesMixin · PreviewMixin
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
| `FFmpeg` | Encodage MP4 (NVENC / libx264) |

---

## Changelog

### v1.8 — Texte amélioré
- Taille de police ajustable par curseur
- Sous-titre indépendant
- Ombre paramétrable : intensité · couleur · décalage XY

### v1.7 — Fond image personnalisé + robustesse
- **Nouveau mode fond `Image perso`** : image de fond indépendante de la pochette album
- Luminosité du fond par défaut rehaussée (`0.85`)
- Couche d'erreurs centralisée (`errors.py`) avec 8 exceptions métier typées
- Logger rotatif (`logger.py`) — trace complète dans `tac.log`
- Messages d'erreur utilisateur en français via popup, détails techniques loggués
- Callbacks preview protégés contre les `TclError` (widgets détruits)
- Subprocess FFmpeg nettoyés en `try/finally`

### v1.6 — Optimisations performances
- Cache LRU sur `compute_audio_features` — refresh preview instantané si l'audio n'a pas changé
- Cache disque vinyle de base — reconstruction évitée à chaque frame (~12 ms/frame économisés)
- Cache label et sleeve pochette vinyle (~9 ms/frame)
- Précalcul des angles cos/sin spectre (orbe + arc plasma)
- Vectorisation numpy de l'oscilloscope (suppression de 512 `cv2.line` individuels par frame)
- Redimensionnement preview BILINEAR au lieu de LANCZOS (~2.5 ms/tick)
- Cache waveform basse résolution évitant le rechargement librosa

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
