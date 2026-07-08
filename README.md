# NVIDIA Driver Installer

> [Polska wersja README](README_PL.md)

A simple graphical tool (PySide6) for **fully automatic installation of NVIDIA
drivers on Linux**. Pick a method, click a single button, enter the administrator
password once — the program takes care of the rest.

---

## Screenshots

| Light theme | Dark theme |
|:---:|:---:|
| ![Light theme](screenshot-light.png) | ![Dark theme](screenshot-dark.png) |

---

## Features

**Driver installation methods:**
- **NVK** — open-source NVIDIA driver (Mesa), no proprietary components, full Wayland support
- **Repository** — installs the driver from the distribution's official repository; available versions are detected automatically
- **Run file (Production / New Feature / Beta / Legacy)** — downloads and installs directly from NVIDIA servers

**Additional features:**
- Automatic GPU and installed-driver detection
- Real-time GPU monitor: temperature, usage, VRAM, power draw, fan
- System diagnostics with a detailed error report (Secure Boot, DKMS, kernel headers, logs)
- Installation history with full logs
- Automatic configuration: `nvidia_drm modeset=1` (Wayland), nouveau blacklist, initramfs update
- Support for open kernel modules (Turing architecture and newer, RTX 20xx+)
- Polish and English interface (auto-detected from the system locale; the choice in Settings takes precedence)
- Light and dark theme

---

## Tested distributions

| Family | Distributions |
|---|---|
| Arch | Arch Linux, CachyOS, EndeavourOS |
| Fedora | Fedora 44, Nobara 43 |
| Debian | Debian 13, Kubuntu 26.04 LTS, Linux Mint 22.3 |

Each distribution passed the full test cycle (repository → NVK → .run → repository)
on a GeForce RTX 5070 Ti. Other distributions from these families (Ubuntu, RHEL,
Rocky Linux, AlmaLinux, etc.) should also work, but were not tested directly.

---

## Requirements

- Linux with an NVIDIA graphics card
- `python3` (on Debian / Kubuntu / Mint also the `python3-venv` package)
- Administrator (sudo) access

`PySide6` and `requests` are installed automatically into a local virtual
environment on the first run — you do not need to install them yourself.

---

## How to run

```bash
chmod +x NVIDIA-Installer.run   # first time only
./NVIDIA-Installer.run
```

The script automatically creates a Python virtual environment (`.venv`),
installs the dependencies (`PySide6`, `requests`) and launches the program.
The first run may take a few minutes because of the `PySide6` download —
a progress window is shown while the environment is being prepared.

On Debian / Kubuntu / Mint the `venv` and `ensurepip` modules ship in a
separate `python3-venv` package; the script detects a missing package and
offers to install it for you.

---

## Ready-made binary (no Python required)

If you prefer not to run from source, download the ready binary
`nvidia-driver-installer-linux-x86_64` from the
[Releases](https://github.com/Pablo-g8q1l/nvidia-driver-installer/releases) page,
make it executable and run it:

```bash
chmod +x nvidia-driver-installer-linux-x86_64
./nvidia-driver-installer-linux-x86_64
```

The binary is built on Ubuntu 24.04 (glibc 2.39), so it runs on distributions
with glibc 2.39 or newer. No Python or PySide6 installation is required.

---

## How installation works

1. The program detects your distribution, graphics card and current driver.
2. After you click **INSTALL DRIVER**, a single installation script is generated
   and run via `pkexec` (with a `sudo` fallback) — you enter the password only once.
3. The script automatically installs dependencies, removes the previous driver,
   blacklists nouveau, enables `nvidia_drm modeset=1` (Wayland), installs the
   driver and updates the initramfs.
4. Progress and the full log are shown live; the log is also saved to the
   **History** tab.
5. When finished, the program offers to restart the computer.

---

## Important notes

- **Secure Boot:** with Secure Boot enabled, unsigned DKMS modules will not load.
  The *Diagnostics* tab detects this state and suggests a solution.
- **Legacy branches (470 / 390 / 340)** may fail to build on the latest 6.x
  kernels — the program warns you before such an installation.
- A system restart is recommended after every installation.
- **Tested on:** GeForce RTX 5070 Ti, KDE Plasma desktop environment.

---

## Where the program stores data

The application follows the XDG directory standard:

```
~/.config/nvidia-installer-gui/        # settings (language, theme)
~/.local/share/nvidia-installer-gui/   # logs, installation history (history.json), boot reports
~/.cache/nvidia-installer-gui/         # downloaded .run installer file
```

---

## Troubleshooting

**No internet connection**
The application checks connectivity before installation. Make sure you have an
active connection — the repository and `.run` methods download packages from the network.

**The password window does not appear / installation is not authorized**
The program asks for the administrator password once, via `pkexec` (or `sudo` in a
terminal, or a `kdialog` / `zenity` password window). Make sure `polkit` (pkexec)
or `zenity` / `kdialog` is installed.

**The driver fails to load after a reboot**
Check whether Secure Boot is enabled — unsigned DKMS modules will not load. The
*Diagnostics* tab detects this state. Sign the modules or disable Secure Boot.

**Black screen after a `.run` installation**
Boot into recovery mode (or a previous kernel) and use the program to switch back
to the repository driver, or remove the driver manually with `nvidia-uninstall`.

---

## Project status

This project was created with the help of AI (Claude Code) by a Linux user
without a programming background. The author's role was to define the goals,
test the application on real hardware across multiple distributions, and report
issues for further improvement.

This is a hobby project — there is no guarantee of regular updates. Bug reports
and suggestions are welcome in the Issues tab, though response time may vary.
The project is provided free of charge for the community.

---

## Author

Created by [Pablo-g8q1l](https://github.com/Pablo-g8q1l) — a Linux user who
wanted a simple, clean way to install NVIDIA drivers without touching the
terminal every time.

---

## Support

If you find this project useful, you can buy me a coffee.

[![Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/pablog8q1l)

---

## License

Released under the MIT License — see [LICENSE](LICENSE) for details.
