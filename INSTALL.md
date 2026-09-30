# Installing GlyphOS (manual, for now)

This assumes a fresh Arch Linux install with Hyprland already set up.

## 1. Install required packages

```bash
sudo pacman -S --needed hyprland eww waybar mako hyprlock hypridle hyprpaper \
    htop bc grim slurp wf-recorder zathura zathura-pdf-mupdf \
    brightnessctl playerctl pipewire wireplumber networkmanager \
    ttf-font-awesome noto-fonts python curl librsvg imagemagick bluez-utils
```

## 2. Copy configs

```bash
cp -r config/hypr ~/.config/
cp -r config/eww ~/.config/
cp -r config/waybar ~/.config/
cp -r config/mako ~/.config/
mkdir -p ~/.local/share/nothingos ~/Pictures
cp local/share/nothingos/*.sh ~/.local/share/nothingos/
cp assets/wallpaper.jpg ~/Pictures/wallpaper.jpg
```

## 3. Install the dot-matrix font

Install a separately obtained, appropriately licensed `Dot-55.otf` (font family `Ndot 55`) into `~/.local/share/fonts/` and run:

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

## Lock-screen helpers

Hyprlock v0.9.6 and Hyprland v0.56.2 were used for the current configuration.
The lock screen uses `~/Pictures/wallpaper.jpg`, live Chandigarh weather from wttr.in,
and MPRIS media data. Profile names are visual placeholders; PAM authenticates the
current system account. Wi-Fi requires NetworkManager, Bluetooth requires BlueZ,
and power actions use systemd. Install wvkbd separately for the optional keyboard;
its visibility over the lock screen depends on compositor support.

Weather location, SSID labels, profile names, and the `LVDS-1` monitor name remain
machine-specific values to review before using this configuration on another device.
