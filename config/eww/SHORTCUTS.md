# GlyphOS shortcuts and recovery guide

Verified against `~/.config/hypr/hyprland.conf`, live Hyprland bindings, and `~/.config/eww/eww.yuck` on 2 October 2026.

**Super** means the Windows / Command-logo key. Shortcuts below reflect the current configuration; example shortcuts that are not configured are identified explicitly. Terminal commands assume Bash.

## General navigation

| Action | Shortcut | What happens |
| --- | --- | --- |
| File Explorer | **Super + E** | Opens Dolphin. |
| Terminal | **Super + Q** | Opens Kitty; this does **not** close a window. |
| GlyphOS Launcher / Start menu | **Tap and release left Super** | Toggles the Eww app launcher. |
| Application runner | **Super + R** | Opens Rofi's application list. |
| Show / restore desktop | **Super + D** | Hides unpinned windows on the current workspace; press again to restore them. |
| Close active window | **Super + C** | Requests a normal close; an app may ask to save or confirm. |
| Minimize active app | **Super + S** | Sends it to `special:minimized`; click its taskbar icon to restore. |
| View minimized workspace | **Super + Shift + S** | Toggles the minimized special workspace. |
| Fullscreen / restore | **Super + F** | Toggles true fullscreen, which can hide the taskbar/header. |
| Floating / tiled | **Super + V** | Toggles the active window's floating state. |
| Switch workspace | **Super + 1 / 2 / 3 / 4** | Switches to that workspace. |
| Move active window to workspace | **Super + Shift + 1 / 2 / 3 / 4** | Moves the window and follows it. |
| Control Center | **Super + N** | Opens Control Center. |
| Settings | **Super + I** | Opens Eww Settings. |
| Lock screen | **Super + L** | Starts Hyprlock. |
| Dismiss Eww panels | **Super + Escape** | Closes overlays and the outside-click backdrop. |
| Dismiss current Eww panel | **Escape** or click outside | Escape is temporarily bound while an overlay is open. |
| Exit the desktop session | **Super + M** | **Ends Hyprland and your graphical session. It does not minimize.** |

**Alt + F4 is not globally configured.** An individual app might handle it. **Super + Shift + Q is not configured.**

Apps normally open maximized, keeping the top bar/header visible. Maximized and true fullscreen are different modes.

## Window buttons and taskbar

Traffic lights are at the right of the shared app header and Eww panel titlebars.

| Control | Native application | Eww panel |
| --- | --- | --- |
| Red × | Requests a normal close. | Closes the panel. |
| Yellow − | Minimizes into `special:minimized`. | Hides the panel and adds a restore entry to the taskbar. |
| Green expand | Toggles maximize / restore, keeping the bar visible. | Toggles panel size between normal and the available screen area. |
| Taskbar icon | Focuses an inactive app, minimizes the active app, or restores a minimized app. | Restores a minimized panel. |

The shared header controls the currently selected native app. To dismiss Control Center, use its × button, Escape, Super + Escape, or click outside it.

## System and multimedia controls

Volume, brightness, and playback hardware keys are **not bound in Hyprland**. Use Control Center, Now Playing, or these commands:

| Action | GUI control | Terminal command |
| --- | --- | --- |
| Volume up 5% | Control Center → Volume slider | `wpctl set-volume -l 1.0 @DEFAULT_AUDIO_SINK@ 5%+` |
| Volume down 5% | Control Center → Volume slider | `wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-` |
| Mute / unmute | Control Center → Mute | `wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle` |
| Brightness up 5% | Control Center → Brightness slider | `brightnessctl set +5%` |
| Brightness down 5% | Control Center → Brightness slider | `brightnessctl -n set 5%-` |
| Play / pause | Now Playing → middle button | `playerctl play-pause` |
| Previous track | Now Playing → left button | `playerctl previous` |
| Next track | Now Playing → right button | `playerctl next` |
| Night Light | Control Center → Night Light | `~/.config/eww/scripts/toggle-nightlight.sh` |
| Disable Night Light | Click the active Night Light button | `~/.config/eww/scripts/toggle-nightlight.sh off` |
| Do Not Disturb | Control Center → DND | `~/.config/eww/scripts/control-center.py dnd` |
| Wi-Fi / Bluetooth | Control Center pills or top-bar status icons | `~/.config/eww/scripts/control-center.py wifi` / `bluetooth` |
| Restore latest notification | Control Center → Priority Notifications | `makoctl restore` |

Slider percentages update as you adjust them. Night Light uses a native Hyprland warm-color shader. The battery bolt indicates AC power, including when the battery is full.

### Screenshots

| Shortcut / control | Result |
| --- | --- |
| **Super + P** | Full-screen image saved as `~/Pictures/screenshot-YYYYMMDD-HHMMSS.png`. |
| **Print Screen** | Configured for region selection with Slurp, saving to `~/Pictures/Screenshots/` and copying to clipboard. See dependency note below. |
| Control Center → **Screenshot** | Closes the panel and saves a full-screen image to `~/Pictures/Screenshots/`. |

The Print Screen binding currently uses Bash process substitution and calls `wl-copy`, which is **not installed**. Clipboard copying is unavailable, and the binding may fail if launched through a shell without Bash syntax support. This guide does not change that binding. For dependable region capture without clipboard copying, run:

```bash
mkdir -p ~/Pictures/Screenshots
region=$(slurp) && grim -g "$region" "$HOME/Pictures/Screenshots/region-$(date +%Y%m%d-%H%M%S).png"
```

### Clipboard

**Ctrl + C** and **Ctrl + V** copy and paste in most graphical apps. These are app shortcuts, not Hyprland bindings. In Kitty, use **Ctrl + Shift + C / V**; Ctrl + C interrupts a terminal program. No global clipboard-history shortcut is configured.

## Task Manager and process controls

Open the GUI CPU-process overview from Launcher → Task Manager, or run:

```bash
eww open task-manager
```

Its **Open Full Task Manager** button opens `htop` in Kitty. You can also run `kitty -e htop`. In htop, select the process, press **F9**, choose **SIGTERM**, and confirm. Use **SIGKILL** only if normal termination fails; it discards that process's unsaved work.

The Eww overview itself displays CPU usage; process termination happens in htop. No global Task Manager hotkey is configured.

## Emergency recovery

Work through these steps in order. Reloading widgets preserves native apps; restarting the compositor ends the graphical session.

### 1. Release a stuck overlay

Press **Super + Escape**, or run:

```bash
~/.config/eww/scripts/modal.py close
```

If the panel remains stuck, try `eww close-all`. This also hides desktop widgets; restore them with `~/.config/eww/scripts/start-desktop.sh`.

### 2. Reload configuration or widgets

```bash
hyprctl reload
hyprctl configerrors
eww reload
```

`hyprctl reload` reloads configuration, **not the compositor process**. `eww reload` reloads widget definitions, **not the Eww daemon**. Neither can repair a compositor that no longer responds to IPC.

**Super + Shift + R is not configured.** There is also no dedicated Eww-recovery hotkey.

### 3. Restart Eww without rebooting or closing native apps

If reload fails or Eww stops responding:

```bash
pkill -TERM -x eww
pkill -f '^python3 /home/nothing_os/.config/eww/scripts/modal.py watch$'
sleep 1
~/.config/eww/scripts/start-desktop.sh
```

If an Eww process survives normal termination, replace the first command with `pkill -KILL -x eww`, then repeat the watcher cleanup and startup commands. This restores the bar, app header, desktop widgets, Now Playing, and dock. The startup script redirects daemon logs to `~/.config/eww/.desktop-daemon.log`.

To restore a missing wallpaper, run `~/.config/eww/scripts/set-wallpaper.sh`.

### 4. Terminate one frozen app

Super + C and the red traffic light request a normal close; they do not forcibly kill a process. Use htop, or inspect the active app before killing it:

```bash
hyprctl activewindow -j
app_pid=$(hyprctl activewindow -j | jq -r '.pid')
if [[ "$app_pid" =~ ^[1-9][0-9]*$ ]]; then
    kill -TERM "$app_pid"
fi
```

If that same process remains frozen, run `kill -KILL "$app_pid"`. Force-killing can lose unsaved work, and killing a browser process may close multiple windows. `killall APP_NAME` terminates all matching processes; use a verified PID when you want to target one process.

### 5. Switch to a text console (TTY)

Press **Ctrl + Alt + F3** and log in as your normal user. On some keyboards, also hold **Fn**. This is a Linux virtual-console shortcut, not a custom GlyphOS binding. To return to the desktop, try Ctrl + Alt + F1 or F2; the graphical VT varies.

A TTY usually lacks the desktop's Wayland/Hyprland environment. Before issuing desktop commands:

```bash
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
hyprctl instances
ls "$XDG_RUNTIME_DIR"/wayland-*
```

Copy the running instance's **instance signature** from `hyprctl instances`, then set:

```bash
export HYPRLAND_INSTANCE_SIGNATURE='PASTE_THE_RUNNING_INSTANCE_SIGNATURE_HERE'
export WAYLAND_DISPLAY=wayland-1
```

`wayland-1` is this session's current display name; use the actual socket name shown by `ls` if it differs. Then try the reload, Eww recovery, or targeted process-termination steps above. If several Hyprland instances exist, select your own graphical session.

### 6. Last resort: restart the graphical session, without rebooting

If Hyprland itself is frozen and TTY access still works, `pkill -TERM -x Hyprland` ends the compositor. Log back in through the display manager to start a new session. **This closes graphical apps and can lose unsaved work.** It is not an in-place reload. A hardware reboot should not be needed for an Eww-only failure.

## Check the configuration after changes

```bash
hyprctl binds -j
hyprctl configerrors
eww active-windows
```

The first command shows live bindings. Escape's temporary modal binding appears only while an overlay is open. Keep this guide aligned with changes to `hyprland.conf`, `eww.yuck`, and the scripts they call.

Reference: [Hyprland's reload command](https://github.com/hyprwm/Hyprland/discussions/1849) and [window-close semantics](https://wiki.hypr.land/0.41.0/Configuring/Dispatchers/).
