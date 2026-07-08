# -*- coding: utf-8 -*-
"""Diagnostyka systemu pod kątem sterownika NVIDIA.

Każda kontrola zwraca CheckResult ze statusem:
  ok    — wszystko w porządku
  uwaga — działa, ale coś wymaga uwagi (np. Secure Boot)
  blad  — problem uniemożliwiający poprawną pracę sterownika
  info  — informacja neutralna
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime

from app.i18n import tr

from .distro import DistroInfo, detect_distro
from .gpu import (
    detect_gpus,
    detect_installed_driver,
    driver_bound,
    driver_description,
    is_turing_or_newer,
)
from .utils import is_linux, read_file, run, which


@dataclass
class CheckResult:
    """Wynik pojedynczej kontroli diagnostycznej."""

    kategoria: str  # nazwa kontroli, np. "Secure Boot"
    status: str     # "ok" | "uwaga" | "blad" | "info"
    opis: str       # szczegóły w języku interfejsu (tr() przy tworzeniu)


def _check_gpu() -> CheckResult:
    gpus = detect_gpus()
    if gpus:
        nazwy = ", ".join(g.name for g in gpus)
        return CheckResult(
            tr("Karta graficzna NVIDIA"), "ok", tr("Wykryto:") + f" {nazwy}"
        )
    return CheckResult(
        tr("Karta graficzna NVIDIA"), "blad",
        tr("Nie wykryto karty NVIDIA (lspci) — sterownik nie ma czego obsługiwać"),
    )


def _check_driver() -> CheckResult:
    info = detect_installed_driver()
    if info["typ"]:
        return CheckResult(
            tr("Zainstalowany sterownik"), "ok", driver_description(info)
        )
    return CheckResult(
        tr("Zainstalowany sterownik"), "uwaga",
        tr("Brak aktywnego sterownika NVIDIA (ani proprietary, ani nouveau)"),
    )


def _check_module_loaded() -> CheckResult:
    modules = read_file("/proc/modules")
    # Sterownik musi nie tylko być załadowany, ale też przejąć kartę —
    # moduł bez przypiętego urządzenia oznacza nieudany probe (karta bez
    # sterownika, pulpit działa wtedy na renderowaniu programowym CPU)
    if re.search(r"^nvidia\s", modules, re.M):
        if driver_bound("nvidia"):
            return CheckResult(
                tr("Moduł jądra"), "ok", tr("Moduł nvidia obsługuje kartę")
            )
        return CheckResult(
            tr("Moduł jądra"), "blad",
            tr("Moduł nvidia jest załadowany, ale NIE przejął karty — sterownik nie"
               " działa, szczegóły w kontroli „Log jądra”"),
        )
    if re.search(r"^nouveau\s", modules, re.M):
        if driver_bound("nouveau"):
            return CheckResult(
                tr("Moduł jądra"), "ok", tr("Moduł nouveau obsługuje kartę (NVK)")
            )
        return CheckResult(
            tr("Moduł jądra"), "blad",
            tr("Moduł nouveau jest załadowany, ale NIE przejął karty — sterownik nie"
               " działa (na kartach RTX typowa przyczyna to brak firmware GSP),"
               " szczegóły w kontroli „Log jądra”"),
        )
    return CheckResult(
        tr("Moduł jądra"), "uwaga",
        tr("Żaden moduł graficzny NVIDIA nie jest załadowany — możliwy brak"
           " sterownika lub konieczny restart"),
    )


def _check_nvidia_smi() -> CheckResult:
    code, out, err = run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"])
    if code == 0:
        return CheckResult(
            "nvidia-smi", "ok", tr("Działa — GPU:") + f" {out.splitlines()[0]}"
        )
    if code == 127:
        return CheckResult(
            "nvidia-smi", "info",
            tr("Narzędzie nvidia-smi niezainstalowane (normalne przy NVK/nouveau)"),
        )
    return CheckResult(
        "nvidia-smi", "uwaga",
        tr("nvidia-smi zwraca błąd:") + f" {err or out or tr('brak komunikatu')}",
    )


def _check_version_match() -> CheckResult:
    """Niezgodność wersji modułu jądra i bibliotek zdarza się po aktualizacji."""
    kernel_ver = read_file("/sys/module/nvidia/version").strip()
    if not kernel_ver:
        return CheckResult(
            tr("Zgodność wersji sterownika"), "info",
            tr("Moduł nvidia nieaktywny — pominięto"),
        )
    code, out, _ = run(
        ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"]
    )
    user_ver = out.splitlines()[0].strip() if code == 0 and out else ""
    if user_ver and user_ver != kernel_ver:
        return CheckResult(
            tr("Zgodność wersji sterownika"), "blad",
            tr("Moduł jądra ({k}) ≠ biblioteki ({u}) — wymagany restart lub"
               " ponowna instalacja").format(k=kernel_ver, u=user_ver),
        )
    return CheckResult(
        tr("Zgodność wersji sterownika"), "ok",
        tr("Moduł i biblioteki zgodne") + f" ({kernel_ver})",
    )


def _check_secure_boot() -> CheckResult:
    if which("mokutil"):
        code, out, _ = run(["mokutil", "--sb-state"])
        if code == 0:
            if "enabled" in out.lower():
                return CheckResult(
                    "Secure Boot", "uwaga",
                    tr("Secure Boot WŁĄCZONY — niepodpisane moduły DKMS nie załadują"
                       " się. Wyłącz Secure Boot w UEFI albo podpisz moduł (MOK)."),
                )
            return CheckResult("Secure Boot", "ok", tr("Secure Boot wyłączony"))
    if not os.path.isdir("/sys/firmware/efi"):
        return CheckResult(
            "Secure Boot", "ok", tr("System uruchomiony w trybie BIOS/CSM")
        )
    return CheckResult(
        "Secure Boot", "info", tr("Nie można ustalić stanu (brak narzędzia mokutil)")
    )


def _check_kernel_headers() -> CheckResult:
    """DKMS wymaga nagłówków dokładnie dla działającego jądra."""
    _, uname, _ = run(["uname", "-r"])
    build_dir = f"/lib/modules/{uname}/build"
    if uname and os.path.isdir(build_dir):
        return CheckResult(
            tr("Nagłówki jądra"), "ok", tr("Zainstalowane dla jądra") + f" {uname}"
        )
    return CheckResult(
        tr("Nagłówki jądra"), "uwaga",
        tr("Brak nagłówków dla jądra {k} — program doinstaluje je podczas"
           " instalacji sterownika").format(k=uname or "?"),
    )


def _check_nouveau_blacklist() -> CheckResult:
    for path in (
        "/etc/modprobe.d/blacklist-nouveau.conf",
        "/usr/lib/modprobe.d/nvidia-installer-disable-nouveau.conf",
        "/etc/modprobe.d/nvidia-installer-disable-nouveau.conf",
    ):
        if "blacklist nouveau" in read_file(path):
            return CheckResult(
                tr("Blokada nouveau"), "ok",
                tr("Aktywna (plik {p})").format(p=path),
            )
    return CheckResult(
        tr("Blokada nouveau"), "info",
        tr("Brak blokady nouveau (wymagana tylko dla sterownika proprietary)"),
    )


def _check_gsp_firmware() -> CheckResult:
    """Nouveau/NVK na kartach RTX (Turing+) wymaga firmware GSP od NVIDII.

    Firmware dostarcza pakiet dystrybucji (linux-firmware / firmware-nouveau /
    nvidia-gpu-firmware). Bez niego probe nouveau kończy się błędem i karta
    zostaje bez sterownika.
    """
    gpus = detect_gpus()
    if not gpus or not any(is_turing_or_newer(g.name) for g in gpus):
        return CheckResult(
            "Firmware GSP", "info", tr("Karta nie wymaga firmware GSP — pominięto")
        )
    if re.search(r"^nvidia\s", read_file("/proc/modules"), re.M):
        return CheckResult(
            "Firmware GSP", "info",
            tr("Aktywny sterownik NVIDIA — firmware z linux-firmware nieużywany"),
        )
    import glob
    if glob.glob("/lib/firmware/nvidia/*/gsp*") or glob.glob(
        "/usr/lib/firmware/nvidia/*/gsp*"
    ):
        return CheckResult(
            "Firmware GSP", "ok",
            tr("Pliki firmware GSP obecne w /lib/firmware/nvidia"),
        )
    return CheckResult(
        "Firmware GSP", "blad",
        tr("Brak firmware GSP w /lib/firmware/nvidia — nouveau/NVK nie wystartuje"
           " na tej karcie. Zainstaluj pakiet linux-firmware (program zrobi to"
           " przy instalacji NVK)."),
    )


# Zmienne wymuszające sterownik NVIDIA w bibliotekach graficznych (GL/EGL/VA)
_GL_ENV_KEYS = (
    "GBM_BACKEND",
    "__GLX_VENDOR_LIBRARY_NAME",
    "__EGL_VENDOR_LIBRARY_FILENAMES",
    "__EGL_VENDOR_LIBRARY_FILELIST",
    "LIBVA_DRIVER_NAME",
    "VDPAU_DRIVER",
)


def _check_gl_env() -> CheckResult:
    """Wykrywa wymuszenie sterownika NVIDIA w zmiennych środowiskowych.

    Takie wpisy (np. w /etc/environment) zostawiają inne narzędzia. Gdy
    sterownika NVIDIA nie ma w systemie, wymuszenia psują inicjalizację
    EGL i pulpit spada na renderowanie programowe (CPU) — objaw: tnący
    kursor i animacje mimo działającego nouveau/NVK.
    """
    import glob
    paths = ["/etc/environment"] + sorted(glob.glob("/etc/environment.d/*.conf"))
    found: list[str] = []
    for path in paths:
        for line in read_file(path).splitlines():
            s = line.strip()
            if s.startswith(tuple(k + "=" for k in _GL_ENV_KEYS)) and "nvidia" in s.lower():
                found.append(f"{path}: {s}")
    if not found:
        return CheckResult(
            tr("Zmienne środowiskowe GL"), "ok",
            tr("Brak wymuszeń sterownika NVIDIA w /etc/environment*"),
        )
    if os.path.exists("/usr/share/glvnd/egl_vendor.d/10_nvidia.json"):
        return CheckResult(
            tr("Zmienne środowiskowe GL"), "uwaga",
            tr("Wpisy wymuszające sterownik NVIDIA ({n}) — teraz działają, ale po"
               " przejściu na NVK zepsują pulpit. Przykład:").format(n=len(found))
            + " " + found[0],
        )
    return CheckResult(
        tr("Zmienne środowiskowe GL"), "blad",
        tr("Zmienne wymuszają sterownik NVIDIA, którego nie ma w systemie —"
           " pulpit działa na renderowaniu programowym (CPU). Usuń wpisy:")
        + " " + "; ".join(found[:3]),
    )


def _check_glvnd() -> CheckResult:
    """Sprawdza plik glvnd EGL sterownika NVIDIA (10_nvidia.json).

    Bez niego biblioteka EGL nie znajduje sterownika NVIDIA i pulpit
    spada na renderowanie programowe (CPU), mimo że nvidia-smi działa.
    Plik potrafi zniknąć, gdy nvidia-uninstall z instalacji .run wykona
    się w trakcie instalowania pakietów z repozytorium.
    """
    if not re.search(r"^nvidia\s", read_file("/proc/modules"), re.M):
        return CheckResult(
            tr("Plik glvnd (EGL)"), "info",
            tr("Sterownik NVIDIA nieaktywny — pominięto"),
        )
    if os.path.exists("/usr/share/glvnd/egl_vendor.d/10_nvidia.json"):
        return CheckResult(
            tr("Plik glvnd (EGL)"), "ok",
            tr("10_nvidia.json obecny — EGL znajdzie sterownik"),
        )
    return CheckResult(
        tr("Plik glvnd (EGL)"), "blad",
        tr("Brak /usr/share/glvnd/egl_vendor.d/10_nvidia.json — pulpit działa na"
           " renderowaniu CPU. Napraw przeinstalowując pakiety sterownika"
           " (np. apt install --reinstall wszystkich pakietów nvidia)."),
    )


def _check_modeset() -> CheckResult:
    val = read_file("/sys/module/nvidia_drm/parameters/modeset").strip()
    if val == "Y":
        return CheckResult(
            "KMS (modeset)", "ok", tr("nvidia_drm modeset=1 — Wayland OK")
        )
    if val == "N":
        return CheckResult(
            "KMS (modeset)", "uwaga",
            tr("nvidia_drm modeset wyłączony — Wayland może nie działać poprawnie"),
        )
    # Parametr nieodczytany: moduł nieaktywny albo plik w /sys dostępny tylko
    # dla roota (tak jest na nowszych sterownikach) — rozróżnij te przypadki
    if not re.search(r"^nvidia_drm\s", read_file("/proc/modules"), re.M):
        return CheckResult(
            "KMS (modeset)", "info", tr("Moduł nvidia_drm nieaktywny — pominięto")
        )
    import glob
    conf_files = glob.glob("/etc/modprobe.d/*.conf") + glob.glob(
        "/usr/lib/modprobe.d/*.conf"
    )
    conf_has_modeset = any(
        re.search(r"^\s*options\s+nvidia[-_]drm\s+.*modeset=1", read_file(p), re.M)
        for p in conf_files
    )
    if conf_has_modeset or re.search(
        r"nvidia[-_]drm\.modeset=1", read_file("/proc/cmdline")
    ):
        return CheckResult(
            "KMS (modeset)", "ok",
            tr("Moduł nvidia_drm działa, modeset=1 ustawiony w konfiguracji"
               " (parametr w /sys wymaga roota)"),
        )
    return CheckResult(
        "KMS (modeset)", "info",
        tr("Moduł nvidia_drm działa; stan modeset nieznany — odczyt parametru"
           " wymaga uprawnień administratora"),
    )


def _check_session() -> CheckResult:
    session = os.environ.get("XDG_SESSION_TYPE", "")
    if session:
        return CheckResult(
            tr("Typ sesji"), "info", tr("Sesja graficzna:") + f" {session}"
        )
    return CheckResult(tr("Typ sesji"), "info", tr("Nie wykryto typu sesji graficznej"))


def _check_dkms() -> CheckResult:
    if not which("dkms"):
        return CheckResult("DKMS", "info", tr("DKMS niezainstalowany"))
    code, out, _ = run(["dkms", "status"], timeout=20)
    if code != 0:
        return CheckResult("DKMS", "uwaga", tr("dkms status zwraca błąd"))
    nvidia_lines = [l for l in out.splitlines() if "nvidia" in l.lower()]
    if not nvidia_lines:
        return CheckResult("DKMS", "info", tr("Brak modułów NVIDIA w DKMS"))
    bad = [l for l in nvidia_lines if "installed" not in l]
    if bad:
        return CheckResult(
            "DKMS", "blad",
            tr("Moduł NVIDIA nie jest zbudowany:") + " " + "; ".join(bad),
        )
    return CheckResult("DKMS", "ok", "; ".join(nvidia_lines))


def _check_kernel_log() -> CheckResult:
    """Szuka błędów NVRM/nouveau w logu jądra bieżącego rozruchu."""
    # Format "-o cat" zwraca sam komunikat, bez daty i hostname — inaczej
    # hostname zawierający "nvidia" dopasowałby każdą linię logu
    code, out, _ = run(
        ["journalctl", "-k", "-b", "--no-pager", "-p", "err", "-n", "200",
         "-o", "cat"],
        timeout=20,
    )
    if code != 0:
        return CheckResult(
            tr("Log jądra"), "info", tr("Brak dostępu do journalctl — pominięto")
        )
    errors = [
        l for l in out.splitlines()
        if re.search(r"nvrm|nvidia|nouveau", l, re.I)
    ]
    if errors:
        return CheckResult(
            tr("Log jądra"), "uwaga",
            tr("Błędy sterownika w logu ({n}), ostatni:").format(n=len(errors))
            + f" {errors[-1][:200]}",
        )
    return CheckResult(
        tr("Log jądra"), "ok", tr("Brak błędów sterownika w bieżącym rozruchu")
    )


def run_diagnostics() -> list[CheckResult]:
    """Wykonuje wszystkie kontrole i zwraca listę wyników."""
    if not is_linux():
        return [
            CheckResult(
                "System", "blad",
                tr("Program uruchomiony poza Linuksem — diagnostyka niedostępna"
                   " (tryb podglądu GUI)"),
            )
        ]
    distro = detect_distro()
    results = [
        CheckResult(
            tr("Dystrybucja"),
            "ok" if distro.supported else "uwaga",
            f"{distro.name}"
            + ("" if distro.supported
               else tr(" — dystrybucja nieobsługiwana przez program")),
        ),
        _check_gpu(),
        _check_driver(),
        _check_module_loaded(),
        _check_nvidia_smi(),
        _check_version_match(),
        _check_secure_boot(),
        _check_kernel_headers(),
        _check_nouveau_blacklist(),
        _check_gsp_firmware(),
        _check_gl_env(),
        _check_glvnd(),
        _check_modeset(),
        _check_dkms(),
        _check_kernel_log(),
        _check_session(),
    ]
    return results


def build_report(results: list[CheckResult], distro: DistroInfo | None = None) -> str:
    """Buduje tekstowy raport diagnostyczny do zapisania w pliku."""
    _, uname, _ = run(["uname", "-a"])
    lines = [
        "=" * 70,
        tr("RAPORT DIAGNOSTYCZNY — NVIDIA Driver Installer"),
        f"{tr('Data:')} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"{tr('System:')} {uname or tr('nieznany')}",
        "=" * 70,
        "",
    ]
    ikony = {"ok": "[ OK  ]", "uwaga": tr("[UWAGA]"), "blad": tr("[BŁĄD ]"),
             "info": "[INFO ]"}
    for r in results:
        lines.append(f"{ikony.get(r.status, '[ ?  ]')} {r.kategoria}: {r.opis}")
    lines.append("")
    problemy = [r for r in results if r.status == "blad"]
    uwagi = [r for r in results if r.status == "uwaga"]
    lines.append(f"{tr('Podsumowanie:')} {len(problemy)} {tr('błędów')},"
                 f" {len(uwagi)} {tr('ostrzeżeń')}")
    return "\n".join(lines) + "\n"
