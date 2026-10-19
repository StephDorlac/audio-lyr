# audio-lyr

Extrait les paroles d'un mp3/wav avec Whisper (faster-whisper) et les enregistre
dans `<nom du morceau>.txt` à côté du fichier audio.

## Installation

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Usage

```bash
.venv/bin/python lyrics.py morceau.mp3          # un fichier
.venv/bin/python lyrics.py ~/Musique --lang fr  # un dossier (récursif)
.venv/bin/python lyrics.py morceau.wav --force  # réécrit le .txt existant
```

Options : `--model` (défaut `large-v3`, ex. `medium` si peu de VRAM), `--lang`, `--force`, `--lrc` (écrit aussi un `.lrc` synchronisé).
Utilise le GPU si disponible, sinon le CPU (plus lent).

## Interface graphique

```bash
.venv/bin/python ui.py
```

Sous Linux, Qt peut nécessiter `sudo apt install libxcb-cursor0`.

## Licence

MIT, voir [LICENSE](LICENSE).
