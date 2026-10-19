#!/usr/bin/env python3
"""Interface graphique pour lyrics.py : choisir des mp3/wav, lancer, voir les paroles."""
import sys
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel, QListWidget,
    QProgressBar, QPushButton, QSplitter, QTextEdit, QVBoxLayout, QWidget,
)

import lyrics

LANGS = [("Auto", None), ("Français", "fr"), ("English", "en"), ("Español", "es"),
         ("Deutsch", "de"), ("Italiano", "it"), ("Português", "pt")]
MODELS = ["large-v3", "medium", "small"]


class Worker(QThread):
    status = pyqtSignal(str)
    done_file = pyqtSignal(str)  # chemin du .txt écrit
    progress = pyqtSignal(int)  # avancement global en %

    def __init__(self, files, model_name, lang, lrc):
        super().__init__()
        self.files, self.model_name, self.lang, self.lrc = files, model_name, lang, lrc

    def run(self):
        try:
            todo = lyrics.pending(self.files, lrc=self.lrc)
            for f in self.files:
                if f not in todo and f.with_suffix(".txt").exists():
                    self.done_file.emit(str(f.with_suffix(".txt")))
            if not todo:
                self.status.emit("Terminé (tout existait déjà).")
                return
            self.status.emit(f"Chargement du modèle {self.model_name}…")
            model = lyrics.load_model(self.model_name)
            for i, audio in enumerate(todo, 1):
                out = audio.with_suffix(".txt")
                self.status.emit(f"[{i}/{len(todo)}] Transcription : {audio.name}")
                base = (i - 1) * 100
                lyrics.transcribe_file(
                    model, audio, out, self.lang, lrc=self.lrc,
                    on_progress=lambda p, base=base: self.progress.emit(
                        (base + p) // len(todo)),
                )
                self.done_file.emit(str(out))
            self.progress.emit(100)
            self.status.emit(f"Terminé : {len(todo)} fichier(s).")
        except Exception as e:
            self.status.emit(f"Erreur : {e}")


class Window(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("audio-lyr")
        self.resize(820, 520)
        self.files = []
        self.worker = None

        self.list = QListWidget()
        self.list.currentItemChanged.connect(self.show_lyrics)
        self.text = QTextEdit()
        self.text.setPlaceholderText("Sélectionnez un morceau transcrit pour voir ses paroles.")
        self.text.setReadOnly(True)
        split = QSplitter()
        split.addWidget(self.list)
        split.addWidget(self.text)
        split.setSizes([300, 520])

        add = QPushButton("Ajouter des fichiers…")
        add.clicked.connect(self.add_files)
        folder = QPushButton("Ajouter un dossier…")
        folder.clicked.connect(self.add_folder)
        clear = QPushButton("Vider")
        clear.clicked.connect(self.clear)
        self.lang = QComboBox()
        for label, _ in LANGS:
            self.lang.addItem(label)
        self.model = QComboBox()
        self.model.addItems(MODELS)
        self.lrc = QCheckBox("Export .lrc")
        self.go = QPushButton("Extraire les paroles")
        self.go.clicked.connect(self.start)

        bar = QHBoxLayout()
        for w in (add, folder, clear):
            bar.addWidget(w)
        bar.addStretch()
        bar.addWidget(QLabel("Langue"))
        bar.addWidget(self.lang)
        bar.addWidget(QLabel("Modèle"))
        bar.addWidget(self.model)
        bar.addWidget(self.lrc)
        bar.addWidget(self.go)

        self.status = QLabel("Prêt.")
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        lay = QVBoxLayout(self)
        lay.addLayout(bar)
        lay.addWidget(split)
        lay.addWidget(self.bar)
        lay.addWidget(self.status)

    def add_paths(self, paths):
        for p in paths:
            if p not in self.files:
                self.files.append(p)
                self.list.addItem(p.name)

    def add_files(self):
        names, _ = QFileDialog.getOpenFileNames(self, "Choisir des fichiers audio", "",
                                                "Audio (*.mp3 *.wav)")
        self.add_paths([Path(n) for n in names])

    def add_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Choisir un dossier")
        if d:
            self.add_paths(lyrics.collect(Path(d)))

    def clear(self):
        if not self.worker or not self.worker.isRunning():
            self.files.clear()
            self.list.clear()
            self.text.clear()

    def start(self):
        if not self.files:
            self.status.setText("Ajoutez d'abord des fichiers.")
            return
        self.go.setEnabled(False)
        self.bar.setValue(0)
        lang = LANGS[self.lang.currentIndex()][1]
        self.worker = Worker(list(self.files), self.model.currentText(), lang,
                             self.lrc.isChecked())
        self.worker.status.connect(self.status.setText)
        self.worker.done_file.connect(self.on_done)
        self.worker.progress.connect(self.bar.setValue)
        self.worker.finished.connect(lambda: self.go.setEnabled(True))
        self.worker.start()

    def on_done(self, txt_path):
        self.show_lyrics(self.list.currentItem())
        if self.list.currentRow() < 0:
            for i, f in enumerate(self.files):
                if str(f.with_suffix(".txt")) == txt_path:
                    self.list.setCurrentRow(i)
                    break

    def show_lyrics(self, item, _prev=None):
        if item is None:
            return
        txt = self.files[self.list.row(item)].with_suffix(".txt")
        self.text.setPlainText(txt.read_text(encoding="utf-8") if txt.exists()
                               else "(pas encore transcrit)")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = Window()
    w.show()
    sys.exit(app.exec())
