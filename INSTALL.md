# Installing GlyphOS (manual, for now)

This assumes a fresh Arch Linux install with Hyprland already set up.

## 1. Install required packages

```bash
sudo pacman -S --needed hyprland eww waybar mako hyprlock hypridle hyprpaper \
    htop bc grim slurp wf-recorder zathura zathura-pdf-mupdf \
    brightnessctl playerctl pipewire wireplumber networkmanager \
    ttf-font-awesome noto-fonts
```

## 2. Copy configs

```bash
cp -r config/hypr ~/.config/
cp -r config/eww ~/.config/
cp -r config/waybar ~/.config/
cp -r config/mako ~/.config/
```

## 3. Install the dot-matrix font

Copy `assets/fonts/Dot-55.otf` into `~/.local/share/fonts/` and run:

```bash
fc-cache -fv ~/.local/share/fonts
```

## 4. Personalize the config

These values are currently hardcoded and need to be changed for your setup:

| File | What to change |
|---|---|
| `eww/eww.yuck` | Weather location text (`Chandigarh`), WiFi network name label |
| `hypr/hyprpaper.conf` | Monitor name (check yours with `hyprctl monitors`) |
| `hypr/hyprland.conf` | Autologin username, monitor name |

A setup script that prompts for these automatically is planned — see the [Roadmap](./README.md#roadmap).

## 5. Reload

```bash
hyprctl reload
eww kill; pkill -9 eww; sleep 1; eww daemon
eww open dock && eww open nowplaying && eww open sys-resources && eww open weather
```
