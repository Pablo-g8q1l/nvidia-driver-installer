# -*- coding: utf-8 -*-
"""Driver installation page — method and option selection and the install flow."""
from __future__ import annotations

import os
import subprocess

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMessageBox, QProgressBar,
    QPushButton, QRadioButton, QTextEdit, QVBoxLayout, QWidget,
)

from app import config
from app.core import nvidia_versions
from app.core.gpu import (
    driver_description, is_blackwell_or_newer, is_turing_or_newer,
    recommended_driver_info,
)
from app.core.installer import InstallOptions, InstallThread
from app.core.utils import is_linux, system_env, which
from app.i18n import tr, tr_prefix


def _tr_step(label: str) -> str:
    """Translates an installation step label (delegates to i18n.tr_prefix)."""
    return tr_prefix(label)


class VersionThread(QThread):
    """Fetches available driver versions in the background (internet + repository)."""

    # .run versions, repository versions, Mesa version (for the NVK method)
    sig_versions = Signal(dict, list, str)

    def __init__(self, distro, parent=None):
        super().__init__(parent)
        self._distro = distro

    def run(self):  # noqa: D102
        run_versions = nvidia_versions.fetch_run_versions()
        repo_versions = (
            nvidia_versions.get_repo_versions(self._distro) if self._distro else []
        )
        mesa_version = nvidia_versions.get_mesa_version(self._distro)
        self.sig_versions.emit(run_versions, repo_versions, mesa_version)


class InstallPage(QWidget):
    """The program's main page: detected system + fully automatic installation."""

    sig_system_changed = Signal()  # after install — the main window refreshes detection

    def __init__(self, cfg: dict | None = None, parent=None):
        super().__init__(parent)
        self._cfg = cfg if cfg is not None else {}  # program settings (incl. boot_report)
        self._state: dict = {}          # detection result from main_window
        self._install_thread = None
        self._version_thread = None
        self._build_ui()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # --- Detected system ------------------------------------------------
        # Two columns: a dimmed caption and the actual value, so the eye lands
        # on the values instead of a flat wall of same-colored text.
        box_sys = QGroupBox(tr("Wykryty system"))
        sys_lay = QVBoxLayout(box_sys)
        self.lbl_distro = QLabel(tr("wykrywanie..."))
        self.lbl_gpu = QLabel(tr("wykrywanie..."))
        self.lbl_driver = QLabel(tr("wykrywanie..."))
        # The current driver is the reference for the update notice below, so
        # its value is the only one shown in bold.
        f = self.lbl_driver.font()
        f.setBold(True)
        self.lbl_driver.setFont(f)
        # The kernel is known immediately (os.uname), without background detection
        kernel = os.uname().release if is_linux() else "—"
        self.lbl_kernel = QLabel(kernel)
        info_grid = QGridLayout()
        info_grid.setHorizontalSpacing(16)
        info_grid.setVerticalSpacing(6)
        info_grid.setColumnStretch(1, 1)
        rows = (
            (tr("Dystrybucja"), self.lbl_distro),
            (tr("Karta graficzna"), self.lbl_gpu),
            (tr("Obecny sterownik"), self.lbl_driver),
            (tr("Uruchomione jądro"), self.lbl_kernel),
        )
        for row, (caption, value) in enumerate(rows):
            lbl_caption = QLabel(caption)
            lbl_caption.setObjectName("dim")
            info_grid.addWidget(lbl_caption, row, 0, Qt.AlignmentFlag.AlignTop)
            value.setWordWrap(True)
            info_grid.addWidget(value, row, 1)
        sys_lay.addLayout(info_grid)
        # Driver update notice — accent callout (QSS #updateNotice), filled in
        # _update_notice, hidden until a newer version for the card is available
        self.lbl_update = QLabel("")
        self.lbl_update.setObjectName("updateNotice")
        self.lbl_update.setWordWrap(True)
        self.lbl_update.setVisible(False)
        sys_lay.addWidget(self.lbl_update)
        layout.addWidget(box_sys)

        # --- Installation method --------------------------------------------
        box_method = QGroupBox(tr("Metoda instalacji"))
        m_lay = QVBoxLayout(box_method)
        self.rb_repo = QRadioButton(tr("Repozytorium dystrybucji (zalecane)"))
        self.rb_run = QRadioButton(tr("Plik .run z serwerów NVIDIA"))
        self.rb_nvk = QRadioButton(tr("NVK — sterownik open source (Mesa)"))
        self.rb_repo.setChecked(True)

        self._btn_group = QButtonGroup(self)
        for rb in (self.rb_repo, self.rb_run, self.rb_nvk):
            self._btn_group.addButton(rb)
            rb.toggled.connect(self._update_method_widgets)

        def _method_frame(radio: QRadioButton, sub_row: QHBoxLayout) -> QFrame:
            """Frame for a single method — highlighted when the method is selected."""
            frame = QFrame()
            frame.setObjectName("methodRow")
            frame.setProperty("selected", False)
            f_lay = QVBoxLayout(frame)
            f_lay.setContentsMargins(10, 8, 10, 8)
            f_lay.setSpacing(4)
            f_lay.addWidget(radio)
            f_lay.addLayout(sub_row)
            return frame

        # Repository: detected version / package selection (Kubuntu/Mint)
        repo_row = QHBoxLayout()
        repo_row.addSpacing(24)
        self.lbl_repo_info = QLabel(tr("Sprawdzanie dostępnej wersji..."))
        self.lbl_repo_info.setObjectName("dim")
        self.combo_repo = QComboBox()
        self.combo_repo.setVisible(False)
        self.combo_repo.setMinimumWidth(280)
        # On plain Debian the list selects the source (Debian / NVIDIA repo),
        # which determines the availability of open kernel modules
        self.combo_repo.currentIndexChanged.connect(self._update_open_checkbox)
        repo_row.addWidget(self.lbl_repo_info)
        repo_row.addWidget(self.combo_repo)
        repo_row.addStretch()
        self._frame_repo = _method_frame(self.rb_repo, repo_row)
        m_lay.addWidget(self._frame_repo)

        # .run file: branch selection (Production / New Feature / Beta / Legacy)
        run_row = QHBoxLayout()
        run_row.addSpacing(24)
        self.combo_run = QComboBox()
        self.combo_run.setMinimumWidth(280)
        self.combo_run.addItem(tr("Pobieranie listy wersji..."), "")
        self.combo_run.currentIndexChanged.connect(self._update_open_checkbox)
        run_row.addWidget(self.combo_run)
        self.lbl_run_warn = QLabel("")
        self.lbl_run_warn.setObjectName("dim")
        run_row.addWidget(self.lbl_run_warn)
        run_row.addStretch()
        self._frame_run = _method_frame(self.rb_run, run_row)
        m_lay.addWidget(self._frame_run)

        # NVK
        nvk_row = QHBoxLayout()
        nvk_row.addSpacing(24)
        self.lbl_nvk = QLabel(
            tr("Bez komponentów NVIDIA, pełne wsparcie Wayland. Najlepiej działa"
               " na kartach RTX 20xx i nowszych.")
        )
        self.lbl_nvk.setObjectName("dim")
        self.lbl_nvk.setWordWrap(True)
        nvk_row.addWidget(self.lbl_nvk)
        self._frame_nvk = _method_frame(self.rb_nvk, nvk_row)
        m_lay.addWidget(self._frame_nvk)

        # Open kernel modules
        self.chk_open = QCheckBox(
            tr("Otwarte moduły jądra (open kernel modules) — RTX 20xx i nowsze")
        )
        m_lay.addWidget(self.chk_open)
        layout.addWidget(box_method)

        # --- Timeshift snapshot (checkbox only when the tool is installed) ---
        self.chk_snapshot = QCheckBox(
            tr("Utwórz migawkę systemu Timeshift przed instalacją")
        )
        has_timeshift = bool(is_linux() and which("timeshift"))
        self.chk_snapshot.setVisible(has_timeshift)
        self.chk_snapshot.setChecked(
            has_timeshift and bool(self._cfg.get("snapshot", False))
        )
        self.chk_snapshot.toggled.connect(self._on_snapshot_toggled)
        layout.addWidget(self.chk_snapshot)

        # --- Install button --------------------------------------------------
        self.btn_install = QPushButton(tr("ZAINSTALUJ STEROWNIK"))
        self.btn_install.setObjectName("primary")
        self.btn_install.setMinimumHeight(48)
        self.btn_install.clicked.connect(self._start_install)
        layout.addWidget(self.btn_install)

        # --- Progress and log --------------------------------------------------
        self.lbl_step = QLabel("")
        self.lbl_step.setObjectName("dim")
        layout.addWidget(self.lbl_step)
        self.progress = QProgressBar()
        self.progress.setValue(0)
        layout.addWidget(self.progress)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(140)
        self.log.setPlaceholderText(
            tr("Tutaj pojawi się szczegółowy przebieg instalacji...")
        )
        layout.addWidget(self.log, stretch=1)

        self._update_method_widgets()

    # ------------------------------------------------------ system state
    def set_system_state(self, state: dict) -> None:
        """Updates the page after system detection (called by main_window)."""
        self._state = state
        distro = state.get("distro")
        gpus = state.get("gpus", [])
        driver = state.get("driver", {})

        if distro:
            txt = distro.name
            if not distro.supported:
                txt += "  ⚠ " + tr("(nieobsługiwana — instalacja zablokowana)")
            self.lbl_distro.setText(txt)
        if gpus:
            self.lbl_gpu.setText(", ".join(g.name for g in gpus))
        else:
            self.lbl_gpu.setText(tr("nie wykryto karty NVIDIA"))
        self.lbl_driver.setText(driver_description(driver))

        # Installation is possible only on a supported Linux with an NVIDIA card
        can_install = bool(distro and distro.supported and is_linux())
        self.btn_install.setEnabled(can_install)
        if not is_linux():
            self.lbl_step.setText(
                tr("Tryb podglądu — instalacja dostępna tylko na Linuksie.")
            )

        # The method selected by default matches the driver currently on the
        # system; when there is no driver — the recommended repository stays
        typ = driver.get("typ", "")
        if typ == "nouveau":
            self.rb_nvk.setChecked(True)
        elif typ in ("proprietary", "open-kernel"):
            if driver.get("zrodlo") == "plik .run":
                self.rb_run.setChecked(True)
            else:
                self.rb_repo.setChecked(True)

        # Default state of the open-modules checkbox depending on the GPU
        turing = any(is_turing_or_newer(g.name) for g in gpus)
        self.chk_open.setChecked(turing)

        # NVK on plain Debian with RTX 50xx requires backports — a note by the
        # method so that the new kernel isn't a surprise
        opis_nvk = tr(
            "Bez komponentów NVIDIA, pełne wsparcie Wayland. Najlepiej działa"
            " na kartach RTX 20xx i nowszych."
        )
        if self._nvk_needs_backports():
            opis_nvk += " " + tr(
                "Na RTX 50xx program zainstaluje nowsze jądro, Mesę i firmware"
                " z oficjalnych backportów Debiana."
            )
        self._opis_nvk = opis_nvk  # base — the Mesa version is added after fetching
        self.lbl_nvk.setText(opis_nvk)
        self._update_method_widgets()

        # Fetch the available versions in the background
        self._version_thread = VersionThread(distro, self)
        self._version_thread.sig_versions.connect(self._on_versions)
        self._version_thread.start()

    # ------------------------------------------------------ driver versions
    def _on_versions(self, run_versions: dict, repo_versions: list,
                     mesa_version: str = "") -> None:
        """Fills the version lists after the data has been fetched in the background.

        It also matches the recommended branch to the detected card's
        architecture: marks it with a star, sets it as the default and warns
        about branches the card doesn't support (e.g. the latest driver vs a
        Kepler card).
        """
        # Mesa version next to the NVK method description (like the version for repo/run)
        if mesa_version:
            self.lbl_nvk.setText(
                getattr(self, "_opis_nvk", self.lbl_nvk.text())
                + f"\n{tr('Wykryta wersja:')} Mesa {mesa_version}"
            )
        gpus = self._state.get("gpus", [])
        # The recommendation is computed for the first card (the most common case)
        rec = (
            recommended_driver_info(gpus[0].name) if gpus
            else {"arch": "", "legacy": None, "max_major": None}
        )

        # .run branches
        self.combo_run.clear()
        rec_index = -1
        branches = [
            ("production", tr("Production (stabilna)")),
            ("new_feature", tr("New Feature")),
            ("beta", tr("Beta")),
        ]
        for key, label in branches:
            ver = run_versions.get(key)
            if not ver:
                continue
            try:
                major = int(ver.split(".")[0])
            except ValueError:
                major = 0
            text = f"{label} — {ver}"
            if rec["legacy"]:
                # Old card — new branches don't support it
                text += "  ⚠ " + tr("(nie obsługuje Twojej karty)")
            elif rec["max_major"] and major > rec["max_major"]:
                # E.g. Maxwell/Pascal: branches newer than 580 may not support it
                text += "  ⚠ " + tr("(może nie wspierać Twojej karty)")
            elif gpus and key == "production" and rec_index < 0:
                text += "  ★ " + tr("(zalecana dla Twojej karty)")
                rec_index = self.combo_run.count()
            self.combo_run.addItem(text, ver)

        for ver in run_versions.get("legacy", []):
            seria = ver.split(".")[0]
            text = f"{tr('Legacy')} {seria}.xx — {ver}"
            if rec["legacy"] == seria:
                text += "  ★ " + tr("(zalecana dla Twojej karty)")
                rec_index = self.combo_run.count()
            self.combo_run.addItem(text, ver)
        if rec_index >= 0:
            self.combo_run.setCurrentIndex(rec_index)
        if not run_versions.get("online"):
            self.combo_run.addItem(
                tr("(brak internetu — wersje zapasowe)"), ""
            )

        # Info about the detected architecture next to the branch list
        # (proper names like Kepler/Fermi are passed through by tr() unchanged)
        if rec["arch"]:
            self.lbl_run_warn.setText(
                tr("Architektura karty:") + f" {tr(rec['arch'])}"
            )

        # Driver update notice — reuses the data fetched above, no extra traffic
        self._update_notice(run_versions, rec)

        # Repository
        distro = self._state.get("distro")
        if repo_versions:
            if distro and distro.ubuntu_based and len(repo_versions) > 1:
                # Kubuntu / Mint: the user selects the driver series from the list
                self.lbl_repo_info.setText(tr("Dostępne wersje:"))
                self.combo_repo.setVisible(True)
                self.combo_repo.clear()
                for rv in repo_versions:
                    label = rv["pakiet"]
                    if rv["zalecany"]:
                        label += " ★ " + tr("(zalecany)")
                    self.combo_repo.addItem(label, rv["pakiet"])
                    if rv["zalecany"]:
                        self.combo_repo.setCurrentIndex(self.combo_repo.count() - 1)
            elif (
                distro and distro.family == "debian" and len(repo_versions) > 1
            ):
                # Plain Debian: package source selection. The Debian repo ends
                # at series 550, so for RTX 50xx the official NVIDIA repository
                # is recommended (and required).
                blackwell = any(is_blackwell_or_newer(g.name) for g in gpus)
                self.lbl_repo_info.setText(tr("Źródło pakietów:"))
                self.combo_repo.setVisible(True)
                self.combo_repo.clear()
                for rv in repo_versions:
                    src = rv.get("zrodlo", "debian")
                    if src == "nvidia":
                        label = (tr("Repozytorium NVIDIA")
                                 + f" — {rv['pakiet']} ({rv['wersja']})")
                        if blackwell:
                            label += "  ★ " + tr("(wymagane dla RTX 50xx)")
                    else:
                        label = (tr("Repozytorium Debiana")
                                 + f" — {rv['pakiet']} ({rv['wersja']})")
                        if blackwell:
                            label += "  ⚠ " + tr("(nie obsługuje RTX 50xx)")
                        else:
                            label += "  ★ " + tr("(zalecane)")
                    self.combo_repo.addItem(label, src)
                    if (src == "nvidia") == blackwell:
                        self.combo_repo.setCurrentIndex(self.combo_repo.count() - 1)
            else:
                rv = repo_versions[0]
                self.lbl_repo_info.setText(
                    tr("Wykryta wersja:") + f" {rv['pakiet']} ({rv['wersja']})"
                )
        else:
            self.lbl_repo_info.setText(
                tr("Nie udało się wykryć wersji w repozytorium.")
            )

        # Old card: the latest driver from the repository won't support it
        if rec["legacy"]:
            self.lbl_repo_info.setText(
                self.lbl_repo_info.text()
                + "\n⚠ " + tr("Twoja karta wymaga gałęzi Legacy")
                + f" {rec['legacy']}.xx — "
                + tr("najnowszy sterownik z repozytorium może jej nie"
                     " obsługiwać. Najbezpieczniejsza jest metoda .run"
                     " z zalecaną wersją.")
            )

    def _update_notice(self, run_versions: dict, rec: dict) -> None:
        """Shows a notice when a newer driver suitable for the card is available.

        Applies only to the installed proprietary / open-kernel driver — with
        nouveau/NVK updates arrive with the system (Mesa/kernel), and without
        internet the fetched versions are fallbacks, not facts. The comparison
        target respects the card's architecture: Legacy cards are compared with
        their Legacy branch, and cards with a series cap (e.g. Maxwell/Pascal
        ≤ 580) are not urged onto a branch that dropped their support.
        """
        driver = self._state.get("driver", {})
        installed = driver.get("wersja", "")
        self.lbl_update.setVisible(False)
        if (driver.get("typ") not in ("proprietary", "open-kernel")
                or not installed or not run_versions.get("online")):
            return

        target = run_versions.get("production") or ""
        if rec["legacy"]:
            target = next(
                (v for v in run_versions.get("legacy", [])
                 if v.split(".")[0] == rec["legacy"]), "",
            )
        elif rec["max_major"]:
            try:
                if target and int(target.split(".")[0]) > rec["max_major"]:
                    target = ""
            except ValueError:
                target = ""

        if target and nvidia_versions.is_newer(target, installed):
            self.lbl_update.setText(
                f"⬆ <b>{tr('Dostępna nowsza wersja sterownika:')} {target}</b>"
                f" ({tr('zainstalowana:')} {installed})"
            )
            self.lbl_update.setVisible(True)

    # ------------------------------------------------------ option logic
    def _update_method_widgets(self) -> None:
        """Enables/disables widgets depending on the selected installation method."""
        self.combo_run.setEnabled(self.rb_run.isChecked())
        self.combo_repo.setEnabled(self.rb_repo.isChecked())

        # Highlight the frame of the selected method (the QSS reads the property)
        for frame, rb in (
            (self._frame_repo, self.rb_repo),
            (self._frame_run, self.rb_run),
            (self._frame_nvk, self.rb_nvk),
        ):
            frame.setProperty("selected", rb.isChecked())
            # Force the style to be re-applied after the property changes
            frame.style().unpolish(frame)
            frame.style().polish(frame)

        self._update_open_checkbox()

    def _update_open_checkbox(self) -> None:
        """Availability rules for open kernel modules for the current method."""
        gpus = self._state.get("gpus", [])
        distro = self._state.get("distro")
        turing = any(is_turing_or_newer(g.name) for g in gpus)

        if self.rb_nvk.isChecked():
            # NVK is open by itself — the checkbox doesn't apply
            self.chk_open.setEnabled(False)
            self.chk_open.setToolTip(tr("NVK jest w całości open source."))
            return
        if any(is_blackwell_or_newer(g.name) for g in gpus):
            # Blackwell (RTX 50xx+) works only with open modules —
            # proprietary modules don't support these cards, so we force the choice
            self.chk_open.setEnabled(False)
            self.chk_open.setChecked(True)
            self.chk_open.setToolTip(
                tr("Karty RTX 50xx i nowsze działają wyłącznie z otwartymi"
                   " modułami jądra — wybór jest wymuszony.")
            )
            return
        if not turing and gpus:
            self.chk_open.setEnabled(False)
            self.chk_open.setChecked(False)
            self.chk_open.setToolTip(
                tr("Otwarte moduły wymagają karty RTX 20xx lub nowszej.")
            )
            return
        if (
            self.rb_repo.isChecked()
            and distro is not None
            and distro.family == "debian"
            and not distro.ubuntu_based
            and self.combo_repo.currentData() != "nvidia"
        ):
            # The Debian repository has no simple open variant —
            # only the official NVIDIA repository has it (nvidia-open)
            self.chk_open.setEnabled(False)
            self.chk_open.setChecked(False)
            self.chk_open.setToolTip(
                tr("Repozytorium Debiana nie oferuje wariantu open — wybierz"
                   " źródło Repozytorium NVIDIA albo metodę .run.")
            )
            return
        if self.rb_run.isChecked():
            # Old branches (Legacy < 515) have no open modules
            ver = self.combo_run.currentData() or ""
            if ver and not nvidia_versions.open_module_flag(ver):
                self.chk_open.setEnabled(False)
                self.chk_open.setChecked(False)
                self.chk_open.setToolTip(
                    tr("Ta wersja sterownika nie obsługuje modułów otwartych.")
                )
                return
        self.chk_open.setEnabled(True)
        self.chk_open.setToolTip("")

    def _nvk_needs_backports(self) -> bool:
        """Whether NVK requires backports: plain Debian + an RTX 50xx card.

        Stable Debian has too old a kernel (nouveau without GB20x), Mesa < 25.2
        (NVK without Blackwell) and firmware without GSP r570.
        """
        distro = self._state.get("distro")
        gpus = self._state.get("gpus", [])
        return bool(
            distro
            and distro.family == "debian"
            and not distro.ubuntu_based
            and any(is_blackwell_or_newer(g.name) for g in gpus)
        )

    def _on_snapshot_toggled(self, checked: bool) -> None:
        """Persists the snapshot choice so it survives program restarts."""
        self._cfg["snapshot"] = bool(checked)
        config.save_config(self._cfg)

    def _selected_method(self) -> str:
        if self.rb_nvk.isChecked():
            return "nvk"
        if self.rb_run.isChecked():
            return "run"
        return "repo"

    # ------------------------------------------------------ installation
    def _start_install(self) -> None:
        """Confirmation and launch of the fully automatic installation."""
        distro = self._state.get("distro")
        if not distro or not distro.supported:
            return
        method = self._selected_method()

        opts = InstallOptions(method=method, distro=distro,
                              open_modules=self.chk_open.isChecked(),
                              boot_report=bool(self._cfg.get("boot_report", False)),
                              snapshot=(self.chk_snapshot.isVisible()
                                        and self.chk_snapshot.isChecked()))
        opis = {
            "nvk": tr("NVK — sterownik open source (Mesa)"),
            "repo": tr("Repozytorium dystrybucji (zalecane)"),
            "run": tr("Plik .run z serwerów NVIDIA"),
        }[method]

        if method == "nvk" and self._nvk_needs_backports():
            opts.use_backports = True
            opis += "\n\n" + tr(
                "Karta RTX 50xx: jądro, Mesa i firmware zostaną"
                " zainstalowane z oficjalnych backportów Debiana."
            )
        elif method == "run":
            opts.run_version = self.combo_run.currentData() or ""
            if not opts.run_version:
                QMessageBox.warning(
                    self, tr("Brak wersji"),
                    tr("Nie wybrano wersji sterownika do pobrania."),
                )
                return
            opis += f" ({opts.run_version})"
            # Warning for old Legacy branches
            try:
                if int(opts.run_version.split(".")[0]) < 470:
                    opis += "\n\n⚠ " + tr(
                        "Gałęzie Legacy mogą nie zbudować się na nowych jądrach 6.x."
                    )
            except ValueError:
                pass
        elif method == "repo" and self.combo_repo.isVisible():
            data = self.combo_repo.currentData() or ""
            if distro.ubuntu_based:
                opts.repo_package = data
                if data:
                    opis += f" ({data})"
            else:
                # Plain Debian — the list selects the package source
                opts.repo_source = data or "debian"
                if opts.repo_source == "nvidia":
                    opis += " — " + tr("oficjalne repozytorium NVIDIA")
                else:
                    opis += " — " + tr("repozytorium Debiana")
                    gpus = self._state.get("gpus", [])
                    if any(is_blackwell_or_newer(g.name) for g in gpus):
                        opis += "\n\n⚠ " + tr(
                            "Sterownik z repozytorium Debiana (seria 550) nie"
                            " obsługuje kart RTX 50xx — wybierz Repozytorium"
                            " NVIDIA."
                        )

        # One simple question — everything after that happens automatically
        pytanie = (
            tr("Wybrana metoda:") + f"\n{opis}\n\n"
            + (tr("Przed instalacją zostanie utworzona migawka systemu"
                  " (Timeshift).") + "\n\n" if opts.snapshot else "")
            + tr("Instalacja jest w pełni automatyczna. System poprosi raz"
                 " o hasło administratora, a po zakończeniu zalecany jest"
                 " restart komputera.")
            + "\n\n" + tr("Rozpocząć instalację?")
        )
        odp = QMessageBox.question(
            self, tr("Potwierdzenie instalacji"), pytanie,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
        )
        if odp != QMessageBox.Yes:
            return

        # Without pkexec (e.g. Debian without the pkexec package) the GUI
        # collects the password, and the installation falls back to sudo -S
        sudo_pw = ""
        if is_linux() and not which("pkexec"):
            if not which("sudo"):
                QMessageBox.critical(
                    self, tr("Brak uprawnień"),
                    tr("W systemie nie ma ani pkexec, ani sudo. Zainstaluj"
                       " pakiet pkexec (polkit) i spróbuj ponownie."),
                )
                return
            sudo_pw = self._ask_sudo_password()
            if not sudo_pw:
                return

        # Lock the UI for the duration of the installation
        self.btn_install.setEnabled(False)
        self.log.clear()
        self.progress.setValue(0)
        self.lbl_step.setText(tr("Przygotowywanie instalacji..."))

        self._install_thread = InstallThread(opts, sudo_pw, self)
        self._install_thread.sig_log.connect(self._on_log)
        self._install_thread.sig_step.connect(self._on_step)
        self._install_thread.sig_download.connect(self._on_download)
        self._install_thread.sig_finished.connect(self._on_finished)
        self._install_thread.start()

    def _ask_sudo_password(self) -> str:
        """Asks for the administrator password and verifies it via sudo.

        Returns the verified password or an empty string after cancellation.
        """
        while True:
            pw, ok = QInputDialog.getText(
                self, tr("Hasło administratora"),
                tr("W systemie nie ma pkexec — podaj hasło administratora"
                   " (sudo), aby przeprowadzić instalację:"),
                QLineEdit.Password,
            )
            if not ok:
                return ""
            # -k forces fresh authorization, -p "" disables the text prompt
            wynik = subprocess.run(
                ["sudo", "-S", "-k", "-p", "", "true"],
                input=pw + "\n", text=True, capture_output=True,
            )
            if pw and wynik.returncode == 0:
                return pw
            QMessageBox.warning(
                self, tr("Błędne hasło"),
                tr("Hasło nie zostało przyjęte przez sudo — spróbuj ponownie."),
            )

    def _on_log(self, line: str) -> None:
        self.log.append(line)
        # Auto-scroll to the newest line
        sb = self.log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_step(self, idx: int, total: int, label: str) -> None:
        self.lbl_step.setText(f"{tr('Krok')} {idx}/{total}: {_tr_step(label)}")
        self.progress.setValue(int(idx * 100 / max(total, 1)))

    def _on_download(self, percent: int) -> None:
        self.lbl_step.setText(tr("Pobieranie sterownika...") + f" {percent}%")
        # The download is shown in the first half of the bar, before the script
        self.progress.setValue(percent // 2)

    def _on_finished(self, ok: bool, message: str) -> None:
        self.btn_install.setEnabled(True)
        self.sig_system_changed.emit()
        if ok:
            self.progress.setValue(100)
            self.lbl_step.setText(tr("Instalacja zakończona pomyślnie."))
            odp = QMessageBox.question(
                self, tr("Sukces"),
                tr("Sterownik został zainstalowany. Aby zmiany zadziałały,"
                   " uruchom komputer ponownie.")
                + "\n\n" + tr("Uruchomić ponownie teraz?"),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if odp == QMessageBox.Yes:
                # system_env(): from the release binary systemctl must load the
                # SYSTEM libraries, not the ones bundled by PyInstaller
                subprocess.Popen(["systemctl", "reboot"], env=system_env())
        else:
            self.lbl_step.setText(tr("Instalacja nie powiodła się."))
            QMessageBox.critical(
                self, tr("Błąd instalacji"),
                (message or tr("Nieznany błąd."))
                + "\n\n" + tr("Pełny log znajdziesz w zakładce Historia."),
            )
