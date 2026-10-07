# Installing GlyphOS (manual, for now)

This assumes a fresh Arch Linux install with Hyprland already set up.

## 1. Install required packages

```bash
sudo pacman -S --needed hyprland eww waybar mako hyprlock hypridle hyprpaper \
    htop bc grim slurp wf-recorder zathura zathura-pdf-mupdf \
    brightnessctl playerctl pipewire wireplumber networkmanager \
    ttf-font-awesome noto-fonts python python-gobject python-cairo gtk3 gtk-layer-shell \
    kdeconnect sshfs wl-clipboard cliphist rofi-wayland jq ripgrep flatpak curl librsvg imagemagick bluez-utils
```

## 2. Copy configs

```bash
mkdir -p ~/.config ~/.config/systemd/user ~/.local/bin
cp -r config/glyphos ~/.config/
cp config/systemd/user/* ~/.config/systemd/user/
cp local/bin/* ~/.local/bin/
mkdir -p ~/.local/share/applications
cp local/share/applications/*.desktop ~/.local/share/applications/
cp -r config/hypr ~/.config/
cp -r config/eww ~/.config/
cp -r config/waybar ~/.config/
cp -r config/mako ~/.config/
mkdir -p ~/.local/share/nothingos ~/Pictures
cp local/share/nothingos/*.sh ~/.local/share/nothingos/
cp assets/wallpaper.jpg ~/Pictures/wallpaper.jpg
cp assets/wallpaper-glyphos.png ~/Pictures/wallpaper-glyphos.png
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
| Eww and Hyprland configs | Replace `/home/nothing_os` with your home path; review weather location (`Chandigarh`) and network labels |
| `hypr/hyprpaper.conf` | Monitor name (check yours with `hyprctl monitors`) |
| `hypr/hyprland.conf` | Monitor name, launch paths, and application-specific rules |

A setup script that prompts for these automatically is planned — see the [Roadmap](./README.md#roadmap).

## 5. Start services and reload

Run inside your Hyprland session after reviewing the copied configs:

```bash
systemctl --user daemon-reload
systemctl --user enable glyphos-eww.service glyphos-desktop.service glyphos-lyrics.service \
    glyphos-clipboard.service glyphos-file-undo.service glyphos-snap.service glyphos-phone-mesh.service glyphos-index.timer
~/.config/glyphos/scripts/start-services.sh
~/.config/eww/scripts/start-desktop.sh &
hyprctl reload
eww --no-daemonize reload &
```

Do not start a second standalone Eww daemon alongside `glyphos-eww.service`.
For later lyrics changes, use `systemctl --user restart --no-block glyphos-lyrics.service`;
this does not stop the media player. Super+Ctrl+Left/Right adjust lyrics by 250 ms;
Super+Ctrl+Backspace resets the offset to -500 ms. Negative offsets delay lines.

Runtime history, application registry, window geometry and credentials are generated
locally and are not distributed. Optional Gemini configuration is documented in
[`config/glyphos/README.md`](./config/glyphos/README.md). Existing Waybar configs
are retained as legacy alternatives; the current taskbar runs in Eww.

## Lock-screen helpers

Hyprlock v0.9.6 and Hyprland v0.56.2 were used for the current configuration.
The lock screen uses `~/Pictures/wallpaper.jpg`, live Chandigarh weather from wttr.in,
and MPRIS media data. The centered title displays “Nothing OS” with Ndot 55; PAM authenticates the
current session account. Account Help renders inside the Hyprlock surface with a
TTY `passwd` guide, virtual keyboard toggle, keymap switch, and confirmed power
actions. Back to Login dismisses it. No recovery action bypasses authentication.
The guide requires an existing account login and current password.

Install wvkbd or maliit-keyboard separately for the optional keyboard. Its visibility
above the lock depends on compositor support. Switch Keymap cycles configured
layouts; with only US configured, it adds GB for the current compositor session.
Set `GLYPHOS_SECONDARY_KEYMAP` in the session environment to choose another
secondary layout. A Hyprland reload restores the configured layout list.

Wi-Fi requires NetworkManager, Bluetooth requires BlueZ,
and power actions use systemd. Install wvkbd separately for the optional keyboard;
its visibility over the lock screen depends on compositor support.

Weather location, SSID labels, profile names, and the `LVDS-1` monitor name remain
machine-specific values to review before using this configuration on another device.

### GlyphOS file chooser portal

After installing the user configuration, run `python3 ~/.config/glyphos/scripts/install_file_portal.py`, then `systemctl --user daemon-reload`, `systemctl --user enable --now glyphos-file-portal.service`, and `systemctl --user restart xdg-desktop-portal.service`. Refresh discovery with the installer after adding another portal backend. GTK/Qt applications prefer portal dialogs on their next launch. Browser-specific dialogs can bypass portals. Explorer handles directory/image/media MIME launches; it previews images and delegates audio/video playback to VLC.

### Direct mobile SFTP storage

Install `sshfs` (`sudo pacman -S --needed sshfs`). In Explorer’s Network & Mesh section, use Mobile Storage → Connect Phone to set the phone’s LAN IP, SSH username, port (Termux typically 8022), and remote folder. On Termux, run `termux-setup-storage` and `sshd`. Generate the PC key using the setup dialog, copy its public key, and add it to the phone’s `~/.ssh/authorized_keys`. Inspect the SSH host fingerprint and compare it with `ssh-keygen -lf $PREFIX/etc/ssh/ssh_host_ed25519_key.pub` on the phone before choosing Trust Host & Connect. SSHFS uses SSH/SFTP encryption, not TLS. Strict host-key verification and key-only authentication remain enabled.

The mount is `~/.config/glyphos/mesh/phone`; eject uses FUSE unmount and falls back to lazy unmount for broken mounts. Capacity probes and image reads run outside GTK’s main thread. Copy/move through drag-and-drop never overwrites existing files; remote Delete explicitly confirms permanent removal. The daemon retries an existing SSHFS connection with server-alive settings and reports connection loss after a bounded probe; an ejected mount stays disconnected until explicitly connected again. Personal connection profiles and SSH keys are excluded from Git.
