# -*- coding: utf-8 -*-
"""Detecting NVIDIA cards (lspci) and the currently installed driver."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass

from app.i18n import tr

from .utils import is_linux, read_file, run, which


@dataclass
class GPU:
    """A single NVIDIA graphics card."""

    name: str      # e.g. "GeForce RTX 3060"
    pci_id: str    # device identifier, e.g. "2504"


# Name patterns for cards with Turing or newer architecture (RTX 20xx+) —
# only these support open kernel modules and full NVK.
_TURING_PLUS = [
    r"\bRTX\s*[2-9]0\d0\b",      # GeForce RTX 2060…5090
    r"\bGTX\s*16\d0\b",          # GTX 1650/1660 (Turing without RT)
    r"\bTITAN\s*RTX\b",
    r"\bQUADRO\s*RTX\b",
    r"\bRTX\s*A\d{3,4}\b",       # RTX A2000…A6000 (Ampere pro)
    r"\bRTX\s*\d{3,4}\s*(ADA|Ada)\b",  # RTX 2000/4000 Ada
    r"\bTESLA\s*T4\b",
    r"\b[AHL]\d{2,3}\b",         # A100, H100, L40 etc. (server)
]


def is_turing_or_newer(name: str) -> bool:
    """Heuristic: whether the card has Turing or newer architecture (RTX 20xx+)."""
    upper = name.upper()
    return any(re.search(p, upper, re.IGNORECASE) for p in _TURING_PLUS)


# Patterns for cards with Blackwell or newer architecture (RTX 50xx+) — these
# cards work ONLY with open kernel modules (proprietary ones don't support them).
# Note: "RTX 5000 Ada" is an older architecture — the 50[5-9]0 requirement excludes it.
_BLACKWELL_PLUS = [
    r"\bRTX\s*50[5-9]0\b",           # GeForce RTX 5050-5090
    r"\bRTX\s*PRO\s*\d{3,4}\b",      # RTX PRO 4000/5000/6000 (Blackwell pro)
    r"\bGB\s?[12]\d{2}\b",           # GB10x/GB20x chip names from lspci
    r"\bB[12]00\b",                  # B100/B200 (server)
]


def is_blackwell_or_newer(name: str) -> bool:
    """Heuristic: whether the card requires open kernel modules (RTX 50xx+)."""
    upper = name.upper()
    return any(re.search(p, upper, re.IGNORECASE) for p in _BLACKWELL_PLUS)


# Rules for recognizing older architectures by card name.
# ORDER MATTERS — the patterns partially overlap (e.g. GTX 750 is Maxwell,
# though it also matches the Kepler GTX 7xx pattern), so newer architectures
# are checked first.
# Format: (architecture, patterns, required Legacy branch, max driver series)
_ARCH_RULES: list[tuple[str, list[str], str | None, int | None]] = [
    # Maxwell / Pascal / Volta — the last branch supporting them is series 580
    ("Maxwell/Pascal/Volta", [
        r"\bGTX\s*9[5-8]0\b",            # GTX 950-980
        r"\bGTX\s*10[5-8]0\b",           # GTX 1050-1080
        r"\bGTX\s*(745|750|850M?|860M?|950M?|960M?|965M?)\b",
        r"\bGT\s*10[13]0\b",             # GT 1010/1030
        r"\bTITAN\s*(X\b|XP\b|V\b)",
        r"\bMX[123]\d0\b",               # MX110-MX350 (laptops)
        r"\bQUADRO\s*[MP]\d{3,4}\b",
        r"\bTESLA\s*[MPV]\d{1,3}\b",
    ], None, 580),
    # Kepler — requires the Legacy 470 branch
    ("Kepler", [
        r"\bGTX\s*6[4-9]0\b",            # GTX 640-690
        r"\bGTX\s*7[1-8]0\b",            # GTX 710-780 (750 caught above)
        r"\bGT\s*(64\d|7[1-4]0)\b",      # GT 640-740
        r"\bGTX\s*TITAN\b",              # original TITAN / Black / Z
        r"\bQUADRO\s*K\d{3,4}\b",
        r"\bTESLA\s*K\d{1,3}\b",
    ], "470", None),
    # Fermi — requires the Legacy 390 branch
    ("Fermi", [
        r"\bGTX?\s*4\d0\b",              # GTX 460-480, GT 420-440
        r"\bGTX?\s*5[0-8]\d\b",          # GTX 550-580, GT 520-530
        r"\bQUADRO\s*[2456]000\b",
    ], "390", None),
    # Tesla (G8x-GT2xx) — requires the Legacy 340 branch
    ("Tesla (GeForce 8/9/200/300)", [
        r"\b[89]\d{3}\s*(GT|GTX|GS|GSO|GX2)\b",   # 8800 GT, 9600 GT etc.
        r"\bGTX?\s*2[5-9]\d\b",                   # GTX 260-295
        r"\bGT\s*(1[23]0|2[24]0|3[23]0|340)\b",
        r"\bG\s?210\b",
    ], "340", None),
]


def recommended_driver_info(name: str) -> dict:
    """Matches the recommended driver branch to the detected card's architecture.

    Returns a dictionary:
      arch      — architecture name ("" if unrecognized)
      legacy    — required Legacy series ("470"/"390"/"340") or None
      max_major — highest supported driver series or None (= latest)
    Heuristic based on the card name — unrecognized names are treated like new
    cards (latest driver), because that is by far the most common case.
    """
    if is_turing_or_newer(name):
        return {"arch": "Turing lub nowsza", "legacy": None, "max_major": None}
    upper = name.upper()
    for arch, patterns, legacy, max_major in _ARCH_RULES:
        if any(re.search(p, upper, re.IGNORECASE) for p in patterns):
            return {"arch": arch, "legacy": legacy, "max_major": max_major}
    return {"arch": "", "legacy": None, "max_major": None}


def detect_gpus() -> list[GPU]:
    """Returns the list of NVIDIA cards found by lspci."""
    if not is_linux():
        return []
    code, out, _ = run(["lspci", "-nn"])
    if code != 0:
        return []

    gpus: list[GPU] = []
    for line in out.splitlines():
        # We only care about NVIDIA graphics controllers (vendor 10de)
        if "10de" not in line.lower():
            continue
        if not re.search(r"VGA compatible|3D controller|Display controller", line, re.I):
            continue
        # PCI device identifier: [10de:2504]
        m_id = re.search(r"\[10de:([0-9a-f]{4})\]", line, re.I)
        # Card name: text after "NVIDIA Corporation" up to the bracket with the ID
        m_name = re.search(r":\s*NVIDIA Corporation\s+(.*?)\s*(?:\[10de:|\(|$)", line)
        name = m_name.group(1).strip() if m_name else "NVIDIA (nieznany model)"
        # lspci often reports the name in the form "GA106 [GeForce RTX 3060]"
        m_pretty = re.search(r"\[([^\]]+)\]", name)
        if m_pretty:
            name = m_pretty.group(1)
        gpus.append(GPU(name=name, pci_id=m_id.group(1).lower() if m_id else ""))
    return gpus


def _loaded_modules() -> str:
    """Contents of /proc/modules (list of loaded kernel modules)."""
    return read_file("/proc/modules")


def driver_bound(driver: str) -> bool:
    """Whether the kernel driver has actually claimed any PCI device.

    A mere entry in /proc/modules is not enough: the module may be loaded
    yet still not drive the card (e.g. nouveau without GSP firmware fails
    the probe and the card is left without a driver).
    """
    try:
        return any(
            entry.startswith(("0000:", "0001:"))
            for entry in os.listdir(f"/sys/bus/pci/drivers/{driver}")
        )
    except OSError:
        return False


def detect_installed_driver() -> dict:
    """Detects the installed NVIDIA driver.

    Returns a dictionary: {"typ": ..., "wersja": ..., "zrodlo": ...}
      typ    — "proprietary" | "open-kernel" | "nouveau" | none ("")
      wersja — e.g. "580.95.05" (when known)
      zrodlo — "plik .run" | "repozytorium" | ""
    """
    result = {"typ": "", "wersja": "", "zrodlo": ""}
    if not is_linux():
        return result

    modules = _loaded_modules()

    # NVIDIA driver (proprietary or open kernel modules)
    code, out, _ = run(
        ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"]
    )
    if code == 0 and out:
        result["wersja"] = out.splitlines()[0].strip()
        # The module license distinguishes the open module (MIT/GPL) from the proprietary one
        _, lic, _ = run(["modinfo", "-F", "license", "nvidia"])
        result["typ"] = "open-kernel" if "MIT" in lic.upper() else "proprietary"
        # The nvidia-uninstall file exists only after installation from a .run file
        result["zrodlo"] = "plik .run" if which("nvidia-uninstall") else "repozytorium"
        return result

    # Version from the module when nvidia-smi doesn't work but the module is in the kernel
    if re.search(r"^nvidia\s", modules, re.M):
        result["typ"] = "proprietary"
        result["wersja"] = read_file("/sys/module/nvidia/version").strip()
        result["zrodlo"] = "plik .run" if which("nvidia-uninstall") else "repozytorium"
        return result

    # Open nouveau driver (NVK from Mesa runs on it) — it counts only when it
    # has really claimed the card, not the mere fact that the module is loaded
    if re.search(r"^nouveau\s", modules, re.M) and driver_bound("nouveau"):
        result["typ"] = "nouveau"
        result["zrodlo"] = "jądro / Mesa"
    return result


def driver_description(info: dict) -> str:
    """Human-readable driver description for the user (in the interface language)."""
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
