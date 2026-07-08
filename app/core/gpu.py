# -*- coding: utf-8 -*-
"""Wykrywanie kart NVIDIA (lspci) i aktualnie zainstalowanego sterownika."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass

from app.i18n import tr

from .utils import is_linux, read_file, run, which


@dataclass
class GPU:
    """Pojedyncza karta graficzna NVIDIA."""

    name: str      # np. "GeForce RTX 3060"
    pci_id: str    # identyfikator urządzenia, np. "2504"


# Wzorce nazw kart o architekturze Turing lub nowszej (RTX 20xx+) —
# tylko te obsługują otwarte moduły jądra (open kernel modules) i pełne NVK.
_TURING_PLUS = [
    r"\bRTX\s*[2-9]0\d0\b",      # GeForce RTX 2060…5090
    r"\bGTX\s*16\d0\b",          # GTX 1650/1660 (Turing bez RT)
    r"\bTITAN\s*RTX\b",
    r"\bQUADRO\s*RTX\b",
    r"\bRTX\s*A\d{3,4}\b",       # RTX A2000…A6000 (Ampere pro)
    r"\bRTX\s*\d{3,4}\s*(ADA|Ada)\b",  # RTX 2000/4000 Ada
    r"\bTESLA\s*T4\b",
    r"\b[AHL]\d{2,3}\b",         # A100, H100, L40 itd. (serwerowe)
]


def is_turing_or_newer(name: str) -> bool:
    """Heurystyka: czy karta ma architekturę Turing lub nowszą (RTX 20xx+)."""
    upper = name.upper()
    return any(re.search(p, upper, re.IGNORECASE) for p in _TURING_PLUS)


# Wzorce kart o architekturze Blackwell lub nowszej (RTX 50xx+) — te karty
# działają WYŁĄCZNIE z otwartymi modułami jądra (zamknięte ich nie obsługują).
# Uwaga: "RTX 5000 Ada" to starsza architektura — wyklucza ją wymóg 50[5-9]0.
_BLACKWELL_PLUS = [
    r"\bRTX\s*50[5-9]0\b",           # GeForce RTX 5050-5090
    r"\bRTX\s*PRO\s*\d{3,4}\b",      # RTX PRO 4000/5000/6000 (Blackwell pro)
    r"\bGB\s?[12]\d{2}\b",           # nazwy układów GB10x/GB20x z lspci
    r"\bB[12]00\b",                  # B100/B200 (serwerowe)
]


def is_blackwell_or_newer(name: str) -> bool:
    """Heurystyka: czy karta wymaga otwartych modułów jądra (RTX 50xx+)."""
    upper = name.upper()
    return any(re.search(p, upper, re.IGNORECASE) for p in _BLACKWELL_PLUS)


# Reguły rozpoznawania starszych architektur po nazwie karty.
# KOLEJNOŚĆ MA ZNACZENIE — wzorce częściowo się nakładają (np. GTX 750 to
# Maxwell, choć pasuje też do wzorca Keplera GTX 7xx), więc nowsze
# architektury sprawdzane są jako pierwsze.
# Format: (architektura, wzorce, wymagana gałąź Legacy, maks. seria sterownika)
_ARCH_RULES: list[tuple[str, list[str], str | None, int | None]] = [
    # Maxwell / Pascal / Volta — ostatnia wspierająca je gałąź to seria 580
    ("Maxwell/Pascal/Volta", [
        r"\bGTX\s*9[5-8]0\b",            # GTX 950-980
        r"\bGTX\s*10[5-8]0\b",           # GTX 1050-1080
        r"\bGTX\s*(745|750|850M?|860M?|950M?|960M?|965M?)\b",
        r"\bGT\s*10[13]0\b",             # GT 1010/1030
        r"\bTITAN\s*(X\b|XP\b|V\b)",
        r"\bMX[123]\d0\b",               # MX110-MX350 (laptopy)
        r"\bQUADRO\s*[MP]\d{3,4}\b",
        r"\bTESLA\s*[MPV]\d{1,3}\b",
    ], None, 580),
    # Kepler — wymaga gałęzi Legacy 470
    ("Kepler", [
        r"\bGTX\s*6[4-9]0\b",            # GTX 640-690
        r"\bGTX\s*7[1-8]0\b",            # GTX 710-780 (750 złapane wyżej)
        r"\bGT\s*(64\d|7[1-4]0)\b",      # GT 640-740
        r"\bGTX\s*TITAN\b",              # oryginalny TITAN / Black / Z
        r"\bQUADRO\s*K\d{3,4}\b",
        r"\bTESLA\s*K\d{1,3}\b",
    ], "470", None),
    # Fermi — wymaga gałęzi Legacy 390
    ("Fermi", [
        r"\bGTX?\s*4\d0\b",              # GTX 460-480, GT 420-440
        r"\bGTX?\s*5[0-8]\d\b",          # GTX 550-580, GT 520-530
        r"\bQUADRO\s*[2456]000\b",
    ], "390", None),
    # Tesla (G8x-GT2xx) — wymaga gałęzi Legacy 340
    ("Tesla (GeForce 8/9/200/300)", [
        r"\b[89]\d{3}\s*(GT|GTX|GS|GSO|GX2)\b",   # 8800 GT, 9600 GT itd.
        r"\bGTX?\s*2[5-9]\d\b",                   # GTX 260-295
        r"\bGT\s*(1[23]0|2[24]0|3[23]0|340)\b",
        r"\bG\s?210\b",
    ], "340", None),
]


def recommended_driver_info(name: str) -> dict:
    """Dobiera zalecaną gałąź sterownika do architektury wykrytej karty.

    Zwraca słownik:
      arch      — nazwa architektury ("" gdy nierozpoznana)
      legacy    — wymagana seria Legacy ("470"/"390"/"340") lub None
      max_major — najwyższa obsługiwana seria sterownika lub None (= najnowsza)
    Heurystyka po nazwie karty — nazwy nierozpoznane traktujemy jak nowe
    karty (najnowszy sterownik), bo to zdecydowanie najczęstszy przypadek.
    """
    if is_turing_or_newer(name):
        return {"arch": "Turing lub nowsza", "legacy": None, "max_major": None}
    upper = name.upper()
    for arch, patterns, legacy, max_major in _ARCH_RULES:
        if any(re.search(p, upper, re.IGNORECASE) for p in patterns):
            return {"arch": arch, "legacy": legacy, "max_major": max_major}
    return {"arch": "", "legacy": None, "max_major": None}


def detect_gpus() -> list[GPU]:
    """Zwraca listę kart NVIDIA znalezionych przez lspci."""
    if not is_linux():
        return []
    code, out, _ = run(["lspci", "-nn"])
    if code != 0:
        return []

    gpus: list[GPU] = []
    for line in out.splitlines():
        # Interesują nas tylko kontrolery graficzne NVIDIA (vendor 10de)
        if "10de" not in line.lower():
            continue
        if not re.search(r"VGA compatible|3D controller|Display controller", line, re.I):
            continue
        # Identyfikator urządzenia PCI: [10de:2504]
        m_id = re.search(r"\[10de:([0-9a-f]{4})\]", line, re.I)
        # Nazwa karty: tekst po "NVIDIA Corporation" do nawiasu z ID
        m_name = re.search(r":\s*NVIDIA Corporation\s+(.*?)\s*(?:\[10de:|\(|$)", line)
        name = m_name.group(1).strip() if m_name else "NVIDIA (nieznany model)"
        # lspci często podaje nazwę w formie "GA106 [GeForce RTX 3060]"
        m_pretty = re.search(r"\[([^\]]+)\]", name)
        if m_pretty:
            name = m_pretty.group(1)
        gpus.append(GPU(name=name, pci_id=m_id.group(1).lower() if m_id else ""))
    return gpus


def _loaded_modules() -> str:
    """Zawartość /proc/modules (lista załadowanych modułów jądra)."""
    return read_file("/proc/modules")


def driver_bound(driver: str) -> bool:
    """Czy sterownik jądra faktycznie przejął jakieś urządzenie PCI.

    Sam wpis w /proc/modules nie wystarcza: moduł może być załadowany,
    a mimo to nie obsługiwać karty (np. nouveau bez firmware GSP kończy
    probe błędem i karta zostaje bez sterownika).
    """
    try:
        return any(
            entry.startswith(("0000:", "0001:"))
            for entry in os.listdir(f"/sys/bus/pci/drivers/{driver}")
        )
    except OSError:
        return False


def detect_installed_driver() -> dict:
    """Wykrywa zainstalowany sterownik NVIDIA.

    Zwraca słownik: {"typ": ..., "wersja": ..., "zrodlo": ...}
      typ    — "proprietary" | "open-kernel" | "nouveau" | brak ("")
      wersja — np. "580.95.05" (gdy znana)
      zrodlo — "plik .run" | "repozytorium" | ""
    """
    result = {"typ": "", "wersja": "", "zrodlo": ""}
    if not is_linux():
        return result

    modules = _loaded_modules()

    # Sterownik NVIDIA (proprietary lub open kernel modules)
    code, out, _ = run(
        ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"]
    )
    if code == 0 and out:
        result["wersja"] = out.splitlines()[0].strip()
        # Licencja modułu odróżnia moduł otwarty (MIT/GPL) od zamkniętego
        _, lic, _ = run(["modinfo", "-F", "license", "nvidia"])
        result["typ"] = "open-kernel" if "MIT" in lic.upper() else "proprietary"
        # Plik nvidia-uninstall istnieje tylko po instalacji z pliku .run
        result["zrodlo"] = "plik .run" if which("nvidia-uninstall") else "repozytorium"
        return result

    # Wersja z modułu, gdy nvidia-smi nie działa, ale moduł jest w jądrze
    if re.search(r"^nvidia\s", modules, re.M):
        result["typ"] = "proprietary"
        result["wersja"] = read_file("/sys/module/nvidia/version").strip()
        result["zrodlo"] = "plik .run" if which("nvidia-uninstall") else "repozytorium"
        return result

    # Sterownik otwarty nouveau (na nim działa NVK z Mesy) — liczy się tylko
    # wtedy, gdy naprawdę przejął kartę, nie sam fakt załadowania modułu
    if re.search(r"^nouveau\s", modules, re.M) and driver_bound("nouveau"):
        result["typ"] = "nouveau"
        result["zrodlo"] = "jądro / Mesa"
    return result


def driver_description(info: dict) -> str:
    """Czytelny opis sterownika dla użytkownika (w języku interfejsu)."""
    typ = info.get("typ", "")
    if typ == "proprietary":
        opis = f"NVIDIA proprietary {info.get('wersja', '')}".strip()
    elif typ == "open-kernel":
        opis = f"NVIDIA open kernel modules {info.get('wersja', '')}".strip()
    elif typ == "nouveau":
        return "nouveau / NVK (open source, Mesa)"
    else:
        return tr("brak sterownika NVIDIA")
    zrodlo = info.get("zrodlo", "")
    return f"{opis} ({tr(zrodlo)})" if zrodlo else opis
