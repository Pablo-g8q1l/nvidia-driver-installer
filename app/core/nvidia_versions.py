# -*- coding: utf-8 -*-
"""Wykrywanie dostępnych wersji sterownika NVIDIA.

Dwa źródła:
  1. Pliki .run — oficjalna strona NVIDIA Unix Drivers (Production /
     New Feature / Beta / Legacy); przy braku internetu wersje zapasowe.
  2. Repozytorium dystrybucji — zapytania pacman / dnf / apt wykonywane
     lokalnie, bez uprawnień administratora.
"""
from __future__ import annotations

import re

from .distro import DistroInfo
from .utils import run, which

# Strona NVIDIA z aktualnymi wersjami sterowników dla Linuksa
UNIX_DRIVERS_URL = "https://www.nvidia.com/en-us/drivers/unix/"
# Zapasowe źródło — plik tekstowy z najnowszą wersją
LATEST_TXT_URL = "https://download.nvidia.com/XFree86/Linux-x86_64/latest.txt"
# Oficjalne repozytorium APT NVIDIA — na czystym Debianie jedyne źródło
# pakietów nowszych niż seria 550 (wymagane m.in. dla kart RTX 50xx)
NVIDIA_REPO_BASE = "https://developer.download.nvidia.com/compute/cuda/repos"

# Wersje zapasowe używane tylko przy całkowitym braku internetu.
# Instalacja i tak wymaga sieci, więc służą głównie do pokazania GUI.
FALLBACK_VERSIONS = {
    "production": "580.95.05",
    "new_feature": None,
    "beta": None,
    "legacy": ["470.256.02", "390.157", "340.108"],
}

# Etykiety gałęzi na stronie NVIDIA → klucze słownika wyników
_BRANCH_PATTERNS = {
    "production": r"Production\s+Branch\s+Version",
    "new_feature": r"New\s+Feature\s+Branch\s+Version",
    "beta": r"Beta\s+Version",
}
_LEGACY_PATTERN = r"Legacy\s+GPU\s+[Vv]ersion[^:]*:"
_VER_RE = r"(\d{3}\.\d{1,3}(?:\.\d{1,3})?)"


def _http_get(url: str, timeout: int) -> str:
    """Pobiera tekst spod adresu wbudowanym urllib.

    Celowo bez requests — wersja CLI działa na systemowym Pythonie bez
    dodatkowych pakietów, a GUI zachowuje się identycznie.
    """
    import urllib.request

    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (nvidia-installer-gui)"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def download_url(version: str) -> str:
    """Adres pobierania pliku .run dla podanej wersji."""
    return (
        "https://us.download.nvidia.com/XFree86/Linux-x86_64/"
        f"{version}/NVIDIA-Linux-x86_64-{version}.run"
    )


def fetch_run_versions(timeout: int = 15) -> dict:
    """Pobiera aktualne wersje gałęzi .run ze strony NVIDIA.

    Zwraca {"production": str|None, "new_feature": ..., "beta": ...,
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

        # Gałęzie główne: szukamy wersji najbliżej etykiety gałęzi
        for key, label in _BRANCH_PATTERNS.items():
            m = re.search(label + r".{0,300}?" + _VER_RE, html, re.S | re.I)
            if m:
                result[key] = m.group(1)

        # Gałęzie Legacy (470.xx / 390.xx / 340.xx) — może być ich kilka
        for m in re.finditer(_LEGACY_PATTERN + r".{0,300}?" + _VER_RE, html, re.S):
            ver = m.group(1)
            if ver not in result["legacy"]:
                result["legacy"].append(ver)

        result["online"] = bool(result["production"] or result["legacy"])
    except Exception:
        pass  # brak internetu / zmiana strony — przechodzimy do fallbacku

    # Zapasowe źródło najnowszej wersji produkcyjnej
    if not result["production"]:
        try:
            m = re.search(_VER_RE, _http_get(LATEST_TXT_URL, timeout))
            if m:
                result["production"] = m.group(1)
                result["online"] = True
        except Exception:
            pass

    # Ostateczny fallback — wersje wpisane w programie
    if not result["production"]:
        result["production"] = FALLBACK_VERSIONS["production"]
    if not result["legacy"]:
        result["legacy"] = list(FALLBACK_VERSIONS["legacy"])
    return result


def nvidia_repo_url(distro: DistroInfo) -> str:
    """Adres oficjalnego repozytorium APT NVIDIA dla danego wydania Debiana."""
    ver = re.search(r"\d+", distro.version or "")
    return f"{NVIDIA_REPO_BASE}/debian{ver.group(0) if ver else '13'}/x86_64"


def keyring_url(distro: DistroInfo) -> str:
    """Adres pakietu cuda-keyring dodającego podpisane repozytorium NVIDIA."""
    return nvidia_repo_url(distro) + "/cuda-keyring_1.1-1_all.deb"


def open_module_flag(version: str) -> str:
    """Flaga instalatora .run włączająca otwarte moduły jądra.

    Składnia zmieniała się między wersjami; starsze niż 515 nie mają
    modułów otwartych w ogóle (zwracany pusty tekst).
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


def _czysta_wersja(wersja: str) -> str:
    """Sam numer wersji, bez epoki i rewizji pakietu (1:26.1.4-1 → 26.1.4)."""
    return re.sub(r"^\d+:", "", wersja).split("-")[0]


def get_mesa_version(distro: DistroInfo | None) -> str:
    """Wersja Mesy dostępna w repozytorium dystrybucji (dla metody NVK).

    Zapytanie lokalnego menedżera pakietów — bez uprawnień administratora.
    Pusty tekst, gdy nie da się ustalić (GUI/CLI po prostu nie pokażą wersji).
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
# Wersje dostępne w repozytorium dystrybucji
# ---------------------------------------------------------------------------

def get_repo_versions(distro: DistroInfo) -> list[dict]:
    """Zwraca pakiety sterownika dostępne w repozytorium dystrybucji.

    Każdy element: {"pakiet": str, "wersja": str, "zalecany": bool}.
    Pusta lista oznacza, że nie udało się nic wykryć.
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
    """Arch: wersja pakietu nvidia-utils z oficjalnego repo."""
    code, out, _ = run(["pacman", "-Si", "nvidia-utils"], timeout=20)
    if code != 0:
        return []
    m = re.search(r"^(?:Version|Wersja)\s*:\s*(\S+)", out, re.M)
    ver = m.group(1) if m else "?"
    return [{"pakiet": "nvidia-dkms + nvidia-utils", "wersja": ver, "zalecany": True}]


def _fedora_repo_versions() -> list[dict]:
    """Fedora/Nobara: akmod-nvidia z RPMFusion (jeśli repo już włączone)."""
    code, out, _ = run(["dnf", "-q", "info", "akmod-nvidia"], timeout=40)
    if code == 0:
        m = re.search(r"^(?:Version|Wersja)\s*:\s*(\S+)", out, re.M)
        if m:
            return [{"pakiet": "akmod-nvidia", "wersja": m.group(1), "zalecany": True}]
    # RPMFusion jeszcze nie włączone — program włączy je podczas instalacji
    return [
        {
            "pakiet": "akmod-nvidia",
            "wersja": "najnowsza z RPMFusion (repo zostanie włączone automatycznie)",
            "zalecany": True,
        }
    ]


def _nvidia_repo_latest(distro: DistroInfo, timeout: int = 15) -> str:
    """Najnowsza wersja nvidia-open w oficjalnym repozytorium NVIDIA."""
    try:
        tekst = _http_get(nvidia_repo_url(distro) + "/", timeout)
        vers = re.findall(r"nvidia-open_(\d+\.\d+(?:\.\d+)?)-\d+_amd64\.deb", tekst)
        if vers:
            return max(vers, key=lambda v: tuple(int(x) for x in v.split(".")))
    except Exception:
        pass  # brak internetu / zmiana układu strony — wersja pozostaje nieznana
    return ""


def _debian_repo_versions(distro: DistroInfo) -> list[dict]:
    """Czysty Debian: dwa źródła — sekcja non-free i oficjalne repo NVIDIA.

    Repozytorium Debiana kończy się na serii 550, która nie obsługuje kart
    RTX 50xx — dla nich potrzebne jest oficjalne repozytorium NVIDIA.
    O tym, które źródło jest zalecane, decyduje GUI na podstawie karty.
    """
    code, out, _ = run(["apt-cache", "policy", "nvidia-driver"], timeout=20)
    m = re.search(r"(?:Candidate|Kandydująca)\s*:\s*(\S+)", out) if code == 0 else None
    # Brak kandydata to "(none)" / "(brak)" — zależnie od języka systemu
    if m and not m.group(1).startswith("("):
        debian_ver = m.group(1)
    else:
        # Sekcja non-free nie jest jeszcze włączona — stanie się to przy instalacji
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
    """Kubuntu/Mint: lista pakietów nvidia-driver-XXX + zalecany z ubuntu-drivers."""
    # Pakiet zalecany przez narzędzie ubuntu-drivers (jeśli dostępne)
    recommended = ""
    if which("ubuntu-drivers"):
        _, out, _ = run(["ubuntu-drivers", "devices"], timeout=40)
        m = re.search(r"driver\s*:\s*(nvidia-driver-\d+(?:-open)?)\s.*recommended", out)
        if m:
            recommended = m.group(1)

    # Wszystkie dostępne metapakiety sterownika (też w wariancie -open)
    code, out, _ = run(
        ["apt-cache", "search", "--names-only", r"^nvidia-driver-[0-9]+(-open)?$"],
        timeout=30,
    )
    if code != 0:
        return []
    pkgs = sorted(
        {m.group(0) for m in re.finditer(r"nvidia-driver-\d+(?:-open)?", out)},
        # Sortowanie: najnowsza seria najpierw, wariant zwykły przed -open
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
