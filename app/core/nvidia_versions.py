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
# 580.xx is a legacy branch since the 590/595 release (2026): the last one
# supporting Maxwell/Pascal/Volta (official NVIDIA announcement, 2025-07) —
# it still receives updates, unlike the frozen 470/390/340.
FALLBACK_VERSIONS = {
    "production": "595.84",
    "new_feature": None,
    "beta": None,
    "legacy": ["580.173.02", "470.256.02", "390.157", "340.108"],
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


def _archive_latest(major: int, timeout: int = 15) -> str:
    """Newest version of a branch from the official NVIDIA archive index.

    The unix drivers page stopped listing some legacy branches (2026-07 it
    shows only 470.xx), but download.nvidia.com/XFree86/Linux-x86_64/ keeps
    a directory per version — the newest one of the given series is the
    current state of that branch (matters for 580, which still gets updates).
    """
    try:
        html = _http_get("https://download.nvidia.com/XFree86/Linux-x86_64/",
                         timeout)
    except Exception:
        return ""
    vers = re.findall(rf"\b({major}\.\d{{1,3}}(?:\.\d{{1,3}})?)/", html)
    if not vers:
        return ""
    return max(vers, key=lambda v: [int(x) for x in v.split(".")])


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

    # The 580 branch (the last one for Maxwell/Pascal/Volta) is still updated
    # but the unix page may not list it among the legacy entries — fetch the
    # newest 580.xx from the official archive so owners of those cards get
    # a current recommendation, not a frozen fallback.
    if result["online"] and not any(
            v.split(".")[0] == "580" for v in result["legacy"]):
        ver = _archive_latest(580, timeout)
        if ver:
            result["legacy"].insert(0, ver)

    # The page lists ever fewer legacy branches (2026-07: only 470.xx) —
    # fill in the missing SERIES from the fallbacks, so Fermi/Tesla owners
    # still see their branch; series found online are left untouched.
    known = {v.split(".")[0] for v in result["legacy"]}
    for fv in FALLBACK_VERSIONS["legacy"]:
        if fv.split(".")[0] not in known:
            result["legacy"].append(fv)
    # newest series first — the display order in the GUI list
    result["legacy"].sort(key=lambda v: int(v.split(".")[0]), reverse=True)

    # Final fallback — versions hardcoded in the program
    if not result["production"]:
        result["production"] = FALLBACK_VERSIONS["production"]
    return result


def nvidia_repo_url(distro: DistroInfo) -> str:
    """URL of the official NVIDIA APT repository for a given Debian release."""
    ver = re.search(r"\d+", distro.version or "")
    return f"{NVIDIA_REPO_BASE}/debian{ver.group(0) if ver else '13'}/x86_64"


def keyring_url(distro: DistroInfo) -> str:
    """URL of the cuda-keyring package that adds the signed NVIDIA repository."""
    return nvidia_repo_url(distro) + "/cuda-keyring_1.1-1_all.deb"


def suse_repo_url(distro: DistroInfo) -> str:
    """URL of the official NVIDIA zypper repository for openSUSE.

    Tumbleweed (and Slowroll) have a rolling repo without a version in the
    path; Leap uses leap/$releasever — the literal variable is resolved by
    zypper itself, so one URL works across Leap upgrades. Tumbleweed is
    recognized by the id or by VERSION_ID being a snapshot date (no dot)
    rather than a Leap release number like 15.6 / 16.0.
    """
    ident = (distro.id or "").lower()
    if ("tumbleweed" in ident or "slowroll" in ident
            or not re.match(r"\d+\.\d+", distro.version or "")):
        return "https://download.nvidia.com/opensuse/tumbleweed"
    return "https://download.nvidia.com/opensuse/leap/$releasever"


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
    if distro.family == "suse":
        code, out, _ = run(["zypper", "-n", "info", "Mesa"], timeout=40)
        m = re.search(r"^(?:Version|Wersja)\s*:\s*(\S+)", out, re.M) if code == 0 else None
        return _czysta_wersja(m.group(1)) if m else ""
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
    if distro.family == "suse":
        return _suse_repo_versions()
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


def _suse_repo_versions() -> list[dict]:
    """openSUSE: the newest driver generation visible to zypper.

    The signed open kernel modules (nvidia-open-driver-G0X-signed-kmp-default)
    live in the main openSUSE OSS repository, so a version is usually known
    even before the NVIDIA repository (userspace packages) is added during
    installation. An empty list when nothing is found — the GUI then shows
    a generic message and the installation adds the repository itself.
    """
    code, out, _ = run(
        ["zypper", "-n", "se", "-s", "-t", "package",
         "nvidia-open-driver-G0*-signed-kmp-default"],
        timeout=60,
    )
    if code != 0:
        return []
    found: list[tuple[str, tuple[int, ...], str]] = []
    for line in out.splitlines():
        cols = [c.strip() for c in line.split("|")]
        # zypper -s table: S | Name | Type | Version | Arch | Repository
        if len(cols) >= 4 and cols[1].startswith("nvidia-open-driver"):
            ver = cols[3].split("_")[0]  # "580.95.05_k6.12..." → "580.95.05"
            key = tuple(int(x) for x in re.findall(r"\d+", ver))
            found.append((cols[1], key, ver))
    if not found:
        return []
    # Newest generation NUMERICALLY (G10 > G09), then by version — a plain
    # string comparison of package names would sort "G10" below "G09"
    def _gen_num(pkg_name: str) -> int:
        m = re.search(r"-G(\d+)-", pkg_name)
        return int(m.group(1)) if m else 0

    name, _, ver = max(found, key=lambda f: (_gen_num(f[0]), f[1]))
    return [{"pakiet": name, "wersja": ver, "zalecany": True}]


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
