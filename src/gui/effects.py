"""Effects Dialog — per-state presets, radio toggle, reverb, FX sliders."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QSlider, QScrollArea, QGroupBox, QTabWidget,
    QComboBox, QCheckBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from gui.theme import FONT_FAMILY, PRIMARY, PRIMARY_DIM
from gui.helpers import make_divider, paint_own_background
from settings import get_preset_lists


# ------------------------------------------------------------------ #
#  FX metadata
# ------------------------------------------------------------------ #

FX_TOOLTIPS = {
    "radiohighpass":  "Radio high-pass filter cutoff (Hz). Higher = thinner sound.\nOnly active when a preset uses radio FX.",
    "radiolowpass":   "Radio low-pass filter cutoff (Hz). Lower = more muffled.\nOnly active when a preset uses radio FX.",
    "reverbroomsize": "Reverb room size (0-100). Higher = larger space.\nOnly active when reverb is enabled.",
    "reverbwet":      "Reverb wet/dry mix (0-100). Higher = more echo.\nOnly active when reverb is enabled.",
    "bassboost":      "Low shelf boost at 200Hz (0-12 dB). Adds warmth and punch.\n0 = off.",
    "chorusdepth":    "Chorus depth (0-100%). Adds a shimmering, doubled effect.\n0 = off.",
    "chorusrate":     "Chorus speed (10-50). Higher = faster wobble.\nOnly active when chorus depth > 0.",
    "bitcrush":       "Bit depth (4-16). Lower = more lo-fi digital crunch.\n16 = clean / off.",
    "echodelay":      "Echo delay time (0-500 ms). Adds a repeating echo.\n0 = off.",
    "echomix":        "Echo wet/dry mix (0-100%). How loud the echo is.\nOnly active when echo delay > 0.",
}

FX_RANGES = {
    "radiohighpass":  (20, 2000, 450),
    "radiolowpass":   (500, 8000, 3000),
    "reverbroomsize": (0, 100, 80),
    "reverbwet":      (0, 100, 20),
    "bassboost":      (0, 12, 0),
    "chorusdepth":    (0, 100, 0),
    "chorusrate":     (10, 50, 10),
    "bitcrush":       (4, 16, 16),
    "echodelay":      (0, 500, 25),
    "echomix":        (0, 100, 10),
}

FX_DISPLAY_NAMES = {
    "radiohighpass":  "Radio Highpass",
    "radiolowpass":   "Radio Lowpass",
    "reverbroomsize": "Reverb Room Size",
    "reverbwet":      "Reverb Wet Mix",
    "bassboost":      "Bass Boost",
    "chorusdepth":    "Chorus Depth",
    "chorusrate":     "Chorus Rate",
    "bitcrush":       "Bitcrush",
    "echodelay":      "Echo Delay",
    "echomix":        "Echo Mix",
}

FX_PARAM_ORDER = [
    "radiohighpass", "radiolowpass",
    "reverbroomsize", "reverbwet",
    "bassboost", "chorusdepth", "chorusrate",
    "bitcrush", "echodelay", "echomix",
]

STATE_DISPLAY = {
    "shell_menu":  ("Shell Menu",   "Main menu / title screen music"),
    "avenger":     ("Avenger",      "Base management (Avenger interior) music"),
    "battle":      ("Battle",       "Tactical mission music (explore + combat)"),
    "squadselect": ("Squad Select", "Pre-mission squad loadout music"),
}

LOOP_TOOLTIP_DEFAULT = (
    "Repeat the current track instead of advancing to the next.\n"
    "Uses the _LOOP folder variant if it has tracks."
)

# Battle's box is a master over both mission phases, so it says so. Getting
# this wrong costs the player a whole mission of the same track on repeat.
LOOP_TOOLTIPS = {
    "battle": (
        "Loops the WHOLE mission — both explore and combat tracks.\n"
        "For looping only one phase, use the Explore / Combat boxes below.\n"
        "Uses the _LOOP folder variant if it has tracks."
    ),
}


# ------------------------------------------------------------------ #
#  Dialog
# ------------------------------------------------------------------ #

class EffectsDialog(QWidget):

    closed = Signal()

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        paint_own_background(self)
        self.engine = engine
        self.setWindowTitle("AFM — Effects")
        self.setMinimumSize(600, 620)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(8)

        title = QLabel("AUDIO EFFECTS")
        title.setFont(QFont(FONT_FAMILY, 14, QFont.Bold))
        title.setStyleSheet(f"color: {PRIMARY};")
        root.addWidget(title)
        root.addWidget(make_divider())

        tabs = QTabWidget()
        tabs.addTab(self._build_state_tab(), "Per-State")
        tabs.addTab(self._build_fx_tab(), "Global FX Sliders")
        root.addWidget(tabs)

        info = QLabel(
            "Per-state settings are saved to the game's ini and synced via MCM.\n"
            "Global FX sliders apply when a state's preset is set to 'Custom'."
        )
        info.setFont(QFont(FONT_FAMILY, 10))
        info.setStyleSheet(f"color: {PRIMARY_DIM};")
        info.setWordWrap(True)
        root.addWidget(info)

    # ------------------------------------------------------------ #
    #  Per-State Tab
    # ------------------------------------------------------------ #

    def _build_state_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        settings = self.engine.settings if self.engine else None

        for state_key, (display_name, tip) in STATE_DISPLAY.items():
            group = QGroupBox(display_name)
            group.setToolTip(tip)
            g_lay = QGridLayout(group)
            g_lay.setSpacing(6)

            # Preset
            g_lay.addWidget(QLabel("Preset:"), 0, 0)
            combo = QComboBox()
            preset_names, preset_keys = get_preset_lists()
            combo.addItems(preset_names)
            if settings:
                cur = settings.presets.get(state_key, "custom")
                if cur in preset_keys:
                    combo.setCurrentIndex(preset_keys.index(cur))
            combo.setToolTip(
                "Choose an FX preset for this state.\n"
                "'Custom' uses the Global FX sliders + individual checkboxes.\n"
                "'Clean' disables all effects.\n"
                "'Field Radio' applies a radio filter (highpass + lowpass + compressor)."
            )
            combo.currentIndexChanged.connect(
                lambda idx, k=state_key: self._on_preset_changed(k, idx)
            )
            g_lay.addWidget(combo, 0, 1)

            # Radio Source
            radio_cb = QCheckBox("Radio Source")
            radio_cb.setToolTip(
                "Play tracks from the shared Resistance Radio folder\n"
                "instead of this state's own folder.\n"
                "Every track starts from a random position (like tuning in)."
            )
            if settings:
                radio_cb.setChecked(settings.radio.get(state_key, False))
            radio_cb.toggled.connect(lambda val, k=state_key: self._on_radio(k, val))
            g_lay.addWidget(radio_cb, 1, 0)

            # Reverb
            reverb_cb = QCheckBox("Reverb")
            reverb_cb.setToolTip(
                "Add reverb to this state's music.\n"
                "Room size and wet mix are set in the Global FX tab.\n"
                "Only applies when preset is 'Custom'."
            )
            if settings:
                reverb_cb.setChecked(settings.reverb.get(state_key, False))
            reverb_cb.toggled.connect(lambda val, k=state_key: self._on_reverb(k, val))
            g_lay.addWidget(reverb_cb, 1, 1)

            # Loop
            loop_cb = QCheckBox("Loop Track")
            loop_cb.setToolTip(
                LOOP_TOOLTIPS.get(state_key, LOOP_TOOLTIP_DEFAULT)
            )
            if settings:
                loop_cb.setChecked(settings.loop.get(state_key, False))
            loop_cb.toggled.connect(lambda val, k=state_key: self._on_loop(k, val))
            g_lay.addWidget(loop_cb, 2, 0)

            # Random Start
            rand_cb = QCheckBox("Random Start")
            rand_cb.setToolTip(
                "Start each track from a random position.\n"
                "Like tuning into a radio station mid-song."
            )
            if settings:
                rand_cb.setChecked(settings.random_start.get(state_key, False))
            rand_cb.toggled.connect(lambda val, k=state_key: self._on_random_start(k, val))
            g_lay.addWidget(rand_cb, 2, 1)

            layout.addWidget(group)

            # The two mission phases sit directly under Battle, where they
            # read as a refinement of its Loop Track box rather than an
            # unrelated group stranded at the bottom of the list.
            if state_key == "battle":
                layout.addWidget(self._build_battle_phases(settings))

        layout.addStretch()
        scroll.setWidget(container)
        return scroll

    def _build_battle_phases(self, settings):
        """Explore/Combat sub-toggles — narrower than Battle's own Loop Track."""
        group = QGroupBox("Battle phases — loop just one phase")
        group.setToolTip(
            "Battle's Loop Track box loops the whole mission.\n"
            "These narrow it to a single phase, and give each phase its own\n"
            "random start setting."
        )
        g_lay = QGridLayout(group)

        phases = [
            ("explore", "Explore", "explore (out of contact)"),
            ("combat",  "Combat",  "combat (enemies engaged)"),
        ]
        for row, (sub_key, sub_label, phase_desc) in enumerate(phases):
            loop_cb = QCheckBox(f"{sub_label} Loop")
            loop_cb.setToolTip(
                f"Loops ONLY {phase_desc} tracks.\n"
                f"Battle's Loop Track box loops both phases instead."
            )
            if settings:
                loop_cb.setChecked(settings.loop.get(sub_key, False))
            loop_cb.toggled.connect(lambda val, k=sub_key: self._on_loop(k, val))
            g_lay.addWidget(loop_cb, row, 0)

            rand_cb = QCheckBox(f"{sub_label} Random Start")
            rand_cb.setToolTip(f"Random start position during {phase_desc}.")
            if settings:
                rand_cb.setChecked(settings.random_start.get(sub_key, False))
            rand_cb.toggled.connect(lambda val, k=sub_key: self._on_random_start(k, val))
            g_lay.addWidget(rand_cb, row, 1)

        return group

    # ------------------------------------------------------------ #
    #  Global FX Sliders Tab
    # ------------------------------------------------------------ #

    def _build_fx_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        note = QLabel(
            "These sliders control the FX parameters when a state's preset\n"
            "is set to 'Custom'. Named presets override these values."
        )
        note.setFont(QFont(FONT_FAMILY, 10))
        note.setStyleSheet(f"color: {PRIMARY_DIM};")
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addSpacing(4)

        settings = self.engine.settings if self.engine else None

        for param_key in FX_PARAM_ORDER:
            lo, hi, default = FX_RANGES[param_key]
            current = settings.fx_params.get(param_key, default) if settings else default
            display = FX_DISPLAY_NAMES[param_key]

            row = QHBoxLayout()
            row.setSpacing(8)

            name_lbl = QLabel(display)
            name_lbl.setFixedWidth(140)
            name_lbl.setFont(QFont(FONT_FAMILY, 11))
            name_lbl.setToolTip(FX_TOOLTIPS.get(param_key, ""))
            row.addWidget(name_lbl)

            slider = QSlider(Qt.Horizontal)
            slider.setRange(lo, hi)
            slider.setValue(current)
            slider.setToolTip(FX_TOOLTIPS.get(param_key, ""))
            row.addWidget(slider)

            val_lbl = QLabel(str(current))
            val_lbl.setFixedWidth(40)
            val_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            val_lbl.setFont(QFont(FONT_FAMILY, 11))
            row.addWidget(val_lbl)

            slider.valueChanged.connect(
                lambda v, k=param_key, lbl=val_lbl: self._on_fx_slider(k, v, lbl)
            )
            layout.addLayout(row)

        layout.addStretch()
        scroll.setWidget(container)
        return scroll

    # ------------------------------------------------------------ #
    #  Callbacks
    # ------------------------------------------------------------ #

    def _on_preset_changed(self, state_key, index):
        if not self.engine:
            return
        _, keys = get_preset_lists()
        if 0 <= index < len(keys):
            self.engine.set_preset(state_key, keys[index])

    def _on_radio(self, key, val):
        if self.engine:
            self.engine.set_radio(key, val)

    def _on_reverb(self, key, val):
        if self.engine:
            self.engine.set_reverb(key, val)

    def _on_loop(self, key, val):
        if self.engine:
            self.engine.set_loop(key, val)

    def _on_random_start(self, key, val):
        if self.engine:
            self.engine.set_random_start(key, val)

    def _on_fx_slider(self, key, val, label):
        label.setText(str(val))
        if self.engine:
            self.engine.set_fx_param(key, val)

    def closeEvent(self, event):
        self.closed.emit()
        event.accept()
