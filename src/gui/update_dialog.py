"""Update dialog — shows what's new and applies it.

Download runs on a worker thread; the UI is driven by signals so the progress
bar actually moves and the window stays responsive on a slow connection.
"""

import threading

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit,
    QProgressBar, QCheckBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from gui.theme import FONT_FAMILY, PRIMARY, PRIMARY_DIM, PRIMARY_FAINT, AMBER, ACCENT
from gui.helpers import make_divider, paint_own_background
import console
import updater
import version


class UpdateDialog(QWidget):

    closed = Signal()
    _progress = Signal(int, int)
    _failed = Signal(str)
    _ready = Signal(str)      # staged build root

    def __init__(self, release, on_skip=None, parent=None):
        super().__init__(parent)
        paint_own_background(self)
        self.release = release
        self._on_skip = on_skip
        self._busy = False

        self.setWindowTitle("AFM — Update Available")
        self.setMinimumSize(600, 520)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(6)

        title = QLabel("UPDATE AVAILABLE")
        title.setFont(QFont(FONT_FAMILY, 14, QFont.Bold))
        title.setStyleSheet(f"color: {PRIMARY};")
        root.addWidget(title)

        vers = QLabel(f"You have {version.__version__}   →   {release.version} is out")
        vers.setStyleSheet(f"color: {ACCENT}; font-size: 12px;")
        root.addWidget(vers)
        root.addWidget(make_divider())

        notes = QTextEdit()
        notes.setReadOnly(True)
        notes.setPlainText(release.notes or "No release notes were provided.")
        notes.setFont(QFont(FONT_FAMILY, 10))
        root.addWidget(notes, 1)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setStyleSheet(f"color: {AMBER}; font-size: 11px;")
        root.addWidget(self.status)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setVisible(False)
        root.addWidget(self.bar)

        self.auto_cb = QCheckBox("Check for updates when Anarchy Radio FM starts")
        self.auto_cb.setChecked(True)
        root.addWidget(self.auto_cb)

        row = QHBoxLayout()
        row.addStretch()

        self.install_btn = QPushButton("Download && Install")
        self.install_btn.setCursor(Qt.PointingHandCursor)
        self.install_btn.setFixedWidth(180)
        self.install_btn.setStyleSheet(
            f"background-color: {PRIMARY_FAINT}; border: 1px solid {PRIMARY_DIM}; "
            f"font-weight: bold; padding: 8px;")
        self.install_btn.clicked.connect(self._on_install)
        row.addWidget(self.install_btn)

        page_btn = QPushButton("Open Releases Page")
        page_btn.setCursor(Qt.PointingHandCursor)
        page_btn.clicked.connect(lambda: updater.open_releases_page())
        row.addWidget(page_btn)

        later = QPushButton("Later")
        later.setCursor(Qt.PointingHandCursor)
        later.setFixedWidth(90)
        later.clicked.connect(self.close)
        row.addWidget(later)
        root.addLayout(row)

        if not release.can_auto_apply():
            self.install_btn.setEnabled(False)
            self.status.setText(
                "Running from source — update with git instead."
                if not release.asset_url else
                "No installable download on this release; use the releases page.")

        self._progress.connect(self._on_progress)
        self._failed.connect(self._on_failed)
        self._ready.connect(self._on_ready)

    # ------------------------------------------------------------------ #

    def auto_check_wanted(self):
        return self.auto_cb.isChecked()

    def _on_install(self):
        if self._busy:
            return
        self._busy = True
        self.install_btn.setEnabled(False)
        self.bar.setVisible(True)
        self.status.setText("Downloading…")

        def worker():
            try:
                path = updater.download(
                    self.release,
                    progress=lambda d, t: self._progress.emit(d, t))
                build_root = updater.stage(path)
            except Exception as e:
                self._failed.emit(str(e))
                return
            self._ready.emit(build_root)

        threading.Thread(target=worker, daemon=True, name="AFMUpdate").start()

    def _on_progress(self, done, total):
        if total:
            self.bar.setValue(int(done * 100 / total))
            self.status.setText(f"Downloading… {done // 1048576} MB of {total // 1048576} MB")
        else:
            self.bar.setRange(0, 0)   # indeterminate

    def _on_failed(self, message):
        self._busy = False
        self.bar.setVisible(False)
        self.install_btn.setEnabled(True)
        self.status.setText(f"Update failed: {message}")
        console.warn(f"Update failed: {message}")

    def _on_ready(self, build_root):
        self.bar.setValue(100)
        self.status.setText("Download verified. Restarting to apply…")
        console.shen("Update downloaded — restarting to apply.")
        try:
            updater.apply_and_restart(build_root)
        except Exception as e:
            self._on_failed(f"couldn't start the installer: {e}")
            return
        # The helper is waiting on our PID; get out of its way.
        from PySide6.QtWidgets import QApplication
        QApplication.instance().quit()

    def closeEvent(self, event):
        if self._on_skip:
            self._on_skip(self.release.version, self.auto_cb.isChecked())
        self.closed.emit()
        event.accept()
