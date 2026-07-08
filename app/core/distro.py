# -*- coding: utf-8 -*-
"""Linux distribution detection based on /etc/os-release.

The program groups distributions into three families, because within a family
the driver installation works the same way:
  - arch   → Arch Linux, CachyOS, EndeavourOS          (pacman, mkinitcpio/dracut)
  - fedora → Fedora 44, Nobara 43                      (dnf, dracut)
  - debian → Debian, Kubuntu 26.04 LTS, Mint 22.3      (apt, update-initramfs)
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from .utils import is_linux, read_file

# initramfs rebuild command specific to each family.
# The arch family has no single generator: plain Arch and CachyOS use
# mkinitcpio, EndeavourOS — dracut (without mkinitcpio on disk; the
# EndeavourOS 2026-07-05 case: "mkinitcpio: command not found").
# The choice is conditioned on the tool's presence, not the distribution name;
# dracut-rebuild (eos-dracut) takes precedence over bare dracut, because it
# knows the EOS image layout (/boot/initramfs-linux.img).
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
    """Information about the detected distribution."""

    id: str = ""              # e.g. "arch", "fedora", "linuxmint"
    name: str = "?"           # full name, e.g. "Linux Mint 22.3"
    version: str = ""         # version number from VERSION_ID
    family: str = ""          # family: "arch" | "fedora" | "debian" | ""
    ubuntu_based: bool = False  # Kubuntu/Mint — different packages than plain Debian
    supported: bool = False   # whether the family is supported by the program

    @property
    def initramfs_cmd(self) -> str:
        """initramfs update command for this distribution."""
        return INITRAMFS_CMD.get(self.family, "")


def _parse_os_release(text: str) -> dict:
    """Parses the key=value format of the os-release file (quotes stripped)."""
    data: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            key, _, val = line.partition("=")
            data[key.strip()] = val.strip().strip('"').strip("'")
    return data


def detect_distro() -> DistroInfo:
    """Detects the distribution. On other systems returns preview mode."""
    if not is_linux():
        # Preview mode — the GUI works, but system functions are disabled
        return DistroInfo(name=f"{os.name} (tryb podglądu — to nie Linux)")

    osr = _parse_os_release(read_file("/etc/os-release"))
    distro_id = osr.get("ID", "").lower()
    # ID + ID_LIKE together allow recognizing derivatives (CachyOS → arch etc.)
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
