# -*- coding: utf-8 -*-
"""Silnik instalacji sterownika NVIDIA.

Zasada działania: dla wybranej metody (nvk / repo / run) i rodziny dystrybucji
generowany jest JEDEN skrypt bash, uruchamiany przez pkexec — użytkownik podaje
hasło tylko raz. Skrypt wypisuje znaczniki:
    @KROK@ opis   — początek kolejnego kroku (GUI aktualizuje pasek postępu)
    @BLAD@ opis   — czytelny opis błędu przed przerwaniem
    @SUKCES@      — wszystkie kroki zakończone
Całe wyjście trafia do logu na żywo w GUI oraz do pliku historii instalacji.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass

try:
    from PySide6.QtCore import QThread, Signal
except ImportError:
    # Wersja CLI (osobny projekt) importuje stąd build_plan i _ROOT_RUNNER
    # bez zainstalowanego Qt — atrapy pozwalają załadować moduł, a klasa
    # InstallThread po prostu nie jest wtedy używana (GUI zawsze ma PySide6)
    QThread = object

    def Signal(*_args, **_kwargs):  # noqa: N802 — atrapa API Qt
        return None

from app.i18n import tr

from . import history, nvidia_versions, utils
from .distro import DistroInfo


@dataclass
class InstallOptions:
    """Parametry instalacji wybrane przez użytkownika w GUI."""

    method: str                 # "nvk" | "repo" | "run"
    distro: DistroInfo
    open_modules: bool = False  # otwarte moduły jądra (Turing+)
    run_version: str = ""       # wersja dla metody "run", np. "580.95.05"
    repo_package: str = ""      # pakiet dla Kubuntu/Mint, np. "nvidia-driver-580"
    repo_source: str = ""       # czysty Debian: "debian" (non-free) | "nvidia"
    use_backports: bool = False  # NVK na czystym Debianie z RTX 50xx
    boot_report: bool = False   # usługa raportu rozruchu (opt-in z Ustawień)


# Uruchomienie skryptu podanego na standardowym wejściu (ścieżka pkexec).
# Root przepisuje skrypt z potoku do WŁASNEGO pliku tymczasowego (0600, root)
# i dopiero ten wykonuje — treści nie da się podmienić między autoryzacją
# a wykonaniem (TOCTOU), jak przy pliku użytkownika w /tmp. Wykonanie z pliku
# (nie `bash -s`) zostawia stdin na EOF, więc żaden krok nie „zje" reszty
# skryptu, gdyby czytał standardowe wejście.
_ROOT_RUNNER = (
    'tmp="$(mktemp)" && cat > "$tmp" && bash "$tmp"; rc=$?; rm -f "$tmp"; exit $rc'
)

# Nagłówek każdego generowanego skryptu — funkcje pomocnicze i tryb nieinteraktywny
_SCRIPT_HEADER = """#!/bin/bash
# Skrypt wygenerowany automatycznie przez NVIDIA Driver Installer.
set -o pipefail
export DEBIAN_FRONTEND=noninteractive
krok() { echo "@KROK@ $1"; }
blad() { echo "@BLAD@ $1"; exit 1; }
"""

# Konfiguracja modprobe dla sterownika NVIDIA: blokada nouveau + KMS (Wayland)
_MODPROBE_CONFIG = """mkdir -p /etc/modprobe.d
cat > /etc/modprobe.d/blacklist-nouveau.conf <<'EOF'
# Wygenerowane przez NVIDIA Driver Installer - blokada sterownika nouveau
blacklist nouveau
options nouveau modeset=0
EOF
cat > /etc/modprobe.d/nvidia-modeset.conf <<'EOF'
# Wygenerowane przez NVIDIA Driver Installer - KMS dla NVIDIA (Wayland)
options nvidia_drm modeset=1 fbdev=1
EOF
true"""

# Usunięcie naszej konfiguracji (dla metody NVK, gdzie nouveau ma działać).
# Dodatkowo: osierocone pliki dracuta wymuszające moduły nvidia w initramfs
# (force_drivers/add_drivers) — zostawiają je narzędzia dystrybucji
# (np. nvidia-inst na EndeavourOS tworzy /etc/dracut.conf.d/eos_nvidia_open.conf,
# którego żaden pakiet ani hook nie sprząta; przypadek EndeavourOS 2026-07-05).
# Po odinstalowaniu sterownika taki plik każe dracutowi wciskać nieistniejące
# moduły (FAILED przy budowie) i wpisuje rd.driver.pre=nvidia do cmdline
# initramfs — błędy ładowania przy każdym rozruchu. Usuwamy wyłącznie pliki,
# których treść faktycznie wymusza moduły nvidia (warunek na stanie systemu,
# nie nazwie dystrybucji); bez takich plików pętla niczego nie zmienia.
_REMOVE_MODPROBE_CONFIG = (
    "rm -f /etc/modprobe.d/blacklist-nouveau.conf"
    " /etc/modprobe.d/nvidia-modeset.conf"
    " /etc/modprobe.d/nvidia-drm.conf"
    " /etc/modprobe.d/nvidia-installer-disable-nouveau.conf"
    " /usr/lib/modprobe.d/nvidia-installer-disable-nouveau.conf\n"
    "for f in /etc/dracut.conf.d/*.conf; do\n"
    '  [ -e "$f" ] || continue\n'
    "  if grep -qE '^[^#]*(force_drivers|add_drivers)[+ ]?=.*nvidia' \"$f\"; then\n"
    '    echo "Usuwam wymuszenie modułów NVIDIA w konfiguracji dracuta: $f"\n'
    '    rm -f "$f"\n'
    "  fi\n"
    "done\n"
    "true"
)

# Usunięcie wymuszeń sterownika NVIDIA w zmiennych środowiskowych —
# pozostawiają je inne narzędzia (np. nvidia-driver-manager). Bez sterownika
# NVIDIA psują inicjalizację EGL i pulpit spada na renderowanie programowe CPU
_REMOVE_GL_ENV = """rm -f /etc/environment.d/99-nvidia-wayland.conf
if [ -f /etc/environment ]; then
  sed -i -E '/^(GBM_BACKEND|__GLX_VENDOR_LIBRARY_NAME|__EGL_VENDOR_LIBRARY_FILENAMES|__EGL_VENDOR_LIBRARY_FILELIST|LIBVA_DRIVER_NAME|VDPAU_DRIVER)=.*nvidia/d' /etc/environment
fi
true"""

# Usunięcie parametrów nvidia-drm z linii poleceń jądra — pozostałość po
# sterowniku własnościowym. Krok niekrytyczny: błędy nie przerywają instalacji
_REMOVE_KERNEL_PARAMS = """if [ -f /etc/default/grub ] && grep -qE 'nvidia[-_]drm\\.' /etc/default/grub; then
  sed -i -E 's/ ?nvidia[-_]drm\\.[a-z]+=[0-9]+//g' /etc/default/grub
  if command -v update-grub >/dev/null 2>&1; then update-grub || true
  elif command -v grub2-mkconfig >/dev/null 2>&1; then grub2-mkconfig -o /boot/grub2/grub.cfg || true
  elif command -v grub-mkconfig >/dev/null 2>&1; then grub-mkconfig -o /boot/grub/grub.cfg || true
  fi
fi
if command -v grubby >/dev/null 2>&1; then
  grubby --update-kernel=ALL --remove-args="nvidia-drm.modeset=1 nvidia-drm.fbdev=1 nvidia_drm.modeset=1 nvidia_drm.fbdev=1" 2>/dev/null || true
fi
true"""

# Kontrola obecności firmware GSP — bez niego nouveau nie obsłuży kart RTX
# (Turing i nowszych); tylko ostrzeżenie, na starszych kartach GSP nie istnieje
_GSP_FIRMWARE_CHECK = (
    "find /lib/firmware/nvidia -name 'gsp*' 2>/dev/null | grep -q ."
    ' || echo "UWAGA: brak plików firmware GSP w /lib/firmware/nvidia'
    ' — na kartach RTX nouveau nie wystartuje"\ntrue'
)

# Kontrola obecności modułu nouveau dla działającego jądra — bez niego po
# odinstalowaniu sterownika NVIDIA pulpit spada na renderowanie CPU
_NOUVEAU_MODULE_CHECK = (
    "modinfo nouveau >/dev/null 2>&1"
    ' || echo "UWAGA: brak modułu nouveau dla działającego jądra'
    ' — pulpit może spaść na renderowanie programowe CPU"\ntrue'
)

# Fedora: moduł nouveau leży w pakiecie kernel-modules, którego może brakować —
# instalacja akmod-nvidia potrafi dociągnąć nowe jądro tylko częściowo
# (kernel-core i kernel-devel jako zależności, bez kernel-modules). Po
# przejściu na NVK takie jądro wstaje bez żadnego sterownika GPU. Doinstaluj
# kernel-modules dla każdego zainstalowanego jądra, któremu brakuje nouveau.
_NOUVEAU_KERNEL_MODULES_FEDORA = """for k in /lib/modules/*/; do
  k="$(basename "$k")"
  [ -e "/lib/modules/$k/vmlinuz" ] || continue
  modinfo -k "$k" nouveau >/dev/null 2>&1 && continue
  dnf -y install "kernel-modules-$k" || echo "UWAGA: nie udało się doinstalować pakietu kernel-modules-$k"
done
true"""

# Nobara: własne repozytorium (nobara-nvidia-production) dostarcza akmod-nvidia
# w wersji nowszej niż RPMFusion, ale userspace pakietuje po negativo17
# (nvidia-driver*), a nie po RPMFusion (xorg-x11-drv-nvidia*). Stała lista
# "akmod-nvidia xorg-x11-drv-nvidia-cuda" miesza wtedy dwa stosy: moduł jądra
# idzie z repo dystrybucji (wyższa wersja wygrywa), biblioteki CUDA z RPMFusion
# (jedyny dostawca tej nazwy), a właściwy sterownik GL (libGLX_nvidia) nie
# instaluje się wcale — pulpit spada na llvmpipe, nvidia-smi zgłasza
# "Driver/library version mismatch" (przypadek Nobara 43, 2026-07-03).
# Wybór zestawu warunkujemy na stanie repozytoriów, nie nazwie dystrybucji:
# jeśli najnowszy akmod-nvidia ma odpowiednik nvidia-driver w tej samej
# wersji, a xorg-x11-drv-nvidia w tej wersji nie istnieje, instalujemy zestaw
# natywny (usuwając wcześniej ewentualne resztki xorg-x11-drv-nvidia* — te
# same pliki pod innymi nazwami pakietów powodują konflikty). Na czystej
# Fedorze nvidia-driver nie istnieje w żadnym repozytorium, warunek nie
# zachodzi i zestaw pozostaje dokładnie dotychczasowy.
_FEDORA_REPO_INSTALL = """PKGS="akmod-nvidia xorg-x11-drv-nvidia-cuda"
AKMOD_V="$(dnf -q repoquery --qf '%{version}\\n' akmod-nvidia 2>/dev/null | sort -V | tail -n1)"
if [ -n "$AKMOD_V" ] \\
   && dnf -q repoquery --qf '%{version}\\n' nvidia-driver 2>/dev/null | grep -qxF "$AKMOD_V" \\
   && ! dnf -q repoquery --qf '%{version}\\n' xorg-x11-drv-nvidia 2>/dev/null | grep -qxF "$AKMOD_V"; then
  echo "Repozytorium dystrybucji pakietuje sterownik jako nvidia-driver ($AKMOD_V) — instaluję zestaw natywny"
  PKGS="akmod-nvidia nvidia-driver nvidia-driver-cuda"
  dnf -y remove 'xorg-x11-drv-nvidia*' 2>/dev/null || true
fi
dnf -y install $PKGS || blad "Instalacja pakietów nie powiodła się\""""

# Jądro zbudowane Clangiem z LTO (np. CachyOS z ThinLTO): własny build modułu
# w instalatorze .run kompiluje bitkod LLVM (CC wykrywa sam z
# CONFIG_CC_VERSION_TEXT), ale jego Makefile ma `LD ?= ld` i przekazuje
# `"LD=$(LD)"` do kbuild, więc linkowanie robi GNU ld i pada
# („/usr/bin/ld: unrecognised emulation mode: llvm"). Dzięki `?=` środowiskowe
# LD=ld.lld ma pierwszeństwo; LLVM=1 przełącza resztę narzędzi kbuild
# (llvm-ar/nm/objcopy), a IGNORE_CC_MISMATCH=1 wyłącza porównanie wersji
# kompilatora, które myli dopisek „, LLD" w CONFIG_CC_VERSION_TEXT takiego
# jądra. Narzędzia LLVM są gwarantowane: nagłówki jądra zbudowanego Clangiem
# zależą od clang/llvm/lld. dkms wykrywa jądra Clang samodzielnie
# (grep CONFIG_CC_IS_CLANG per jądro), dlatego zmienne podajemy przez `env`
# tylko instalatorowi .run, nie eksportujemy do dalszych kroków. Na jądrze
# zbudowanym GCC (zwykły Arch, Debian, Fedora, Mint) warunek nie zachodzi,
# NV_TOOLCHAIN_ENV zostaje pusty i nic się nie zmienia.
_LLVM_KERNEL_ENV = """NV_TOOLCHAIN_ENV=""
if grep -qs '^CONFIG_CC_IS_CLANG=y' "/lib/modules/$(uname -r)/build/.config"; then
  echo "Jądro zbudowane Clangiem/LLVM — moduł będzie budowany toolchainem LLVM"
  NV_TOOLCHAIN_ENV="LLVM=1 LD=ld.lld OBJDUMP=llvm-objdump IGNORE_CC_MISMATCH=1"
fi"""

# Instalator .run buduje moduł DKMS wyłącznie dla działającego jądra. Gdy GRUB
# domyślnie startuje inne jądro (np. instalacja ze starszego, a najnowsze jest
# domyślne), system wstałby bez sterownika i bez nouveau (blacklista) — pulpit
# spadłby na renderowanie CPU. Dobuduj moduł dla każdego jądra z nagłówkami.
_DKMS_ALL_KERNELS = """for k in /lib/modules/*/; do
  k="$(basename "$k")"
  [ "$k" = "$(uname -r)" ] && continue
  [ -e "/lib/modules/$k/build" ] || continue
  dkms autoinstall -k "$k" || echo "UWAGA: budowa modułu DKMS dla jądra $k nie powiodła się"
done
true"""

# Arch: naprawa „pakietów-widm" — pakiet figuruje w bazie pacmana, ale jego
# pliki skasowano z dysku poza pacmanem (np. sprzątanie po sterowniku .run
# innym narzędziem). `pacman -S --needed` takiego pakietu nie tknie, a bez
# bibliotek libnvidia-egl-* platforma GBM EGL nie wstaje i pulpit spada do
# TTY, mimo że instalacja i moduł jądra są poprawne (przypadek CachyOS,
# 2026-07-03: brak libnvidia-egl-gbm.so.1 przy „zainstalowanym" egl-gbm).
# Na zdrowym systemie krok tylko czyta stan (`pacman -Qk`) i niczego nie zmienia.
# Wynik -Qk logowany jest bezwarunkowo dla każdego pakietu: 2026-07-04 krok
# w realnych przebiegach nie zgłosił nic mimo brakujących plików na dysku —
# odtąd log instalacji zawsze dokumentuje zastany stan pakietów.
_ARCH_VERIFY_EGL_PACKAGES = """for p in nvidia-utils egl-gbm egl-wayland egl-wayland2 egl-x11 eglexternalplatform libglvnd; do
  if ! pacman -Qq "$p" >/dev/null 2>&1; then
    echo "Pakiet $p: niezainstalowany"
    continue
  fi
  stan="$(LANG=C pacman -Qk "$p" 2>/dev/null)"
  echo "Pakiet ${stan:-$p: pacman -Qk bez odpowiedzi}"
  if echo "$stan" | grep -qE ', [1-9][0-9]* missing'; then
    echo "Pakiet $p ma brakujące pliki na dysku — przeinstalowuję"
    pacman -S --noconfirm "$p" || blad "Naprawa pakietu $p nie powiodła się"
  fi
done
true"""

# Włączenie sekcji non-free w źródłach APT czystego Debiana (repo i firmware)
_DEBIAN_NONFREE_SECTIONS = (
    "if [ -f /etc/apt/sources.list.d/debian.sources ]; then\n"
    "  sed -i 's/^Components:.*/Components: main contrib non-free non-free-firmware/'"
    " /etc/apt/sources.list.d/debian.sources\nfi\n"
    "if [ -f /etc/apt/sources.list ]; then\n"
    "  sed -i '/^deb /{/non-free/!s/ main/ main contrib non-free non-free-firmware/}'"
    " /etc/apt/sources.list\nfi\n"
    'apt-get update || blad "apt-get update nie powiodło się"'
)

# Usunięcie oficjalnego repozytorium NVIDIA — przy powrocie na pakiety
# z repozytorium Debiana nowsze wersje z repo NVIDIA by je przesłoniły
_REMOVE_NVIDIA_REPO = (
    "apt-get -y purge cuda-keyring 2>/dev/null || true\n"
    "rm -f /etc/apt/sources.list.d/cuda-debian*.list\ntrue"
)

# Wykrycie pakietu jądra na Archu (linux / linux-lts / linux-cachyos itd.),
# by doinstalować pasujące nagłówki potrzebne DKMS
_ARCH_KERNEL_HEADERS = (
    'KERNEL_PKG="$(pacman -Qqo "/usr/lib/modules/$(uname -r)/vmlinuz"'
    ' 2>/dev/null || echo linux)"'
)


# Raport rozruchu: usługa systemd zapisująca po każdym starcie systemu
# diagnostykę grafiki (sterownik, moduły, spójność EGL, błędy dziennika)
# do katalogu logów użytkownika, który uruchomił instalator. Katalog domowy
# zwykle leży poza zakresem przywracania systemu (Timeshift domyślnie omija
# /home, częsty układ z /home na osobnej partycji), więc raport z rozruchu
# zakończonego czarnym ekranem czeka na dysku po powrocie migawką — bez niego
# przywracanie kasuje dziennik i logi menedżera pakietów z feralnego rozruchu.
# Krok wyłącznie zapisuje pliki i włącza usługę CZYTAJĄCĄ stan — na żadnej
# dystrybucji nie zmienia konfiguracji grafiki (zasada: no-op behawioralny).
# Usługa jest OPT-IN (checkbox w Ustawieniach, domyślnie wyłączona): zostaje
# na systemie na stałe, więc wymaga świadomej zgody użytkownika. Przy opcji
# wyłączonej instalacja wykonuje zamiast tego krok sprzątający
# (_BOOT_REPORT_REMOVE_STEP), usuwający usługę z wcześniejszych instalacji.
_BOOT_REPORT_STEP = (
    "Włączanie raportu rozruchu (diagnostyka po restarcie)",
    r"""u="${PKEXEC_UID:-${SUDO_UID:-}}"
home=""
[ -n "$u" ] && home="$(getent passwd "$u" | cut -d: -f6)"
if [ -z "$home" ] || [ ! -d "$home" ]; then
  echo "Nie wykryto użytkownika uruchamiającego instalator — pomijam raport rozruchu"
else
  install -d /usr/local/lib/nvidia-installer
  cat > /usr/local/lib/nvidia-installer/raport-rozruchu.sh <<'RAPORT'
#!/bin/bash
# Zapis raportu stanu grafiki z bieżącego rozruchu (wyłącznie odczyty stanu).
sleep 25
d="$RAPORT_KATALOG"; [ -n "$d" ] || exit 0
mkdir -p "$d"
f="$d/raport-rozruchu-$(date +%Y%m%d-%H%M%S).txt"
{
  echo "=== Raport rozruchu $(date '+%F %T') | jądro: $(uname -r)"
  echo "--- cmdline: $(cat /proc/cmdline)"
  echo "--- GPU (lspci -nnk):"
  command -v lspci >/dev/null && lspci -nnk | grep -iA3 -E 'vga|3d controller'
  echo "--- moduły nvidia/nouveau:"
  lsmod | grep -E '^(nvidia|nouveau)' || echo "(żaden nie załadowany)"
  echo "--- nvidia-smi:"
  if command -v nvidia-smi >/dev/null; then timeout 10 nvidia-smi; else echo "(niedostępne)"; fi
  echo "--- biblioteki EGL wskazywane przez pliki JSON:"
  for j in /usr/share/egl/egl_external_platform.d/*.json /usr/share/glvnd/egl_vendor.d/*.json; do
    [ -e "$j" ] || continue
    lib="$(grep -o '"library_path"[[:space:]]*:[[:space:]]*"[^"]*"' "$j" | cut -d'"' -f4)"
    [ -n "$lib" ] || continue
    case "$lib" in
      /*) if [ -e "$lib" ]; then st="OK  "; else st="BRAK"; fi ;;
      *) if [ -e "/usr/lib/$lib" ] || ldconfig -p 2>/dev/null | grep -qF "$lib"; then st="OK  "; else st="BRAK"; fi ;;
    esac
    echo "$st $j -> $lib"
  done
  if command -v pacman >/dev/null; then
    echo "--- pacman -Qk pakietów NVIDIA/EGL:"
    for p in nvidia-utils egl-gbm egl-wayland egl-wayland2 egl-x11 eglexternalplatform libglvnd; do
      pacman -Qq "$p" >/dev/null 2>&1 && LANG=C pacman -Qk "$p" 2>/dev/null
    done
  fi
  echo "--- błędy jądra dot. grafiki w tym rozruchu:"
  journalctl -b -k -p err --no-pager 2>/dev/null | grep -iE 'nvrm|nvidia|nouveau|drm' | tail -30
  echo "--- kompozytor / sesja graficzna:"
  journalctl -b --no-pager 2>/dev/null | grep -iE 'kwin|gnome-shell|mutter|Xorg|sddm|gdm' \
    | grep -iE 'fail|error|crash|segfault|core|EGL|DRI' | tail -30
} > "$f" 2>&1
chown "$RAPORT_WLASCICIEL" "$f" 2>/dev/null || true
ls -1t "$d"/raport-rozruchu-*.txt 2>/dev/null | tail -n +11 | xargs -r rm -f
RAPORT
  chmod 755 /usr/local/lib/nvidia-installer/raport-rozruchu.sh
  cat > /etc/systemd/system/nvidia-installer-raport.service <<UNIT
[Unit]
Description=Raport rozruchu NVIDIA Driver Installer (diagnostyka grafiki)

[Service]
Type=simple
Environment=RAPORT_KATALOG=$home/.local/share/nvidia-installer-gui/raporty
Environment=RAPORT_WLASCICIEL=$u:$(id -g "$u")
ExecStart=/usr/local/lib/nvidia-installer/raport-rozruchu.sh

[Install]
WantedBy=multi-user.target
UNIT
  systemctl daemon-reload
  if systemctl enable nvidia-installer-raport.service; then
    echo "Raport rozruchu: $home/.local/share/nvidia-installer-gui/raporty"
  else
    echo "UWAGA: nie udało się włączyć usługi raportu rozruchu"
  fi
fi
true""",
)

# Sprzątanie usługi raportu rozruchu, gdy opcja jest wyłączona w Ustawieniach —
# usuwa usługę zostawioną przez wcześniejsze instalacje (do 2026-07-05 była
# włączana bezwarunkowo). Warunek na faktycznym stanie systemu (plik usługi
# istnieje); bez niego krok niczego nie zmienia (no-op na czystym systemie).
_BOOT_REPORT_REMOVE_STEP = (
    "Porządkowanie usługi raportu rozruchu (opcja wyłączona)",
    """if [ -f /etc/systemd/system/nvidia-installer-raport.service ]; then
  echo "Usuwam usługę raportu rozruchu z wcześniejszej instalacji"
  systemctl disable --now nvidia-installer-raport.service 2>/dev/null || true
  rm -f /etc/systemd/system/nvidia-installer-raport.service
  rm -rf /usr/local/lib/nvidia-installer
  systemctl daemon-reload
fi
true""",
)


def _removal_commands(family: str) -> str:
    """Polecenia całkowitego usunięcia sterownika NVIDIA (repo i .run)."""
    # Instalacja z pliku .run zostawia własny dezinstalator — użyj go najpierw
    common = 'if [ -x /usr/bin/nvidia-uninstall ]; then nvidia-uninstall --silent || true; fi\n'
    if family == "arch":
        return common + (
            "pacman -Qq 2>/dev/null | grep -E '^(nvidia|lib32-nvidia|opencl-nvidia)'"
            " | xargs -r pacman -Rns --noconfirm || true\ntrue"
        )
    if family == "fedora":
        return common + (
            "dnf -y remove '*nvidia*' --exclude='nvidia-gpu-firmware' || true\ntrue"
        )
    # debian / ubuntu / mint
    return common + (
        "dpkg -l | awk '/^ii/ && $2 ~ /nvidia/ {print $2}' | grep -v firmware"
        " | xargs -r apt-get -y purge || true\n"
        "apt-get -y autoremove || true\ntrue"
    )


def _initramfs_step(distro: DistroInfo) -> tuple[str, str]:
    """Krok aktualizacji initramfs poleceniem właściwym dla dystrybucji."""
    return (
        "Aktualizacja initramfs",
        f'{distro.initramfs_cmd} || blad "Aktualizacja initramfs nie powiodła się"',
    )


# ---------------------------------------------------------------------------
# Kroki dla poszczególnych metod instalacji
# ---------------------------------------------------------------------------

def _steps_repo(opts: InstallOptions, keyring: str = "") -> list[tuple[str, str]]:
    """Instalacja z repozytorium dystrybucji (lub oficjalnego repo NVIDIA)."""
    fam = opts.distro.family
    steps: list[tuple[str, str]] = []

    # Sterownik z pliku .run trzeba usunąć PRZED instalacją pakietów.
    # Inaczej mechanizmy dystrybucji (np. nvidia-installer-cleanup na
    # Ubuntu) odpalą nvidia-uninstall w trakcie rozpakowywania i skasują
    # pliki dopiero co wgrane przez pakiety (m.in. glvnd 10_nvidia.json),
    # przez co pulpit spadnie na renderowanie programowe CPU.
    steps.append((
        "Usuwanie sterownika z pliku .run (jeśli obecny)",
        "if [ -x /usr/bin/nvidia-uninstall ]; then"
        " nvidia-uninstall --silent || true; fi\ntrue",
    ))

    if fam == "arch":
        pkg = "nvidia-open-dkms" if opts.open_modules else "nvidia-dkms"
        steps.append((
            "Usuwanie konfliktującej odmiany sterownika",
            "for p in nvidia nvidia-lts nvidia-open nvidia-open-dkms nvidia-dkms; do\n"
            '  pacman -Qq "$p" >/dev/null 2>&1 && pacman -Rdd --noconfirm "$p"\n'
            "done; true",
        ))
        steps.append((
            "Instalacja sterownika z repozytorium (pełna aktualizacja systemu)",
            f"{_ARCH_KERNEL_HEADERS}\n"
            f"pacman -Syu --noconfirm --needed {pkg} nvidia-utils nvidia-settings"
            ' "${KERNEL_PKG}-headers"'
            ' || blad "Instalacja pakietów nie powiodła się"',
        ))
        steps.append((
            "Kontrola integralności pakietów EGL (naprawa brakujących plików)",
            _ARCH_VERIFY_EGL_PACKAGES,
        ))

    elif fam == "fedora":
        # RPMFusion tylko, gdy żadne włączone repozytorium nie dostarcza
        # jeszcze akmod-nvidia — dystrybucje z własnym repo sterownika
        # (np. Nobara) zostają przy swoim, czysta Fedora dostaje RPMFusion
        steps.append((
            "Włączanie repozytorium RPMFusion (free + nonfree)",
            "if dnf -q repoquery --qf '%{name}\\n' akmod-nvidia 2>/dev/null | grep -q .; then\n"
            '  echo "Repozytorium ze sterownikiem NVIDIA już dostępne — pomijam RPMFusion"\n'
            "else\n"
            '  dnf -y install'
            ' "https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm"'
            ' "https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-$(rpm -E %fedora).noarch.rpm"'
            " || true\nfi\ntrue",
        ))
        if opts.open_modules:
            # Makro RPMFusion przełączające akmod-nvidia na moduły otwarte;
            # musi istnieć zanim akmods zbuduje moduł
            steps.append((
                "Włączanie otwartych modułów jądra (makro RPMFusion)",
                "printf '%%_with_kmod_nvidia_open 1\\n' > /etc/rpm/macros.nvidia-kmod"
                ' || blad "Nie udało się zapisać makra RPM"',
            ))
        steps.append((
            "Instalacja sterownika (akmod-nvidia)",
            _FEDORA_REPO_INSTALL,
        ))
        steps.append((
            "Budowanie modułu jądra (akmods — może potrwać kilka minut)",
            'akmods --force || blad "Budowanie modułu jądra nie powiodło się"',
        ))

    else:  # rodzina debian
        if opts.distro.ubuntu_based:
            pkg = opts.repo_package or "nvidia-driver-580"
            steps.append((
                "Odświeżanie listy pakietów",
                'apt-get update || blad "apt-get update nie powiodło się"',
            ))
            steps.append((
                f"Instalacja sterownika ({pkg})",
                f'apt-get -y install {pkg} || blad "Instalacja pakietu {pkg} nie powiodła się"',
            ))
        elif opts.repo_source == "nvidia":
            # Czysty Debian, oficjalne repozytorium NVIDIA — jedyne źródło
            # pakietowe dla kart RTX 50xx (repo Debiana kończy się na 550).
            # Pakiety Debiana i NVIDIA nie mogą się mieszać, stąd czyszczenie.
            pkg = "nvidia-open" if opts.open_modules else "cuda-drivers"
            steps.append((
                "Odinstalowanie sterownika z repozytorium Debiana (jeśli obecny)",
                _removal_commands("debian"),
            ))
            steps.append((
                "Dodawanie oficjalnego repozytorium NVIDIA (cuda-keyring)",
                f'apt-get -y install "{keyring}"'
                ' || blad "Instalacja pakietu cuda-keyring nie powiodła się"\n'
                'apt-get update || blad "apt-get update nie powiodło się"',
            ))
            steps.append((
                f"Instalacja sterownika z repozytorium NVIDIA ({pkg})",
                f"apt-get -y install linux-headers-amd64 {pkg}"
                f' || blad "Instalacja pakietu {pkg} nie powiodła się"',
            ))
        else:
            steps.append((
                "Odinstalowanie sterownika z repozytorium NVIDIA (jeśli obecny)",
                _removal_commands("debian") + "\n" + _REMOVE_NVIDIA_REPO,
            ))
            steps.append((
                "Włączanie sekcji contrib / non-free / non-free-firmware",
                # Debian może używać klasycznego sources.list lub formatu deb822
                _DEBIAN_NONFREE_SECTIONS,
            ))
            steps.append((
                "Instalacja sterownika (nvidia-driver)",
                "apt-get -y install nvidia-driver firmware-misc-nonfree"
                " linux-headers-amd64"
                ' || blad "Instalacja pakietów nie powiodła się"',
            ))

    # Wspólna konfiguracja po instalacji z repozytorium
    steps.append(("Konfiguracja modprobe (blokada nouveau, modeset)", _MODPROBE_CONFIG))
    steps.append(_initramfs_step(opts.distro))
    return steps


def _steps_nvk(opts: InstallOptions) -> list[tuple[str, str]]:
    """Przejście na otwarty sterownik NVK / Mesa (nouveau)."""
    fam = opts.distro.family
    extra: list[tuple[str, str]] = []  # kroki dodatkowe zależne od dystrybucji
    if fam == "arch":
        install = (
            "pacman -Syu --noconfirm --needed mesa vulkan-nouveau vulkan-icd-loader"
            ' vulkan-tools || blad "Instalacja pakietów Mesa nie powiodła się"'
        )
        firmware = (
            "pacman -S --noconfirm --needed linux-firmware"
            ' || blad "Instalacja pakietu linux-firmware nie powiodła się"'
        )
    elif fam == "fedora":
        extra.append((
            "Uzupełnianie modułu nouveau (pakiet kernel-modules)",
            _NOUVEAU_KERNEL_MODULES_FEDORA,
        ))
        install = (
            "dnf -y install mesa-vulkan-drivers mesa-dri-drivers vulkan-tools"
            ' || blad "Instalacja pakietów Mesa nie powiodła się"'
        )
        firmware = (
            "dnf -y install nvidia-gpu-firmware"
            ' || blad "Instalacja pakietu nvidia-gpu-firmware nie powiodła się"'
        )
    elif opts.use_backports and not opts.distro.ubuntu_based:
        # Czysty Debian z kartą RTX 50xx (Blackwell): stabilne wydanie jest
        # za stare w trzech miejscach naraz — jądro (nouveau bez GB20x),
        # Mesa < 25.2 (NVK bez Blackwella) i firmware bez GSP r570.
        # Wszystkie trzy składniki pochodzą z oficjalnych backportów.
        extra.append((
            "Włączanie oficjalnych backportów Debiana",
            ". /etc/os-release\n"
            'BP="${VERSION_CODENAME}-backports"\n'
            'if ! apt-cache policy | grep -q "$BP"; then\n'
            '  echo "deb http://deb.debian.org/debian ${BP} main contrib'
            ' non-free non-free-firmware"'
            " > /etc/apt/sources.list.d/nvidia-installer-backports.list\n"
            "fi\n" + _DEBIAN_NONFREE_SECTIONS,
        ))
        extra.append((
            "Instalacja nowszego jądra z backportów (wymagane dla RTX 50xx)",
            'apt-get -y -t "$BP" install linux-image-amd64'
            ' || blad "Instalacja jądra z backportów nie powiodła się"',
        ))
        # libgl1-mesa-dri z tej samej wersji co sterownik Vulkan —
        # mieszanie wersji Mesy (GL 25.0 + Vulkan 25.2) psuje pulpit
        install = (
            'apt-get -y -t "$BP" install mesa-vulkan-drivers libgl1-mesa-dri'
            " mesa-utils vulkan-tools"
            ' || blad "Instalacja pakietów Mesa z backportów nie powiodła się"'
        )
        firmware = (
            'apt-get -y -t "$BP" install firmware-nouveau'
            ' || apt-get -y -t "$BP" install firmware-misc-nonfree'
            ' || blad "Instalacja firmware nouveau nie powiodła się"'
        )
    else:
        install = (
            "apt-get update || true\n"
            "apt-get -y install mesa-vulkan-drivers mesa-utils vulkan-tools"
            ' || blad "Instalacja pakietów Mesa nie powiodła się"'
        )
        if opts.distro.ubuntu_based:
            firmware = (
                "apt-get -y install linux-firmware"
                ' || blad "Instalacja pakietu linux-firmware nie powiodła się"'
            )
        else:
            # Czysty Debian: firmware nouveau leży w sekcji non-free-firmware;
            # starsze wydania nie znają pakietu firmware-nouveau
            firmware = (
                _DEBIAN_NONFREE_SECTIONS + "\n"
                "apt-get -y install firmware-nouveau"
                " || apt-get -y install firmware-misc-nonfree"
                ' || blad "Instalacja firmware nouveau nie powiodła się"'
            )
    return [
        ("Odinstalowanie sterownika NVIDIA (jeśli obecny)", _removal_commands(fam)),
        ("Usuwanie blokady nouveau i konfiguracji NVIDIA", _REMOVE_MODPROBE_CONFIG),
        ("Usuwanie wymuszeń NVIDIA w zmiennych środowiskowych", _REMOVE_GL_ENV),
        ("Usuwanie parametrów nvidia-drm z konfiguracji GRUB", _REMOVE_KERNEL_PARAMS),
        *extra,
        ("Instalacja sterownika NVK / Mesa", install),
        (
            "Instalacja firmware GPU (GSP — wymagany na kartach RTX)",
            firmware + "\n" + _GSP_FIRMWARE_CHECK + "\n" + _NOUVEAU_MODULE_CHECK,
        ),
        _initramfs_step(opts.distro),
    ]


def _steps_run(opts: InstallOptions, runfile: str) -> list[tuple[str, str]]:
    """Instalacja z pobranego pliku .run NVIDIA."""
    fam = opts.distro.family
    if fam == "arch":
        deps = (
            f"{_ARCH_KERNEL_HEADERS}\n"
            "pacman -Syu --noconfirm --needed base-devel dkms"
            ' "${KERNEL_PKG}-headers"'
            ' || blad "Instalacja zależności nie powiodła się"'
        )
    elif fam == "fedora":
        deps = (
            "dnf -y install gcc make dkms kernel-devel kernel-headers"
            " libglvnd-devel libglvnd-glx libglvnd-opengl"
            ' || blad "Instalacja zależności nie powiodła się"'
        )
    else:
        deps = (
            'apt-get update || blad "apt-get update nie powiodło się"\n'
            'apt-get -y install build-essential dkms "linux-headers-$(uname -r)"'
            " libglvnd-dev pkg-config"
            ' || blad "Instalacja zależności nie powiodła się"'
        )

    # Flaga otwartych modułów zależna od wersji sterownika
    open_flag = (
        nvidia_versions.open_module_flag(opts.run_version) if opts.open_modules else ""
    )
    # Załadowany moduł nvidia (instalacja .run przy działającym sterowniku,
    # np. zmiana wersji ze sterownika z repozytorium): instalator 595.84 pyta
    # wtedy o pominięcie kontroli i w trybie --silent domyślnie PRZERYWA
    # („Answer: Abort installation" — przypadek EndeavourOS 2026-07-05).
    # Zgodę wyraża z góry --allow-installation-with-running-driver; starsze
    # instalatory (m.in. gałęzie Legacy) nie znają tej flagi, dlatego warunek
    # sprawdza faktyczny stan (moduł w /proc/modules) ORAZ możliwości
    # instalatora (flaga w --advanced-options). Przy nieaktywnym module
    # nvidia — ścieżka z nouveau/NVK, na której zaliczono dotychczasowe
    # cykle — zmienna zostaje pusta i polecenie jest jak dotychczas.
    allow_running = (
        'NV_ALLOW_RUNNING=""\n'
        "if grep -q '^nvidia ' /proc/modules"
        f' && sh "{runfile}" --advanced-options 2>/dev/null'
        " | grep -q -- --allow-installation-with-running-driver; then\n"
        '  echo "Moduł nvidia jest załadowany — przekazuję instalatorowi zgodę'
        ' na instalację przy działającym sterowniku"\n'
        '  NV_ALLOW_RUNNING="--allow-installation-with-running-driver"\n'
        "fi"
    )
    return [
        ("Instalacja zależności do budowania modułu jądra", deps),
        ("Odinstalowanie poprzednich sterowników", _removal_commands(fam)),
        ("Konfiguracja modprobe (blokada nouveau, modeset)", _MODPROBE_CONFIG),
        (
            "Instalacja sterownika NVIDIA z pliku .run (może potrwać kilka minut)",
            # Instalacja odbywa się z działającego pulpitu, więc nouveau (lub
            # stary moduł nvidia) wciąż trzyma kartę: --no-nouveau-check nie
            # przerywa wtedy instalacji, a --skip-module-load pomija próbne
            # ładowanie modułu, które by się nie powiodło. Blacklista nouveau
            # jest już zapisana, więc po restarcie kartę przejmie nvidia.
            _LLVM_KERNEL_ENV + "\n" + allow_running + "\n"
            f'env $NV_TOOLCHAIN_ENV sh "{runfile}" --silent --accept-license --dkms --no-x-check'
            f' --no-nouveau-check --skip-module-load $NV_ALLOW_RUNNING{open_flag}'
            ' || blad "Instalator NVIDIA zwrócił błąd — szczegóły w /var/log/nvidia-installer.log"',
        ),
        ("Budowanie modułu DKMS dla pozostałych jąder", _DKMS_ALL_KERNELS),
        _initramfs_step(opts.distro),
    ]


def build_plan(
    opts: InstallOptions, runfile: str = "", keyring: str = ""
) -> tuple[list[str], str]:
    """Buduje plan instalacji: (lista etykiet kroków, treść skryptu bash)."""
    if opts.method == "repo":
        steps = _steps_repo(opts, keyring)
    elif opts.method == "nvk":
        steps = _steps_nvk(opts)
    elif opts.method == "run":
        steps = _steps_run(opts, runfile)
    else:
        raise ValueError(f"Nieznana metoda instalacji: {opts.method}")

    # Wspólny, czysto diagnostyczny krok na końcu każdej metody — patrz
    # komentarz przy _BOOT_REPORT_STEP. Opt-in: przy opcji wyłączonej
    # instalacja sprząta usługę z wcześniejszych instalacji.
    steps.append(_BOOT_REPORT_STEP if opts.boot_report else _BOOT_REPORT_REMOVE_STEP)

    lines = [_SCRIPT_HEADER]
    for label, cmds in steps:
        lines.append(f'krok "{label}"')
        lines.append(cmds)
    lines.append('echo "@SUKCES@"')
    return [s[0] for s in steps], "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Wątek wykonujący instalację (pobieranie + skrypt przez pkexec)
# ---------------------------------------------------------------------------

class InstallThread(QThread):
    """Wykonuje całą instalację w tle, raportując postęp sygnałami Qt."""

    sig_log = Signal(str)            # kolejna linia logu
    sig_step = Signal(int, int, str)  # numer kroku, liczba kroków, etykieta
    sig_download = Signal(int)       # procent pobierania pliku .run
    sig_finished = Signal(bool, str)  # sukces?, komunikat końcowy

    def __init__(self, opts: InstallOptions, sudo_password: str = "", parent=None):
        super().__init__(parent)
        self.opts = opts
        # Awaryjnie, gdy w systemie nie ma pkexec: hasło do sudo -S,
        # pobrane i zweryfikowane wcześniej przez GUI (nie trafia do logów)
        self._sudo_password = sudo_password

    # ---- pobieranie pliku .run -------------------------------------------
    def _verify_runfile(self, path: str) -> bool:
        """Sprawdza wbudowaną sumę kontrolną instalatora .run (bez roota).

        Wyłapuje pliki ucięte w trakcie pobierania (np. twarde zabicie
        programu zostawia w cache plik > 50 MB wyglądający na kompletny)
        oraz uszkodzone lub podmienione po drodze.
        """
        self.sig_log.emit(tr("Sprawdzanie integralności pliku .run..."))
        code, _, _ = utils.run(["sh", path, "--check"], timeout=300)
        return code == 0

    def _download_runfile(self) -> str:
        """Pobiera plik .run do pamięci podręcznej; zwraca ścieżkę pliku."""
        import requests

        ver = self.opts.run_version
        url = nvidia_versions.download_url(ver)
        dest = utils.CACHE_DIR / f"NVIDIA-Linux-x86_64-{ver}.run"

        # Plik już pobrany wcześniej — użyj kopii, jeśli przechodzi kontrolę
        if dest.exists() and dest.stat().st_size > 50_000_000:
            if self._verify_runfile(str(dest)):
                self.sig_log.emit(
                    tr("Plik {n} już pobrany — używam kopii lokalnej")
                    .format(n=dest.name)
                )
                self.sig_download.emit(100)
                return str(dest)
            self.sig_log.emit(tr("Kopia lokalna uszkodzona — pobieram ponownie"))
            dest.unlink(missing_ok=True)

        self.sig_log.emit(tr("Pobieranie:") + f" {url}")
        try:
            r = requests.get(
                url,
                stream=True,
                timeout=60,
                headers={"User-Agent": "Mozilla/5.0 (nvidia-installer-gui)"},
            )
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            done = 0
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=256 * 1024):
                    f.write(chunk)
                    done += len(chunk)
                    if total:
                        self.sig_download.emit(int(done * 100 / total))
        except Exception:
            # Nie zostawiamy niekompletnego pliku w pamięci podręcznej
            dest.unlink(missing_ok=True)
            raise
        if not self._verify_runfile(str(dest)):
            dest.unlink(missing_ok=True)
            raise RuntimeError(
                tr("Pobrany plik .run nie przechodzi kontroli integralności"
                   " — spróbuj ponownie")
            )
        self.sig_log.emit(
            tr("Pobrano:") + f" {dest} ({dest.stat().st_size // (1024*1024)} MB)"
        )
        return str(dest)

    def _download_keyring(self) -> str:
        """Pobiera pakiet cuda-keyring (repo NVIDIA); zwraca ścieżkę pliku."""
        import requests

        url = nvidia_versions.keyring_url(self.opts.distro)
        dest = utils.CACHE_DIR / url.rsplit("/", 1)[-1]
        if dest.exists() and dest.stat().st_size > 1000:
            self.sig_log.emit(
                tr("Plik {n} już pobrany — używam kopii lokalnej").format(n=dest.name)
            )
            return str(dest)
        self.sig_log.emit(tr("Pobieranie:") + f" {url}")
        try:
            r = requests.get(
                url,
                timeout=60,
                headers={"User-Agent": "Mozilla/5.0 (nvidia-installer-gui)"},
            )
            r.raise_for_status()
            dest.write_bytes(r.content)
        except Exception:
            dest.unlink(missing_ok=True)
            raise
        return str(dest)

    # ---- główna praca wątku ----------------------------------------------
    def run(self):  # noqa: D102 — metoda QThread
        log_lines: list[str] = []

        def log(text: str) -> None:
            log_lines.append(text)
            self.sig_log.emit(text)

        ok = False
        err_msg = ""
        try:
            if not utils.is_linux():
                raise RuntimeError(tr("Instalacja działa tylko na Linuksie"))
            use_sudo = False
            if not utils.which("pkexec"):
                # Awaryjna ścieżka bez polkita: sudo z hasłem od GUI
                if utils.which("sudo") and self._sudo_password:
                    use_sudo = True
                else:
                    raise RuntimeError(
                        tr("Brak poleceń pkexec i sudo — zainstaluj pakiet pkexec"
                           " (polkit) lub sudo")
                    )

            # 1. Metoda .run wymaga wcześniejszego pobrania instalatora,
            #    a repo NVIDIA na Debianie — pakietu cuda-keyring
            runfile = keyring = ""
            if self.opts.method == "run":
                log(tr("Wersja sterownika:") + f" {self.opts.run_version}")
                runfile = self._download_runfile()
            elif self.opts.method == "repo" and self.opts.repo_source == "nvidia":
                keyring = self._download_keyring()

            # 2. Wygenerowanie skryptu instalacyjnego
            steps, script = build_plan(self.opts, runfile, keyring)
            log(tr("Liczba kroków:") + f" {len(steps)}")

            # 3. Uruchomienie jako root — jedno pytanie o hasło.
            #    Standardowo pkexec (okno polkita): skrypt idzie potokiem
            #    wprost do roota (_ROOT_RUNNER), bez pliku w /tmp, którego
            #    treść inny proces mógłby podmienić przed wykonaniem.
            #    Awaryjnie sudo -S: potok przenosi hasło (-p "" wyłącza
            #    tekstowy monit), więc skrypt musi iść plikiem tymczasowym —
            #    ścieżka przetestowana na Debianie bez polkita, zostaje.
            if use_sudo:
                with tempfile.NamedTemporaryFile(
                    "w", suffix=".sh", prefix="nvidia-installer-",
                    delete=False, encoding="utf-8",
                ) as f:
                    f.write(script)
                    script_path = f.name
                os.chmod(script_path, 0o700)
                log(tr("Skrypt instalacyjny:") + f" {script_path}")
                cmd = ["sudo", "-S", "-k", "-p", "", "bash", script_path]
            else:
                log(tr("Skrypt instalacyjny przekazany potokiem (bez pliku w /tmp)"))
                cmd = ["pkexec", "bash", "-c", _ROOT_RUNNER]
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            if use_sudo:
                proc.stdin.write(self._sudo_password + "\n")
                proc.stdin.flush()
                proc.stdin.close()
            else:
                # Skrypt mieści się w buforze potoku — zapis nie zablokuje
                # wątku nawet, gdy okno autoryzacji polkita czeka na hasło
                proc.stdin.write(script)
                proc.stdin.close()
            idx = 0
            success_marker = False
            for line in proc.stdout:
                line = line.rstrip("\n")
                if line.startswith("@KROK@"):
                    idx += 1
                    label = line[len("@KROK@"):].strip()
                    self.sig_step.emit(idx, len(steps), label)
                elif line.startswith("@BLAD@"):
                    err_msg = line[len("@BLAD@"):].strip()
                elif line.strip() == "@SUKCES@":
                    success_marker = True
                log(line)
            code = proc.wait()
            ok = code == 0 and success_marker

            if not ok and not err_msg:
                if code in (126, 127):
                    err_msg = tr("Anulowano autoryzację administratora (pkexec)")
                else:
                    err_msg = tr("Skrypt zakończył się kodem") + f" {code}"
        except Exception as e:
            err_msg = str(e)
            log(tr("BŁĄD:") + f" {err_msg}")

        # 4. Wpis do historii instalacji z pełnym logiem
        wersja = (
            self.opts.run_version
            or self.opts.repo_package
            or ("NVK / Mesa" if self.opts.method == "nvk"
                else "repozytorium NVIDIA" if self.opts.repo_source == "nvidia"
                else "repozytorium")
        )
        try:
            history.add_entry(
                metoda=self.opts.method,
                wersja=wersja,
                dystrybucja=self.opts.distro.name,
                status="sukces" if ok else "błąd",
                log_text="\n".join(log_lines),
            )
        except Exception:
            pass  # problem z zapisem historii nie może zepsuć wyniku

        self.sig_finished.emit(ok, err_msg)
