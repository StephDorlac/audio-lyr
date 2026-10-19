#!/usr/bin/env python3
"""Extrait les paroles d'un fichier mp3/wav (ou d'un dossier) avec faster-whisper.

morceau.mp3 -> morceau.txt (dans le même dossier).
"""
import argparse
import sys
from pathlib import Path

EXTENSIONS = {".mp3", ".wav"}


def preload_cuda_libs():
    """Rend les libs CUDA installées via pip (nvidia-*-cu12) visibles de CTranslate2."""
    import ctypes
    import importlib.util

    for pkg, lib in (("nvidia.cublas", "libcublas.so.12"), ("nvidia.cudnn", "libcudnn.so.9")):
        try:
            spec = importlib.util.find_spec(pkg)
            if spec and spec.submodule_search_locations:
                path = Path(next(iter(spec.submodule_search_locations))) / "lib" / lib
                if path.exists():
                    ctypes.CDLL(str(path), mode=ctypes.RTLD_GLOBAL)
        except (ImportError, OSError):
            pass


def load_model(name):
    from faster_whisper import WhisperModel

    preload_cuda_libs()
    try:
        return WhisperModel(name, device="cuda", compute_type="float16")
    except Exception as e:
        print(f"GPU indisponible ({e}), repli sur CPU.", file=sys.stderr)
        return WhisperModel(name, device="cpu", compute_type="int8")


def collect(path):
    if path.is_dir():
        return sorted(p for p in path.rglob("*") if p.suffix.lower() in EXTENSIONS)
    return [path]


def lrc_time(seconds):
    """Horodatage LRC [mm:ss.xx]."""
    cs = int(round(seconds * 100))
    return f"{cs // 6000:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def pending(files, force=False, lrc=False):
    """Fichiers audio dont il manque le .txt (ou le .lrc si demandé)."""
    def missing(f):
        return not f.with_suffix(".txt").exists() or (lrc and not f.with_suffix(".lrc").exists())
    return [f for f in files if force or missing(f)]


def transcribe_file(model, audio, out, lang=None, on_progress=None, lrc=False):
    """Transcrit `audio` vers le fichier texte `out` (et `.lrc` synchronisé si `lrc`).

    Retourne la langue détectée.

    Le VAD est désactivé : il prend le chant sur fond de musique pour du non-parlé
    et supprime des couplets entiers. `on_progress(pourcentage)` est appelé au fil des segments.
    """
    segments, info = model.transcribe(
        str(audio),
        language=lang,
        vad_filter=False,
        no_speech_threshold=None,
        condition_on_previous_text=False,
        beam_size=5,
        # Sans amorce, Whisper remplace parfois la 1re fenêtre de 30 s (intro musicale
        # puis chant) par un simple titre halluciné et perd les premières phrases.
        initial_prompt="Song lyrics.",
    )
    lines, lrc_lines = [], []
    for s in segments:
        text = s.text.strip()
        if text:
            lines.append(text)
            lrc_lines.append(f"[{lrc_time(s.start)}]{text}")
        if on_progress and info.duration:
            on_progress(min(100, int(s.end / info.duration * 100)))
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if lrc:
        out.with_suffix(".lrc").write_text("\n".join(lrc_lines) + "\n", encoding="utf-8")
    if on_progress:
        on_progress(100)
    return info.language


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("chemin", type=Path, help="fichier mp3/wav ou dossier")
    ap.add_argument("--model", default="large-v3", help="modèle Whisper (défaut: large-v3)")
    ap.add_argument("--lang", default=None, help="langue forcée, ex. fr (défaut: auto)")
    ap.add_argument("--force", action="store_true", help="réécrit les .txt existants")
    ap.add_argument("--lrc", action="store_true", help="écrit aussi un .lrc synchronisé")
    args = ap.parse_args()

    if not args.chemin.exists():
        sys.exit(f"Introuvable : {args.chemin}")
    files = collect(args.chemin)
    if not files:
        sys.exit("Aucun fichier mp3/wav trouvé.")

    todo = pending(files, args.force, args.lrc)
    for f in files:
        if f not in todo:
            print(f"Ignoré (déjà fait) : {f.name}")
    if not todo:
        return

    model = load_model(args.model)
    for audio in todo:
        out = audio.with_suffix(".txt")
        print(f"Transcription : {audio.name}")
        language = transcribe_file(
            model, audio, out, args.lang, lrc=args.lrc,
            on_progress=lambda p: print(f"\r  {p}%", end="", flush=True),
        )
        print(f"\n  -> {out} (langue: {language})")


if __name__ == "__main__":
    main()
