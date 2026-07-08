# -*- coding: utf-8 -*-
"""Wykrywanie dystrybucji Linuksa na podstawie /etc/os-release.

Program grupuje dystrybucje w trzy rodziny, bo w ramach rodziny instalacja
sterownika przebiega tak samo:
  - arch   → Arch Linux, CachyOS, EndeavourOS          (pacman, mkinitcpio/dracut)
  - fedora → Fedora 44, Nobara 43                      (dnf, dracut)
  - debian → Debian, Kubuntu 26.04 LTS, Mint 22.3      (apt, update-initramfs)
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from .utils import is_linux, read_file

# Polecenie odbudowy initramfs właściwe dla każdej rodziny.
# Rodzina arch nie ma jednego generatora: czysty Arch i CachyOS używają
# mkinitcpio, EndeavourOS — dracuta (bez mkinitcpio na dysku; przypadek
# EndeavourOS 2026-07-05: „mkinitcpio: nie znaleziono polecenia").
# Wybór warunkowany obecnością narzędzia, nie nazwą dystrybucji;
# dracut-rebuild (eos-dracut) ma pierwszeństwo przed gołym dracutem,
# bo zna układ obrazów EOS (/boot/initramfs-linux.img).
INITRAMFS_CMD = {
    "arch": (
        "if command -v mkinitcpio >/dev/null 2>&1; then mkinitcpio -P; "
        "elif command -v dracut-rebuild >/dev/null 2>&1; then dracut-rebuild; "
        "else dracut -f --regenerate-all; fi"
    ),
    "fedora": "dracut -f --regenerate-all",
    "debian": "update-initramfs -u -k all",
}


@dataclass
class DistroInfo:
    """Informacje o wykrytej dystrybucji."""

    id: str = ""              # np. "arch", "fedora", "linuxmint"
    name: str = "?"           # pełna nazwa, np. "Linux Mint 22.3"
    version: str = ""         # numer wersji z VERSION_ID
    family: str = ""          # rodzina: "arch" | "fedora" | "debian" | ""
    ubuntu_based: bool = False  # Kubuntu/Mint — inne pakiety niż czysty Debian
    supported: bool = False   # czy rodzina jest obsługiwana przez program

    @property
    def initramfs_cmd(self) -> str:
        """Polecenie aktualizacji initramfs dla tej dystrybucji."""
        return INITRAMFS_CMD.get(self.family, "")


def _parse_os_release(text: str) -> dict:
    """Parsuje format klucz=wartość pliku os-release (cudzysłowy usuwane)."""
    data: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            key, _, val = line.partition("=")
            data[key.strip()] = val.strip().strip('"').strip("'")
    return data


def detect_distro() -> DistroInfo:
    """Wykrywa dystrybucję. Na innych systemach zwraca tryb podglądu."""
    if not is_linux():
        # Tryb podglądu — GUI działa, ale funkcje systemowe są wyłączone
        return DistroInfo(name=f"{os.name} (tryb podglądu — to nie Linux)")

    osr = _parse_os_release(read_file("/etc/os-release"))
    distro_id = osr.get("ID", "").lower()
    # ID + ID_LIKE razem pozwalają rozpoznać pochodne (CachyOS → arch itd.)
    ids = {distro_id} | set(osr.get("ID_LIKE", "").lower().split())

    if "arch" in ids:
        family = "arch"
    elif ids & {"fedora", "rhel", "centos"}:
        family = "fedora"
    elif ids & {"debian", "ubuntu"}:
        family = "debian"
    else:
        family = ""

    return DistroInfo(
        id=distro_id,
        name=osr.get("PRETTY_NAME") or osr.get("NAME", "Nieznana dystrybucja"),
        version=osr.get("VERSION_ID", ""),
        family=family,
        ubuntu_based="ubuntu" in ids or distro_id == "linuxmint",
        supported=family in INITRAMFS_CMD,
    )
