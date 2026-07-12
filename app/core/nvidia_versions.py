# -*- coding: utf-8 -*-
"""Detecting available NVIDIA driver versions.

Two sources:
  1. .run files — the official NVIDIA Unix Drivers page (Production /
     New Feature / Beta / Legacy); fallback versions when offline.
  2. Distribution repository — pacman / dnf / apt queries run locally,
     without administrator privileges.
"""
from __future__ import annotations

import re

from .distro import DistroInfo
from .utils import run, which

# NVIDIA page with the current driver versions for Linux
UNIX_DRIVERS_URL = "https://www.nvidia.com/en-us/drivers/unix/"
# Fallback source — a text file with the latest version
LATEST_TXT_URL = "https://download.nvidia.com/XFree86/Linux-x86_64/latest.txt"
# Official NVIDIA APT repository — on plain Debian the only source of packages
# newer than series 550 (required among others for RTX 50xx cards)
NVIDIA_REPO_BASE = "https://developer.download.nvidia.com/compute/cuda/repos"

# Fallback versions used only when there is no internet at all.
# Installation requires the network anyway, so they mainly serve to show the GUI.
FALLBACK_VERSIONS = {
    "production": "580.95.05",
    "new_feature": None,
    "beta": None,
    "legacy": ["470.256.02", "390.157", "340.108"],
}

# Branch labels on the NVIDIA page → keys of the result dictionary
_BRANCH_PATTERNS = {
    "production": r"Production\s+Branch\s+Version",
    "new_feature": r"New\s+Feature\s+Branch\s+Version",
    "beta": r"Beta\s+Version",
}
_LEGACY_PATTERN = r"Legacy\s+GPU\s+[Vv]ersion[^:]*:"
_VER_RE = r"(\d{3}\.\d{1,3}(?:\.\d{1,3})?)"


def _http_get(url: str, timeout: int) -> str:
    """Fetches text from a URL using the built-in urllib.

    Deliberately without requests — the CLI version runs on the system Python
    without extra packages, and the GUI behaves identically.
    """
    import urllib.request

    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (nvidia-installer-gui)"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def download_url(version: str) -> str:
    """Download URL of the .run file for the given version."""
    return (
        "https://us.download.nvidia.com/XFree86/Linux-x86_64/"
        f"{version}/NVIDIA-Linux-x86_64-{version}.run"
    )


def fetch_run_versions(timeout: int = 15) -> dict:
    """Fetches the current .run branch versions from the NVIDIA page.

    Returns {"production": str|None, "new_feature": ..., "beta": ...,
    "legacy": [str, ...], "online": bool}.
    """
    result = {
        "production": None,
        "new_feature": None,
        "beta": None,
        "legacy": [],
        "online": False,
    }
    try:
        html = _http_get(UNIX_DRIVERS_URL, timeout)

        # Main branches: we look for the version closest to the branch label
        for key, label in _BRANCH_PATTERNS.items():
            m = re.search(label + r".{0,300}?" + _VER_RE, html, re.S | re.I)
            if m:
                result[key] = m.group(1)

        # Legacy branches (470.xx / 390.xx / 340.xx) — there may be several
        for m in re.finditer(_LEGACY_PATTERN + r".{0,300}?" + _VER_RE, html, re.S):
            ver = m.group(1)
            if ver not in result["legacy"]:
                result["legacy"].append(ver)

        result["online"] = bool(result["production"] or result["legacy"])
    except Exception:
        pass  # no internet / page changed — we fall back

    # Fallback source of the latest production version
    if not result["production"]:
        try:
            m = re.search(_VER_RE, _http_get(LATEST_TXT_URL, timeout))
            if m:
                result["production"] = m.group(1)
                result["online"] = True
        except Exception:
            pass

    # Final fallback — versions hardcoded in the program
    if not result["production"]:
        result["production"] = FALLBACK_VERSIONS["production"]
    if not result["legacy"]:
        result["legacy"] = list(FALLBACK_VERSIONS["legacy"])
    return result


def nvidia_repo_url(distro: DistroInfo) -> str:
    """URL of the official NVIDIA APT repository for a given Debian release."""
    ver = re.search(r"\d+", distro.version or "")
    return f"{NVIDIA_REPO_BASE}/debian{ver.group(0) if ver else '13'}/x86_64"


def keyring_url(distro: DistroInfo) -> str:
    """URL of the cuda-keyring package that adds the signed NVIDIA repository."""
    return nvidia_repo_url(distro) + "/cuda-keyring_1.1-1_all.deb"


def open_module_flag(version: str) -> str:
    """The .run installer flag that enables open kernel modules.

    The syntax changed between versions; ones older than 515 have no open
    modules at all (an empty string is returned).
    """
    try:
        major = int(version.split(".")[0])
    except (ValueError, IndexError):
        return ""
    if major >= 560:
        return " --kernel-module-type=open"
    if major >= 515:
        return " -m=kernel-open"
    return ""


def is_newer(available: str, installed: str) -> bool:
    """Whether the available version is strictly newer than the installed one.

    Compares numeric segments ("580.105.08" > "580.95.05"). Unparseable input
    returns False — a missing notice is better than a false one.
    """
    def _parts(ver: str) -> tuple[int, ...]:
        return tuple(int(x) for x in re.findall(r"\d+", ver))

    a, i = _parts(available), _parts(installed)
    return bool(a and i) and a > i


def _czysta_wersja(wersja: str) -> str:
    """Just the version number, without epoch and package revision (1:26.1.4-1 → 26.1.4)."""
    return re.sub(r"^\d+:", "", wersja).split("-")[0]


def get_mesa_version(distro: DistroInfo | None) -> str:
    """Mesa version available in the distribution repository (for the NVK method).

    Queries the local package manager — without administrator privileges.
    Empty string when it cannot be determined (the GUI/CLI simply won't show it).
    """
    if not distro:
        return ""
    if distro.family == "arch":
        code, out, _ = run(["pacman", "-Si", "mesa"], timeout=20)
        m = re.search(r"^(?:Version|Wersja)\s*:\s*(\S+)", out, re.M) if code == 0 else None
        return _czysta_wersja(m.group(1)) if m else ""
    if distro.family == "fedora":
        code, out, _ = run(["dnf", "-q", "info", "mesa-dri-drivers"], timeout=40)
        m = re.search(r"^(?:Version|Wersja)\s*:\s*(\S+)", out, re.M) if code == 0 else None
        return _czysta_wersja(m.group(1)) if m else ""
    if distro.family == "debian":
        code, out, _ = run(["apt-cache", "policy", "mesa-vulkan-drivers"], timeout=20)
        m = (re.search(r"(?:Candidate|Kandydująca)\s*:\s*(\S+)", out)
             if code == 0 else None)
        if m and not m.group(1).startswith("("):
            return _czysta_wersja(m.group(1))
    return ""


# ---------------------------------------------------------------------------
# Versions available in the distribution repository
# ---------------------------------------------------------------------------

def get_repo_versions(distro: DistroInfo) -> list[dict]:
    """Returns the driver packages available in the distribution repository.

    Each item: {"pakiet": str, "wersja": str, "zalecany": bool}.
    An empty list means nothing could be detected.
    """
    if distro.family == "arch":
        return _arch_repo_versions()
    if distro.family == "fedora":
        return _fedora_repo_versions()
    if distro.family == "debian":
        if distro.ubuntu_based:
            return _ubuntu_repo_versions()
        return _debian_repo_versions(distro)
    return []


def _arch_repo_versions() -> list[dict]:
    """Arch: version of the nvidia-utils package from the official repo."""
    code, out, _ = run(["pacman", "-Si", "nvidia-utils"], timeout=20)
    if code != 0:
        return []
    m = re.search(r"^(?:Version|Wersja)\s*:\s*(\S+)", out, re.M)
    ver = m.group(1) if m else "?"
    return [{"pakiet": "nvidia-dkms + nvidia-utils", "wersja": ver, "zalecany": True}]


def _fedora_repo_versions() -> list[dict]:
    """Fedora/Nobara: akmod-nvidia from RPMFusion (if the repo is already enabled)."""
    code, out, _ = run(["dnf", "-q", "info", "akmod-nvidia"], timeout=40)
    if code == 0:
        m = re.search(r"^(?:Version|Wersja)\s*:\s*(\S+)", out, re.M)
        if m:
            return [{"pakiet": "akmod-nvidia", "wersja": m.group(1), "zalecany": True}]
    # RPMFusion not enabled yet — the program will enable it during installation
    return [
        {
            "pakiet": "akmod-nvidia",
            "wersja": "najnowsza z RPMFusion (repo zostanie włączone automatycznie)",
            "zalecany": True,
        }
    ]


def _nvidia_repo_latest(distro: DistroInfo, timeout: int = 15) -> str:
    """The latest nvidia-open version in the official NVIDIA repository."""
    try:
        tekst = _http_get(nvidia_repo_url(distro) + "/", timeout)
        vers = re.findall(r"nvidia-open_(\d+\.\d+(?:\.\d+)?)-\d+_amd64\.deb", tekst)
        if vers:
            return max(vers, key=lambda v: tuple(int(x) for x in v.split(".")))
    except Exception:
        pass  # no internet / page layout changed — version stays unknown
    return ""


def _debian_repo_versions(distro: DistroInfo) -> list[dict]:
    """Plain Debian: two sources — the non-free section and the official NVIDIA repo.

    The Debian repository ends at series 550, which does not support RTX 50xx
    cards — for those the official NVIDIA repository is needed.
    Which source is recommended is decided by the GUI based on the card.
    """
    code, out, _ = run(["apt-cache", "policy", "nvidia-driver"], timeout=20)
    m = re.search(r"(?:Candidate|Kandydująca)\s*:\s*(\S+)", out) if code == 0 else None
    # No candidate is "(none)" / "(brak)" — depending on the system language
    if m and not m.group(1).startswith("("):
        debian_ver = m.group(1)
    else:
        # The non-free section is not enabled yet — it will be during installation
        debian_ver = "najnowsza z non-free (sekcja zostanie włączona automatycznie)"

    nvidia_ver = _nvidia_repo_latest(distro)
    return [
        {
            "pakiet": "nvidia-driver",
            "wersja": debian_ver,
            "zalecany": False,
            "zrodlo": "debian",
        },
        {
            "pakiet": "nvidia-open",
            "wersja": nvidia_ver
            or "najnowsza (repozytorium zostanie dodane automatycznie)",
            "zalecany": False,
            "zrodlo": "nvidia",
        },
    ]


def _ubuntu_repo_versions() -> list[dict]:
    """Kubuntu/Mint: list of nvidia-driver-XXX packages + the one recommended by ubuntu-drivers."""
    # Package recommended by the ubuntu-drivers tool (if available)
    recommended = ""
    if which("ubuntu-drivers"):
        _, out, _ = run(["ubuntu-drivers", "devices"], timeout=40)
        m = re.search(r"driver\s*:\s*(nvidia-driver-\d+(?:-open)?)\s.*recommended", out)
        if m:
            recommended = m.group(1)

    # All available driver metapackages (also in the -open variant)
    code, out, _ = run(
        ["apt-cache", "search", "--names-only", r"^nvidia-driver-[0-9]+(-open)?$"],
        timeout=30,
    )
    if code != 0:
        return []
    pkgs = sorted(
        {m.group(0) for m in re.finditer(r"nvidia-driver-\d+(?:-open)?", out)},
        # Sort: newest series first, regular variant before -open
        key=lambda p: (-int(re.search(r"\d+", p).group(0)), p.endswith("-open")),
    )
    wyniki = []
    for p in pkgs:
        seria = re.search(r"\d+", p).group(0)
        wyniki.append(
            {
                "pakiet": p,
                "wersja": f"seria {seria}" + (" (open)" if p.endswith("-open") else ""),
                "zalecany": p == recommended,
            }
        )
    return wyniki
