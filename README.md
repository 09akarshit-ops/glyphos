<p align="center">
  <img src="assets/glyphos-logo.svg" width="120" alt="GlyphOS logo">
</p>

<h1 align="center">GlyphOS</h1>
<p align="center">A minimal, dot-matrix desktop environment for Arch Linux — built on Hyprland and Eww.</p>

<p align="center">
  <img src="https://img.shields.io/badge/Arch%20Linux-1793D1?logo=arch-linux&logoColor=white" alt="Arch Linux">
  <img src="https://img.shields.io/badge/Hyprland-58E1FF?logo=wayland&logoColor=black" alt="Hyprland">
  <img src="https://img.shields.io/badge/license-MIT-black" alt="MIT License">
</p>

---

## What is GlyphOS?

GlyphOS is a full desktop shell built from scratch on top of Hyprland (a Wayland compositor), using
[eww](https://github.com/elkowar/eww) for UI widgets, the top bar, and the dock. It replaces the entire default Hyprland experience — panels, app launcher, notifications,
settings, and a handful of built-in mini-apps — with a light, minimal, dot-matrix aesthetic.

It is **not** a Linux distribution. It's a dotfiles-based desktop configuration you install on top of
Arch Linux (or an Arch-based distro), plus a set of custom eww widgets that act as small built-in apps.

## Features

- **Global live lyrics** — a top-center Dynamic Island displays two lyric lines from MPRIS media, with local LRC, LRCLIB exact/fuzzy search, NetEase, and plain-text web fallbacks. Availability depends on provider coverage; plain lyrics use estimated timing.
- **Two-row taskbar** — compact spacing, enlarged lyrics, working palette/clipboard/focus buttons, separate window controls, and consistent circular dock icons.
- **Clipboard cards** — explicit Copy/Delete actions with immediate list updates.
- **Playback timing controls** — actual MPRIS position tracking and persistent ±250 ms offset adjustment.
- **Managed desktop services** — one Eww server, an independent lyrics worker, and bounded background jobs; optional isolated Gemini browser launcher.

- **Custom desktop shell** — Now Playing (real media metadata via `playerctl`), live System Resources
  (CPU/memory/storage/network graphs), a weather widget, and a themed dock
- **App launcher** — searchable, category-based, with a power menu and an expandable "more" section
- **Device Manager** — live audio/Bluetooth/USB/network device listing with collapsible categories
- **Task Manager**, **Calendar & Tasks**, **Screenshot & Screen Recorder**, **Display & Power** controls
- **Settings app** — card-based system settings (display, sound, network, appearance)
- **Real notifications** via `mako`, themed to match the rest of the desktop
- **Custom lock screen** via `hyprlock`

## Screenshots

[Latest completed desktop screenshots — 8 October 2026](screenshots/day-08-2026-10-08/README.md).

Build history and feature screenshots are organized by date in [`screenshots/`](./screenshots) —
each folder is one day of development, showing the project's actual progression from a broken config
to a working desktop.

## Installation

> ⚠️ This project is under active development. Manual installation only for now — an automated
> installer script is planned for the first tagged release.

```bash
git clone https://github.com/09akarshit-ops/glyphos.git
cd glyphos
```

See [`INSTALL.md`](./INSTALL.md) for manual setup steps and required packages.

## Tech stack

| Component | Tool |
|---|---|
| Compositor | [Hyprland](https://hyprland.org/) |
| Widgets / desktop shell | [eww](https://github.com/elkowar/eww) |
| Top bar / lyrics pill | Eww + MPRIS lyrics service |
| Notifications | [mako](https://github.com/emersion/mako) |
| Lock screen | [hyprlock](https://github.com/hyprwm/hyprlock) |
| Login manager | plasmalogin |

## Roadmap

- [ ] Automated install script (`setup.sh`)
- [ ] Parameterize hardcoded personal config (location, username, monitor name)
- [x] Local app search and bounded file indexing in the launcher
- [ ] Packaged ISO release
- [ ] Themeable login greeter (evaluating SDDM as a replacement for plasmalogin)

## Contributing

See [`CONTRIBUTING.md`](./CONTRIBUTING.md).

## License

MIT — see [`LICENSE`](./LICENSE).

---

<p align="center"><sub>Built by <a href="https://github.com/09akarshit-ops">Akarshit</a> — documented as a public build log.</sub></p>

See [CHANGELOG.md](./CHANGELOG.md) for the daily snapshot and [desktop feature notes](./config/glyphos/README.md) for service and shortcut details.
