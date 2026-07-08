# -*- coding: utf-8 -*-
"""Interface translations (Polish / English).

Convention: the translation key is the original Polish text. For Polish, tr()
returns the text unchanged; for English it looks it up in the _EN dictionary
(no entry → Polish text as a fallback, the program still works).
"""
from __future__ import annotations

_current_language = "pl"


def set_language(lang: str) -> None:
    """Sets the interface language: "pl" or "en"."""
    global _current_language
    _current_language = lang if lang in ("pl", "en") else "pl"


def get_language() -> str:
    """Returns the current interface language."""
    return _current_language


def tr(text: str) -> str:
    """Translates interface text into the current language."""
    if _current_language == "pl":
        return text
    return _EN.get(text, text)


def tr_prefix(text: str) -> str:
    """tr() tolerant of a dynamic suffix in parentheses.

    Used for installation step and error messages whose text ends with a
    runtime value in parentheses (e.g. a package name) that is not in the
    dictionary. Then only the prefix before " (" is translated.
    """
    t = tr(text)
    if t == text and text.endswith(")") and " (" in text:
        prefix, _, rest = text.rpartition(" (")
        return tr(prefix) + f" ({rest}"
    return t


# Translation dictionary: Polish text → English
_EN = {
    # --- Main window / tabs ---
    "Instalacja": "Installation",
    "Monitor GPU": "GPU Monitor",
    "Diagnostyka": "Diagnostics",
    "Historia": "History",
    "Ustawienia": "Settings",
    "Wykrywanie systemu...": "Detecting system...",
    "brak karty NVIDIA": "no NVIDIA card",

    # --- Installation page ---
    "Wykryty system": "Detected system",
    "Dystrybucja: wykrywanie...": "Distribution: detecting...",
    "Karta graficzna: wykrywanie...": "Graphics card: detecting...",
    "Obecny sterownik: wykrywanie...": "Current driver: detecting...",
    "Dystrybucja": "Distribution",
    "Karta graficzna": "Graphics card",
    "Obecny sterownik": "Current driver",
    "Uruchomione jądro": "Running kernel",
    "(nieobsługiwana — instalacja zablokowana)":
        "(unsupported — installation blocked)",
    "nie wykryto karty NVIDIA": "no NVIDIA card detected",
    "Tryb podglądu — instalacja dostępna tylko na Linuksie.":
        "Preview mode — installation is only available on Linux.",
    "Metoda instalacji": "Installation method",
    "Repozytorium dystrybucji (zalecane)": "Distribution repository (recommended)",
    "Plik .run z serwerów NVIDIA": ".run file from NVIDIA servers",
    "NVK — sterownik open source (Mesa)": "NVK — open source driver (Mesa)",
    "Sprawdzanie dostępnej wersji...": "Checking available version...",
    "Pobieranie listy wersji...": "Fetching version list...",
    "Bez komponentów NVIDIA, pełne wsparcie Wayland. Najlepiej działa"
    " na kartach RTX 20xx i nowszych.":
        "No NVIDIA components, full Wayland support. Works best on"
        " RTX 20xx cards and newer.",
    "Otwarte moduły jądra (open kernel modules) — RTX 20xx i nowsze":
        "Open kernel modules — RTX 20xx and newer",
    "ZAINSTALUJ STEROWNIK": "INSTALL DRIVER",
    "Tutaj pojawi się szczegółowy przebieg instalacji...":
        "Detailed installation progress will appear here...",
    "Production (stabilna)": "Production (stable)",
    "New Feature": "New Feature",
    "Beta": "Beta",
    "Legacy": "Legacy",
    "(brak internetu — wersje zapasowe)": "(no internet — fallback versions)",
    "Dostępne wersje:": "Available versions:",
    "(zalecany)": "(recommended)",
    "Wykryta wersja:": "Detected version:",
    "Nie udało się wykryć wersji w repozytorium.":
        "Could not detect the repository version.",
    "NVK jest w całości open source.": "NVK is fully open source.",
    "Karty RTX 50xx i nowsze działają wyłącznie z otwartymi"
    " modułami jądra — wybór jest wymuszony.":
        "RTX 50xx and newer cards work only with open kernel"
        " modules — the choice is enforced.",
    "Otwarte moduły wymagają karty RTX 20xx lub nowszej.":
        "Open modules require an RTX 20xx card or newer.",
    "Repozytorium Debiana nie oferuje wariantu open — wybierz"
    " źródło Repozytorium NVIDIA albo metodę .run.":
        "The Debian repository has no open variant — choose the NVIDIA"
        " repository source or the .run method.",
    "Źródło pakietów:": "Package source:",
    "Repozytorium Debiana": "Debian repository",
    "Repozytorium NVIDIA": "NVIDIA repository",
    "(wymagane dla RTX 50xx)": "(required for RTX 50xx)",
    "(nie obsługuje RTX 50xx)": "(does not support RTX 50xx)",
    "(zalecane)": "(recommended)",
    "oficjalne repozytorium NVIDIA": "official NVIDIA repository",
    "repozytorium Debiana": "Debian repository",
    "Sterownik z repozytorium Debiana (seria 550) nie"
    " obsługuje kart RTX 50xx — wybierz Repozytorium"
    " NVIDIA.":
        "The driver from the Debian repository (550 series) does not"
        " support RTX 50xx cards — choose the NVIDIA repository.",
    "Ta wersja sterownika nie obsługuje modułów otwartych.":
        "This driver version does not support open modules.",
    "Na RTX 50xx program zainstaluje nowsze jądro, Mesę i firmware"
    " z oficjalnych backportów Debiana.":
        "On RTX 50xx the program will install a newer kernel, Mesa and"
        " firmware from the official Debian backports.",
    "Karta RTX 50xx: jądro, Mesa i firmware zostaną"
    " zainstalowane z oficjalnych backportów Debiana.":
        "RTX 50xx card: the kernel, Mesa and firmware will be installed"
        " from the official Debian backports.",
    "Brak wersji": "No version",
    "Nie wybrano wersji sterownika do pobrania.":
        "No driver version selected for download.",
    "Gałęzie Legacy mogą nie zbudować się na nowych jądrach 6.x.":
        "Legacy branches may fail to build on new 6.x kernels.",
    "Wybrana metoda:": "Selected method:",
    "Instalacja jest w pełni automatyczna. System poprosi raz"
    " o hasło administratora, a po zakończeniu zalecany jest"
    " restart komputera.":
        "Installation is fully automatic. The system will ask once for the"
        " administrator password, and a reboot is recommended afterwards.",
    "Rozpocząć instalację?": "Start the installation?",
    "(nie obsługuje Twojej karty)": "(does not support your card)",
    "(może nie wspierać Twojej karty)": "(may not support your card)",
    "(zalecana dla Twojej karty)": "(recommended for your card)",
    "Architektura karty:": "Card architecture:",
    "Turing lub nowsza": "Turing or newer",
    "Twoja karta wymaga gałęzi Legacy": "Your card requires the Legacy branch",
    "najnowszy sterownik z repozytorium może jej nie"
    " obsługiwać. Najbezpieczniejsza jest metoda .run"
    " z zalecaną wersją.":
        "the newest repository driver may not support it. The safest"
        " option is the .run method with the recommended version.",
    "Potwierdzenie instalacji": "Installation confirmation",
    "Brak uprawnień": "No privileges",
    "W systemie nie ma ani pkexec, ani sudo. Zainstaluj"
    " pakiet pkexec (polkit) i spróbuj ponownie.":
        "The system has neither pkexec nor sudo. Install the pkexec"
        " (polkit) package and try again.",
    "Hasło administratora": "Administrator password",
    "W systemie nie ma pkexec — podaj hasło administratora"
    " (sudo), aby przeprowadzić instalację:":
        "The system has no pkexec — enter the administrator (sudo)"
        " password to perform the installation:",
    "Błędne hasło": "Wrong password",
    "Hasło nie zostało przyjęte przez sudo — spróbuj ponownie.":
        "The password was not accepted by sudo — try again.",
    "Przygotowywanie instalacji...": "Preparing installation...",
    "Krok": "Step",
    "Pobieranie sterownika...": "Downloading driver...",
    "Instalacja zakończona pomyślnie.": "Installation completed successfully.",
    "Sukces": "Success",
    "Sterownik został zainstalowany. Aby zmiany zadziałały,"
    " uruchom komputer ponownie.":
        "The driver has been installed. Reboot the computer for the changes"
        " to take effect.",
    "Uruchomić ponownie teraz?": "Reboot now?",
    "Instalacja nie powiodła się.": "Installation failed.",
    "Błąd instalacji": "Installation error",
    "Nieznany błąd.": "Unknown error.",
    "Instalacja działa tylko na Linuksie": "Installation works only on Linux",
    "Brak poleceń pkexec i sudo — zainstaluj pakiet pkexec (polkit) lub sudo":
        "Neither pkexec nor sudo is available — install the pkexec (polkit)"
        " or sudo package",
    "Anulowano autoryzację administratora (pkexec)":
        "Administrator authorization cancelled (pkexec)",
    "Skrypt zakończył się kodem": "The script exited with code",
    "Sprawdzanie integralności pliku .run...": "Checking .run file integrity...",
    "Kopia lokalna uszkodzona — pobieram ponownie":
        "Local copy corrupted — downloading again",
    "Pobrany plik .run nie przechodzi kontroli integralności"
    " — spróbuj ponownie":
        "The downloaded .run file fails the integrity check — try again",
    "Plik {n} już pobrany — używam kopii lokalnej":
        "File {n} already downloaded — using the local copy",
    "Pobieranie:": "Downloading:",
    "Pobrano:": "Downloaded:",
    "Wersja sterownika:": "Driver version:",
    "Liczba kroków:": "Number of steps:",
    "Skrypt instalacyjny:": "Installation script:",
    "Skrypt instalacyjny przekazany potokiem (bez pliku w /tmp)":
        "Installation script passed through a pipe (no file in /tmp)",
    "BŁĄD:": "ERROR:",
    "Pełny log znajdziesz w zakładce Historia.":
        "The full log is available in the History tab.",

    # --- Installation step labels (installer.py; translated when displayed
    #     in page_install._tr_step — the prefixes alone handle labels with a
    #     dynamic package name in parentheses) ---
    "Aktualizacja initramfs": "Updating initramfs",
    "Budowanie modułu DKMS dla pozostałych jąder":
        "Building the DKMS module for the remaining kernels",
    "Budowanie modułu jądra (akmods — może potrwać kilka minut)":
        "Building the kernel module (akmods — may take a few minutes)",
    "Dodawanie oficjalnego repozytorium NVIDIA (cuda-keyring)":
        "Adding the official NVIDIA repository (cuda-keyring)",
    "Instalacja firmware GPU (GSP — wymagany na kartach RTX)":
        "Installing GPU firmware (GSP — required on RTX cards)",
    "Instalacja nowszego jądra z backportów (wymagane dla RTX 50xx)":
        "Installing a newer kernel from backports (required for RTX 50xx)",
    "Instalacja sterownika": "Installing the driver",
    "Instalacja sterownika z repozytorium NVIDIA":
        "Installing the driver from the NVIDIA repository",
    "Instalacja sterownika NVIDIA z pliku .run (może potrwać kilka minut)":
        "Installing the NVIDIA driver from the .run file (may take a few"
        " minutes)",
    "Instalacja sterownika NVK / Mesa": "Installing the NVK / Mesa driver",
    "Instalacja sterownika z repozytorium (pełna aktualizacja systemu)":
        "Installing the driver from the repository (full system update)",
    "Instalacja zależności do budowania modułu jądra":
        "Installing dependencies for building the kernel module",
    "Konfiguracja modprobe (blokada nouveau, modeset)":
        "Configuring modprobe (nouveau blacklist, modeset)",
    "Kontrola integralności pakietów EGL (naprawa brakujących plików)":
        "Checking EGL package integrity (repairing missing files)",
    "Odinstalowanie poprzednich sterowników": "Uninstalling previous drivers",
    "Odinstalowanie sterownika NVIDIA (jeśli obecny)":
        "Uninstalling the NVIDIA driver (if present)",
    "Odinstalowanie sterownika z repozytorium Debiana (jeśli obecny)":
        "Uninstalling the driver from the Debian repository (if present)",
    "Odinstalowanie sterownika z repozytorium NVIDIA (jeśli obecny)":
        "Uninstalling the driver from the NVIDIA repository (if present)",
    "Odświeżanie listy pakietów": "Refreshing the package list",
    "Porządkowanie usługi raportu rozruchu (opcja wyłączona)":
        "Cleaning up the boot report service (option disabled)",
    "Usuwanie blokady nouveau i konfiguracji NVIDIA":
        "Removing the nouveau blacklist and NVIDIA configuration",
    "Usuwanie konfliktującej odmiany sterownika":
        "Removing the conflicting driver variant",
    "Usuwanie parametrów nvidia-drm z konfiguracji GRUB":
        "Removing nvidia-drm parameters from the GRUB configuration",
    "Usuwanie sterownika z pliku .run (jeśli obecny)":
        "Removing the .run driver (if present)",
    "Usuwanie wymuszeń NVIDIA w zmiennych środowiskowych":
        "Removing NVIDIA overrides from environment variables",
    "Uzupełnianie modułu nouveau (pakiet kernel-modules)":
        "Completing the nouveau module (kernel-modules package)",
    "Włączanie oficjalnych backportów Debiana":
        "Enabling the official Debian backports",
    "Włączanie otwartych modułów jądra (makro RPMFusion)":
        "Enabling open kernel modules (RPMFusion macro)",
    "Włączanie raportu rozruchu (diagnostyka po restarcie)":
        "Enabling the boot report (diagnostics after reboot)",
    "Włączanie repozytorium RPMFusion (free + nonfree)":
        "Enabling the RPMFusion repository (free + nonfree)",
    "Włączanie sekcji contrib / non-free / non-free-firmware":
        "Enabling the contrib / non-free / non-free-firmware sections",

    # --- GPU Monitor ---
    "Oczekiwanie na dane z GPU...": "Waiting for GPU data...",
    "Statystyki na żywo": "Live statistics",
    "Temperatura:": "Temperature:",
    "Użycie GPU:": "GPU usage:",
    "Pamięć VRAM:": "VRAM memory:",
    "Pobór mocy:": "Power draw:",
    "Wentylator:": "Fan:",
    "Sterownik": "Driver",
    "brak danych": "no data",
    "Monitor niedostępny": "Monitor unavailable",
    "Monitor wymaga sterownika NVIDIA (nvidia-smi). Przy NVK /"
    " nouveau statystyki nie są dostępne.":
        "The monitor requires the NVIDIA driver (nvidia-smi). With NVK /"
        " nouveau, statistics are not available.",

    # --- Diagnostics ---
    "Diagnostyka sprawdza stan sterownika, Secure Boot, nagłówki"
    " jądra, DKMS i logi. Uruchom ją, gdy coś nie działa.":
        "Diagnostics checks the driver state, Secure Boot, kernel headers,"
        " DKMS and logs. Run it when something is not working.",
    "Uruchom diagnostykę": "Run diagnostics",
    "Zapisz raport...": "Save report...",
    "Kontrola": "Check",
    "Status": "Status",
    "Szczegóły": "Details",
    "Trwa sprawdzanie systemu...": "Checking the system...",
    "Wykryto problemy:": "Problems detected:",
    "błędów": "errors",
    "ostrzeżeń": "warnings",
    "System działa, ale jest": "The system works, but there are",
    "Wszystkie kontrole zakończone pomyślnie": "All checks passed",
    "Zapisz raport diagnostyczny": "Save diagnostic report",
    "Pliki tekstowe (*.txt)": "Text files (*.txt)",
    "Zapisano": "Saved",
    "Raport zapisany w:": "Report saved to:",
    "Błąd zapisu": "Save error",
    "Nie udało się zapisać raportu:": "Failed to save the report:",
    "UWAGA": "WARNING",
    "BŁĄD": "ERROR",

    # --- Diagnostic checks (diagnostics.py) ---
    "Karta graficzna NVIDIA": "NVIDIA graphics card",
    "Wykryto:": "Detected:",
    "Nie wykryto karty NVIDIA (lspci) — sterownik nie ma czego obsługiwać":
        "No NVIDIA card detected (lspci) — there is nothing for the driver"
        " to handle",
    "Zainstalowany sterownik": "Installed driver",
    "Brak aktywnego sterownika NVIDIA (ani proprietary, ani nouveau)":
        "No active NVIDIA driver (neither proprietary nor nouveau)",
    "Moduł jądra": "Kernel module",
    "Moduł nvidia obsługuje kartę": "The nvidia module is driving the card",
    "Moduł nvidia jest załadowany, ale NIE przejął karty — sterownik nie"
    " działa, szczegóły w kontroli „Log jądra”":
        "The nvidia module is loaded but did NOT take over the card — the"
        " driver is not working, see the \"Kernel log\" check for details",
    "Moduł nouveau obsługuje kartę (NVK)":
        "The nouveau module is driving the card (NVK)",
    "Moduł nouveau jest załadowany, ale NIE przejął karty — sterownik nie"
    " działa (na kartach RTX typowa przyczyna to brak firmware GSP),"
    " szczegóły w kontroli „Log jądra”":
        "The nouveau module is loaded but did NOT take over the card — the"
        " driver is not working (on RTX cards the usual cause is missing GSP"
        " firmware), see the \"Kernel log\" check for details",
    "Żaden moduł graficzny NVIDIA nie jest załadowany — możliwy brak"
    " sterownika lub konieczny restart":
        "No NVIDIA graphics module is loaded — the driver may be missing or"
        " a reboot may be required",
    "Działa — GPU:": "Working — GPU:",
    "Narzędzie nvidia-smi niezainstalowane (normalne przy NVK/nouveau)":
        "The nvidia-smi tool is not installed (normal with NVK/nouveau)",
    "nvidia-smi zwraca błąd:": "nvidia-smi returns an error:",
    "brak komunikatu": "no message",
    "Zgodność wersji sterownika": "Driver version consistency",
    "Moduł nvidia nieaktywny — pominięto": "nvidia module inactive — skipped",
    "Moduł jądra ({k}) ≠ biblioteki ({u}) — wymagany restart lub"
    " ponowna instalacja":
        "Kernel module ({k}) ≠ libraries ({u}) — a reboot or reinstallation"
        " is required",
    "Moduł i biblioteki zgodne": "Module and libraries match",
    "Secure Boot WŁĄCZONY — niepodpisane moduły DKMS nie załadują"
    " się. Wyłącz Secure Boot w UEFI albo podpisz moduł (MOK).":
        "Secure Boot is ENABLED — unsigned DKMS modules will not load."
        " Disable Secure Boot in UEFI or sign the module (MOK).",
    "Secure Boot wyłączony": "Secure Boot disabled",
    "System uruchomiony w trybie BIOS/CSM": "System booted in BIOS/CSM mode",
    "Nie można ustalić stanu (brak narzędzia mokutil)":
        "Cannot determine the state (mokutil tool missing)",
    "Nagłówki jądra": "Kernel headers",
    "Zainstalowane dla jądra": "Installed for kernel",
    "Brak nagłówków dla jądra {k} — program doinstaluje je podczas"
    " instalacji sterownika":
        "No headers for kernel {k} — the program will install them during"
        " driver installation",
    "Blokada nouveau": "Nouveau blacklist",
    "Aktywna (plik {p})": "Active (file {p})",
    "Brak blokady nouveau (wymagana tylko dla sterownika proprietary)":
        "No nouveau blacklist (only required for the proprietary driver)",
    "Karta nie wymaga firmware GSP — pominięto":
        "The card does not require GSP firmware — skipped",
    "Aktywny sterownik NVIDIA — firmware z linux-firmware nieużywany":
        "NVIDIA driver active — firmware from linux-firmware is not used",
    "Pliki firmware GSP obecne w /lib/firmware/nvidia":
        "GSP firmware files present in /lib/firmware/nvidia",
    "Brak firmware GSP w /lib/firmware/nvidia — nouveau/NVK nie wystartuje"
    " na tej karcie. Zainstaluj pakiet linux-firmware (program zrobi to"
    " przy instalacji NVK).":
        "GSP firmware missing from /lib/firmware/nvidia — nouveau/NVK will"
        " not start on this card. Install the linux-firmware package (the"
        " program does this during NVK installation).",
    "Zmienne środowiskowe GL": "GL environment variables",
    "Brak wymuszeń sterownika NVIDIA w /etc/environment*":
        "No NVIDIA driver overrides in /etc/environment*",
    "Wpisy wymuszające sterownik NVIDIA ({n}) — teraz działają, ale po"
    " przejściu na NVK zepsują pulpit. Przykład:":
        "Entries forcing the NVIDIA driver ({n}) — they work now, but after"
        " switching to NVK they will break the desktop. Example:",
    "Zmienne wymuszają sterownik NVIDIA, którego nie ma w systemie —"
    " pulpit działa na renderowaniu programowym (CPU). Usuń wpisy:":
        "Variables force the NVIDIA driver, which is not present in the"
        " system — the desktop runs on software (CPU) rendering. Remove"
        " these entries:",
    "Plik glvnd (EGL)": "glvnd file (EGL)",
    "Sterownik NVIDIA nieaktywny — pominięto":
        "NVIDIA driver inactive — skipped",
    "10_nvidia.json obecny — EGL znajdzie sterownik":
        "10_nvidia.json present — EGL will find the driver",
    "Brak /usr/share/glvnd/egl_vendor.d/10_nvidia.json — pulpit działa na"
    " renderowaniu CPU. Napraw przeinstalowując pakiety sterownika"
    " (np. apt install --reinstall wszystkich pakietów nvidia).":
        "Missing /usr/share/glvnd/egl_vendor.d/10_nvidia.json — the desktop"
        " runs on CPU rendering. Fix it by reinstalling the driver packages"
        " (e.g. apt install --reinstall of all nvidia packages).",
    "nvidia_drm modeset=1 — Wayland OK": "nvidia_drm modeset=1 — Wayland OK",
    "nvidia_drm modeset wyłączony — Wayland może nie działać poprawnie":
        "nvidia_drm modeset disabled — Wayland may not work correctly",
    "Moduł nvidia_drm nieaktywny — pominięto":
        "nvidia_drm module inactive — skipped",
    "Moduł nvidia_drm działa, modeset=1 ustawiony w konfiguracji"
    " (parametr w /sys wymaga roota)":
        "The nvidia_drm module is active, modeset=1 set in the configuration"
        " (reading the /sys parameter requires root)",
    "Moduł nvidia_drm działa; stan modeset nieznany — odczyt parametru"
    " wymaga uprawnień administratora":
        "The nvidia_drm module is active; modeset state unknown — reading"
        " the parameter requires administrator privileges",
    "Typ sesji": "Session type",
    "Sesja graficzna:": "Graphics session:",
    "Nie wykryto typu sesji graficznej": "No graphics session type detected",
    "DKMS niezainstalowany": "DKMS not installed",
    "dkms status zwraca błąd": "dkms status returns an error",
    "Brak modułów NVIDIA w DKMS": "No NVIDIA modules in DKMS",
    "Moduł NVIDIA nie jest zbudowany:": "The NVIDIA module is not built:",
    "Log jądra": "Kernel log",
    "Brak dostępu do journalctl — pominięto":
        "No access to journalctl — skipped",
    "Błędy sterownika w logu ({n}), ostatni:":
        "Driver errors in the log ({n}), most recent:",
    "Brak błędów sterownika w bieżącym rozruchu":
        "No driver errors in the current boot",
    "Program uruchomiony poza Linuksem — diagnostyka niedostępna"
    " (tryb podglądu GUI)":
        "The program is running outside Linux — diagnostics unavailable"
        " (GUI preview mode)",
    " — dystrybucja nieobsługiwana przez program":
        " — distribution not supported by the program",
    "RAPORT DIAGNOSTYCZNY — NVIDIA Driver Installer":
        "DIAGNOSTIC REPORT — NVIDIA Driver Installer",
    "Data:": "Date:",
    "System:": "System:",
    "nieznany": "unknown",
    "[UWAGA]": "[WARN ]",
    "[BŁĄD ]": "[ERROR]",
    "Podsumowanie:": "Summary:",
    "brak sterownika NVIDIA": "no NVIDIA driver",
    "plik .run": ".run file",
    "repozytorium": "repository",
    "jądro / Mesa": "kernel / Mesa",

    # --- History ---
    "Zamknij": "Close",
    "Podwójne kliknięcie wpisu otwiera pełny log instalacji.":
        "Double-click an entry to open the full installation log.",
    "Odśwież": "Refresh",
    "Wyczyść historię": "Clear history",
    "Data": "Date",
    "Metoda": "Method",
    "Wersja": "Version",
    "Log instalacji": "Installation log",
    "Usunąć wszystkie wpisy historii wraz z plikami logów?":
        "Delete all history entries together with log files?",
    # Values stored in history.json (method, version and status in Polish)
    "Repozytorium dystrybucji": "Distribution repository",
    "Plik .run NVIDIA": "NVIDIA .run file",
    "repozytorium NVIDIA": "NVIDIA repository",
    "sukces": "success",
    "błąd": "error",
    "Brak zapisanego logu dla tego wpisu.": "No saved log for this entry.",
    "Nie można odczytać pliku logu:": "Cannot read the log file:",

    # --- Settings ---
    "Ustawienia programu": "Program settings",
    "Język interfejsu:": "Interface language:",
    "Motyw:": "Theme:",
    "Ciemny": "Dark",
    "Jasny": "Light",
    "O programie": "About",
    "Instalator sterowników NVIDIA dla dystrybucji Linux.":
        "NVIDIA driver installer for Linux distributions.",
    "Obsługiwane rodziny dystrybucji:": "Supported distribution families:",
    "Metody instalacji: NVK (Mesa), repozytorium dystrybucji,"
    " plik .run z serwerów NVIDIA.":
        "Installation methods: NVK (Mesa), distribution repository,"
        " .run file from NVIDIA servers.",
    "Język zostanie zmieniony po ponownym uruchomieniu programu.":
        "The language will change after restarting the program.",
    "Raport rozruchu:": "Boot report:",
    "Zapisuj diagnostykę grafiki po każdym rozruchu":
        "Save graphics diagnostics after every boot",
    "Instalacja włączy usługę systemową, która po każdym starcie"
    " komputera zapisuje raport o stanie grafiki (sterownik, moduły,"
    " błędy) do katalogu ~/.local/share/nvidia-installer-gui/raporty."
    " Pomaga zdiagnozować czarny ekran po instalacji sterownika."
    " Zmiana zadziała przy najbliższej instalacji; wyłączenie usunie"
    " usługę z systemu.":
        "Installation will enable a system service that saves a graphics"
        " status report (driver, modules, errors) to"
        " ~/.local/share/nvidia-installer-gui/raporty after every boot."
        " Helps diagnose a black screen after driver installation."
        " Takes effect on the next installation; unchecking removes"
        " the service from the system.",
    "Usługa raportu rozruchu zostanie włączona przy najbliższej instalacji.":
        "The boot report service will be enabled on the next installation.",
    "Usługa raportu rozruchu zostanie usunięta przy najbliższej instalacji.":
        "The boot report service will be removed on the next installation.",

    # --- Installation error messages (installer.py; "blad" markers, translated
    #     in InstallThread.run when read; the prefixes alone handle messages
    #     with a dynamic package name in parentheses) ---
    "Instalacja pakietów nie powiodła się": "Package installation failed",
    "Instalacja pakietu nie powiodła się": "Package installation failed",
    "Naprawa pakietu nie powiodła się": "Package repair failed",
    "apt-get update nie powiodło się": "apt-get update failed",
    "Aktualizacja initramfs nie powiodła się": "initramfs update failed",
    "Nie udało się zapisać makra RPM": "Failed to write the RPM macro",
    "Budowanie modułu jądra nie powiodło się": "Building the kernel module failed",
    "Instalacja pakietu cuda-keyring nie powiodła się":
        "Installing the cuda-keyring package failed",
    "Instalacja pakietów Mesa nie powiodła się": "Installing Mesa packages failed",
    "Instalacja pakietu linux-firmware nie powiodła się":
        "Installing the linux-firmware package failed",
    "Instalacja pakietu nvidia-gpu-firmware nie powiodła się":
        "Installing the nvidia-gpu-firmware package failed",
    "Instalacja jądra z backportów nie powiodła się":
        "Installing the kernel from backports failed",
    "Instalacja pakietów Mesa z backportów nie powiodła się":
        "Installing Mesa packages from backports failed",
    "Instalacja firmware nouveau nie powiodła się":
        "Installing nouveau firmware failed",
    "Instalacja zależności nie powiodła się": "Installing dependencies failed",
    "Instalator NVIDIA zwrócił błąd — szczegóły w /var/log/nvidia-installer.log":
        "The NVIDIA installer returned an error — details in"
        " /var/log/nvidia-installer.log",
}
