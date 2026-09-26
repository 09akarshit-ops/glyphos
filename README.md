<p align="center">
  <img src="assets/glyphos-logo.svg" width="120" alt="GlyphOS logo">
</p>

<h1 align="center">GlyphOS</h1>
<p align="center">A minimal, dot-matrix desktop environment for Arch Linux — built on Hyprland, eww, and waybar.</p>

<p align="center">
  <img src="https://img.shields.io/badge/Arch%20Linux-1793D1?logo=arch-linux&logoColor=white" alt="Arch Linux">
  <img src="https://img.shields.io/badge/Hyprland-58E1FF?logo=wayland&logoColor=black" alt="Hyprland">
  <img src="https://img.shields.io/badge/license-MIT-black" alt="MIT License">
</p>

---

## What is GlyphOS?

GlyphOS is a full desktop shell built from scratch on top of Hyprland (a Wayland compositor), using
[eww](https://github.com/elkowar/eww) for all UI widgets and [waybar](https://github.com/Alexays/Waybar)
for the top bar. It replaces the entire default Hyprland experience — panels, app launcher, notifications,
settings, and a handful of built-in mini-apps — with a light, minimal, dot-matrix aesthetic.

It is **not** a Linux distribution. It's a dotfiles-based desktop configuration you install on top of
Arch Linux (or an Arch-based distro), plus a set of custom eww widgets that act as small built-in apps.

## Features

- **Custom desktop shell** — Now Playing (real media metadata via `playerctl`), live System Resources
  (CPU/memory/storage/network graphs), a weather widget, and a themed dock
- **App launcher** — searchable, category-based, with a power menu and an expandable "more" section
- **Device Manager** — live audio/Bluetooth/USB/network device listing with collapsible categories
- **Task Manager**, **Calendar & Tasks**, **Screenshot & Screen Recorder**, **Display & Power** controls
- **Settings app** — card-based system settings (display, sound, network, appearance)
- **Real notifications** via `mako`, themed to match the rest of the desktop
- **Custom lock screen** via `hyprlock`

## Screenshots

Build history and feature screenshots are organized by date in [`screenshots/`](./screenshots) —
each folder is one day of development, showing the project's actual progression from a broken config
to a working desktop.

## Installation

> ⚠️ This project is under active development. Manual installation only for now — an automated
> installer script is planned for the first tagged release.

```bash
git clone https://github.com/<your-username>/glyphos.git
cd glyphos
```

See [`INSTALL.md`](./INSTALL.md) for manual setup steps and required packages.

## Tech stack

| Component | Tool |
|---|---|
| Compositor | [Hyprland](https://hyprland.org/) |
| Widgets / desktop shell | [eww](https://github.com/elkowar/eww) |
| Top bar | [waybar](https://github.com/Alexays/Waybar) |
| Notifications | [mako](https://github.com/emersion/mako) |
| Lock screen | [hyprlock](https://github.com/hyprwm/hyprlock) |
| Login manager | plasmalogin |

## Roadmap

- [ ] Automated install script (`setup.sh`)
- [ ] Parameterize hardcoded personal config (location, username, monitor name)
- [ ] Full app search/indexing in the launcher
- [ ] Packaged ISO release
- [ ] Themeable login greeter (evaluating SDDM as a replacement for plasmalogin)

## Contributing

See [`CONTRIBUTING.md`](./CONTRIBUTING.md).

## License

MIT — see [`LICENSE`](./LICENSE).

---

<p align="center"><sub>Built by <a href="https://github.com/<your-username>">Akarshit</a> — documented as a public build log.</sub></p>
