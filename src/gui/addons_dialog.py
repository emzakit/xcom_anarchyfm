"""Music Addons panel — turn subscribed Workshop music packs on and off.

Lists every `xipod_settings.json` pack found in the workshop folder, with its author,
genre tags, description and how many tracks it actually contributed to the
library. Toggling a pack and hitting Save rescans the library, so changes are
audible without restarting.

Addon audio is never copied — it plays from the workshop folder where Steam
put it (see addons.py). That's what makes an on/off switch meaningful.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox,
    QScrollArea, QFrame, QComboBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from gui.theme import (
    FONT_FAMILY, PRIMARY, PRIMARY_DIM, PRIMARY_FAINT, AMBER, ACCENT, BORDER,
)
from gui.helpers import make_divider, paint_own_background
import console

# Where the Make a Pack button sends people. Building a pack is a manual
# job through the XCOM 2 SDK — see _on_make_a_pack.
MUSIC_PACK_GUIDE_URL = (
    "https://github.com/emzakit/xcom_anarchyfm/wiki/Making-a-music-pack"
)


SORT_NAME = "Name (A-Z)"
SORT_NAME_DESC = "Name (Z-A)"
SORT_GENRE = "Genre"
SORT_TRACKS = "Track count"
SORT_MODES = [SORT_NAME, SORT_NAME_DESC, SORT_GENRE, SORT_TRACKS]


class AddonsDialog(QWidget):

    closed = Signal()

    def __init__(self, engine, config_path, parent=None):
        super().__init__(parent)
        paint_own_background(self)
        self.engine = engine
        self.config_path = config_path
        self.addons = list(engine.addons or [])

        self.setWindowTitle("AFM — Music Addons")
        self.setMinimumSize(660, 720)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(6)

        title = QLabel("MUSIC ADDONS")
        title.setFont(QFont(FONT_FAMILY, 14, QFont.Bold))
        title.setStyleSheet(f"color: {PRIMARY};")
        root.addWidget(title)

        blurb = QLabel(
            "Workshop music packs you're subscribed to. Their tracks play "
            "straight from the workshop folder alongside your own music — "
            "nothing is copied, so turning one off simply drops it from the "
            "library on the next scan."
        )
        blurb.setWordWrap(True)
        blurb.setStyleSheet(f"color: {PRIMARY_DIM}; font-size: 11px;")
        root.addWidget(blurb)

        # --- Toolbar: sort + bulk toggles ---
        bar = QHBoxLayout()
        bar.setSpacing(6)
        sort_lbl = QLabel("Sort by:")
        sort_lbl.setStyleSheet(f"color: {PRIMARY_DIM}; font-size: 11px;")
        bar.addWidget(sort_lbl)

        self.sort_box = QComboBox()
        self.sort_box.addItems(SORT_MODES)
        self.sort_box.currentTextChanged.connect(lambda _: self._rebuild())
        bar.addWidget(self.sort_box)

        gl = QLabel("Genre:")
        gl.setStyleSheet(f"color: {PRIMARY_DIM}; font-size: 11px;")
        bar.addWidget(gl)
        self.genre_box = QComboBox()
        self.genre_box.currentTextChanged.connect(lambda _: self._rebuild())
        bar.addWidget(self.genre_box)

        bar.addStretch()
        all_on = QPushButton("Enable all")
        all_on.setCursor(Qt.PointingHandCursor)
        all_on.clicked.connect(lambda: self._set_all(True))
        bar.addWidget(all_on)
        all_off = QPushButton("Disable all")
        all_off.setCursor(Qt.PointingHandCursor)
        all_off.clicked.connect(lambda: self._set_all(False))
        bar.addWidget(all_off)
        root.addLayout(bar)
        root.addWidget(make_divider())

        # --- The list ---
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        root.addWidget(self.scroll, 1)

        # --- Buttons ---
        root.addWidget(make_divider())
        row = QHBoxLayout()
        self.summary = QLabel("")
        self.summary.setStyleSheet(f"color: {PRIMARY_DIM}; font-size: 11px;")
        row.addWidget(self.summary)
        row.addStretch()

        # Making a pack belongs with browsing packs, not on the main panel.
        # It's a once-in-a-while authoring job, and it was taking up a slot
        # next to the controls people press every session.
        make_btn = QPushButton("Make a Pack")
        make_btn.setCursor(Qt.PointingHandCursor)
        make_btn.setFixedWidth(130)
        make_btn.setToolTip(
            "Opens the guide for building your own music pack\n"
            "and publishing it to the Workshop.")
        make_btn.clicked.connect(self._on_make_a_pack)
        row.addWidget(make_btn)

        # "&&" — a single & is swallowed as a Qt mnemonic accelerator.
        save_btn = QPushButton("Save && Rescan")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setFixedWidth(150)
        save_btn.setStyleSheet(
            f"background-color: {PRIMARY_FAINT}; border: 1px solid {PRIMARY_DIM}; "
            f"font-weight: bold; padding: 8px;"
        )
        save_btn.clicked.connect(self._on_save)
        row.addWidget(save_btn)
        close_btn = QPushButton("Close")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(self.close)
        row.addWidget(close_btn)
        root.addLayout(row)

        self.status = QLabel("")
        self.status.setStyleSheet(f"color: {AMBER}; font-size: 11px;")
        self.status.setAlignment(Qt.AlignCenter)
        root.addWidget(self.status)

        self._checkboxes = {}      # addon id -> QCheckBox
        self._populate_genres()
        self._rebuild()

    # ------------------------------------------------------------------ #

    def _populate_genres(self):
        genres = sorted({g for a in self.addons for g in a.genres},
                        key=str.lower)
        self.genre_box.blockSignals(True)
        self.genre_box.clear()
        self.genre_box.addItem("All")
        self.genre_box.addItems(genres)
        self.genre_box.blockSignals(False)

    def _sorted_addons(self):
        mode = self.sort_box.currentText()
        wanted = self.genre_box.currentText()
        items = self.addons
        if wanted and wanted != "All":
            items = [a for a in items if wanted in a.genres]

        if mode == SORT_NAME_DESC:
            return sorted(items, key=lambda a: a.name.lower(), reverse=True)
        if mode == SORT_GENRE:
            # Ungenred packs sort last rather than first — an empty string
            # would otherwise float them to the top of every list.
            return sorted(items, key=lambda a: (
                a.genres[0].lower() if a.genres else "zzzz", a.name.lower()))
        if mode == SORT_TRACKS:
            return sorted(items, key=lambda a: (-a.track_count, a.name.lower()))
        return sorted(items, key=lambda a: a.name.lower())

    def _rebuild(self):
        """Redraw the list. Checkbox state is held on the Addon objects, so
        re-sorting never loses a pending tick."""
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(8)
        self._checkboxes = {}

        items = self._sorted_addons()
        if not items:
            empty = QLabel(
                "No music addons found.\n\n"
                "Subscribe to a music pack on the Workshop, then make sure your "
                "Workshop folder is set correctly in Options."
                if not self.addons else
                "No addons match this genre filter."
            )
            empty.setWordWrap(True)
            empty.setStyleSheet(f"color: {PRIMARY_DIM};")
            lay.addWidget(empty)
        else:
            for addon in items:
                lay.addWidget(self._addon_card(addon))

        lay.addStretch()
        self.scroll.setWidget(inner)
        self._update_summary()

    def _addon_card(self, addon):
        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ border: 1px solid {BORDER}; border-radius: 4px; }}")
        box = QVBoxLayout(card)
        box.setContentsMargins(10, 8, 10, 8)
        box.setSpacing(4)

        top = QHBoxLayout()
        cb = QCheckBox(addon.name)
        cb.setChecked(addon.enabled)
        cb.setFont(QFont(FONT_FAMILY, 12, QFont.Bold))
        cb.setStyleSheet("border: none;")
        cb.toggled.connect(lambda on, a=addon: self._on_toggle(a, on))
        self._checkboxes[addon.id] = cb
        top.addWidget(cb)

        # A local pack under test looks identical to a subscribed one
        # otherwise, and confusing the two while you're mid-edit is a good way
        # to waste an evening.
        if getattr(addon, "is_test", False):
            tag = QLabel("TEST")
            tag.setToolTip("From your addon testing folder — not published.")
            tag.setStyleSheet(
                f"color: {AMBER}; font-size: 10px; font-weight: bold; "
                f"border: 1px solid {AMBER}; border-radius: 3px; padding: 0px 4px;"
            )
            top.addSpacing(6)
            top.addWidget(tag)

        top.addStretch()

        count = QLabel(f"{addon.track_count} track{'' if addon.track_count == 1 else 's'}")
        count.setStyleSheet(f"color: {ACCENT}; font-size: 11px; border: none;")
        top.addWidget(count)
        box.addLayout(top)

        meta_bits = []
        if addon.author:
            meta_bits.append(f"by {addon.author}")
        meta_bits.append(addon.genre_text())
        meta = QLabel("   ·   ".join(meta_bits))
        meta.setStyleSheet(f"color: {AMBER}; font-size: 11px; border: none;")
        box.addWidget(meta)

        if addon.description:
            desc = QLabel(addon.description)
            desc.setWordWrap(True)
            desc.setStyleSheet(f"color: {PRIMARY_DIM}; font-size: 11px; border: none;")
            box.addWidget(desc)

        states = ", ".join(sorted(
            k.replace("state_", "").replace("_", " ").title()
            for k in addon.folders_resolved())) or "nothing usable"
        scope = QLabel(f"Scores: {states}")
        scope.setWordWrap(True)
        scope.setStyleSheet(f"color: {PRIMARY_DIM}; font-size: 10px; border: none;")
        box.addWidget(scope)

        return card

    def _on_toggle(self, addon, on):
        addon.enabled = on
        self._update_summary()

    def _set_all(self, on):
        for a in self.addons:
            a.enabled = on
        for cb in self._checkboxes.values():
            cb.blockSignals(True)
            cb.setChecked(on)
            cb.blockSignals(False)
        self._update_summary()

    def _update_summary(self):
        on = sum(1 for a in self.addons if a.enabled)
        self.summary.setText(f"{on} of {len(self.addons)} addon(s) enabled")

    # ------------------------------------------------------------------ #

    def _on_make_a_pack(self):
        """Open the pack-authoring guide.

        A page rather than a one-click scaffolder: the old version built a
        ready-to-publish ModBuddy project, which was flaky, and a button that
        packages up someone's mp3s for redistribution is a very different
        thing from a page explaining how to do it yourself.
        """
        import webbrowser
        console.shen("Opening the music pack guide in your browser.")
        webbrowser.open(MUSIC_PACK_GUIDE_URL)
        self.status.setText("Guide opened in your browser.")

    def _on_save(self):
        import addons as addons_mod
        enabled_map = {a.id: a.enabled for a in self.addons}
        addons_mod.save_enabled_map(self.config_path, enabled_map)

        if self.engine:
            self.engine.rescan()
            self._rebuild()   # track counts change with what's enabled

        on = sum(1 for a in self.addons if a.enabled)
        self.status.setText(f"Saved. {on} addon(s) enabled — library rescanned.")
        console.shen(f"Music addons updated — {on} enabled.")

    def closeEvent(self, event):
        self.closed.emit()
        event.accept()
