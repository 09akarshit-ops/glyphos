# GlyphOS desktop features

Ctrl+Shift+P opens the command palette. It is a normal GTK Wayland window,
uses dot-matrix typography, and closes on Escape or focus loss. This build
of Rofi ignored `-normal-window` on Wayland, so the dedicated picker is used.
Power actions, app launching, commands, windows, shortcuts, clipboard, files,
focus mode, connectivity, and theme selection are available there.

Super+Shift+V opens searchable text clipboard history. The second taskbar row also has
clipboard, palette, and focus buttons. “Pin clipboard snippet” pins the current
selection, or offers to unpin an existing snippet. Multiline snippets are
stored as a JSON array in `clipboard_pins.txt`.

Focus mode keeps the selected application's process tree audible and mutes
other application streams. It includes newly appearing streams, preserves
their previous mute states, and restores the previous notification mode.
The dock's Git/terminal controls follow the active application.

Ctrl+Shift+Z restores the most recent recoverable move, rename, or trash
operation in Desktop, Documents, or Downloads. The event journal uses native
inotify cookies to pair moves accurately, and Freedesktop Trash metadata for
deletions. It does not overwrite existing files. Permanent deletions, moves
outside monitored destinations, and copy/delete moves across filesystems
are not universally recoverable. No backup contents are invented.

Window memory records normal-workspace floating geometry and restores it on
relaunch, with monitor bounds clamping. Temporary minimized and desktop-hiding
workspaces are excluded. Generated class rules override initial maximization
only where saved geometry exists.

The theme setting in the palette offers Light, Dark, or Automatic. Automatic
switches at 06:00 and 18:00 local time. A saved Light or Dark preference overrides the automatic schedule.
GTK, Eww, Glyph Store, icons, Rofi theme files, and Hyprland borders support
the theme state. Third-party applications may require reopening to pick up
GTK changes. Hardcoded third-party app themes are not controlled by GlyphOS.

File search indexes names and text contents under the three user directories
with SQLite FTS5. This is local full-text matching, not an embedding model.
Index runs are bounded to 12,000 files, 20 seconds, and small text files;
filenames of other formats are indexed. A timer refreshes the index every
10 minutes. Launcher searches first show local apps and file matches. With
no matches, Gemini runs in a worker and the answer appears in the launcher.

The notification panel captures live `org.freedesktop.Notifications` calls,
groups recent notifications by application, and offers “Summarise with AI”.
That button sends the selected stack to Gemini and replaces its text with
a one-line banner. New notifications invalidate stale summaries. History is
bounded to 100 events and one day in private per-user state files.

Wi-Fi and Bluetooth buttons open non-focusable flyouts with toggles and
inline connect buttons. Wi-Fi password entry uses a normal, nonmodal GTK
window and passes credentials to NetworkManager through stdin. Bluetooth
scanning stops after eight seconds; devices requiring an interactive pairing
agent may still need pairing outside this flyout.

The top-center Eww Dynamic Island shows lyrics, media metadata, or active context.
Window controls remain in the second taskbar row.
The Store command is `~/.local/bin/glyph-store`. Taskbar context menus retain
the clicked window address and offer pinning, details, and graceful close.

## Gemini configuration

No key is required for the local features. Until configured, AI results show
an unavailable message and make no network calls.

Either create `~/.config/glyphos/gemini.json`:

```json
{"api_key":"YOUR_KEY","model":""}
```

Or copy `gemini.example.env` to `gemini.env` and set `GEMINI_API_KEY` there.
`GEMINI_MODEL` is optional. Protect the real credential file with `chmod 600`.
Then restart `glyphos-desktop.service`. With a blank model, the adapter lists
available text-generation models and caches a suitable Flash model. Requests
use an `x-goog-api-key` header and a 15-second network timeout, following
[Google's REST API documentation](https://ai.google.dev/api).

## Services and verification

`glyphos-eww.service` owns the single foreground Eww server. UI commands use
`--no-daemonize` to prevent duplicate servers on IPC timeouts, matching the
[Eww CLI's startup behavior](https://github.com/elkowar/eww/blob/master/crates/eww/src/main.rs).
`glyphos-desktop.service` owns IPC/context, notification monitoring, window
memory, and bounded worker jobs. Clipboard capture and file watching run in
their own services. Indexing runs through `glyphos-index.timer`.

The old Eww polling listeners and fullscreen dismissal surface are no longer
used. Outside-click and Escape bindings are non-consuming. No compositor input
grabs are installed. Picker and credential windows have finite lifetimes.

`verify.py` is an older interactive diagnostic and includes checks for previous
layouts and machine-specific services. Review it before use; it is not a release
validation command. It uses
disposable text/file fixtures, restores the original text clipboard, opens
and closes non-focusable panels, and sends test notifications. It does not
toggle connectivity, install apps, execute power actions, or send AI content
externally. Results are saved in `~/.local/state/glyphos/verification.json`.
Separate live checks verified palette focus-loss dismissal, floating geometry
restoration, and Store/context actions.

Machine-specific speaker restoration and personal volume settings are not
included in the distributed service set.

## Native Live Activity Island

The existing desktop service owns the GTK layer-shell Island; it is not an additional daemon. It appears only while an activity is available. Keyboard mode NONE and accept-focus false preserve application focus. Hover/click expands the most recently activated activity, 300 ms easing animates its geometry, and four idle seconds or the existing non-consuming outside-click binding collapses it. Compact activities cycle every 3.5 seconds.

Sources: playerctl media/artwork, App Store job files with numeric or indeterminate Flatpak progress and cancel, successful undo notifications (five seconds), focus state, battery below 15%/charging changes, and Bluetooth connections (five seconds). Artwork loading is bounded in the desktop worker pool. No close/minimize/maximize application controls exist in the Island; regular window controls are preserved.

Run `python3 ~/.config/glyphos/scripts/verify_island.py` for bounded live checks. It injects labeled media/install fixtures into this same daemon, automatically expiring after 22 seconds, without installing packages or playing audio. Results: `~/.local/state/glyphos/island-verification.json`. The checker validates compositor focus retention; physical typing and a real installation remain manual checks.

## Global lyric service

`glyphos-lyrics.service` owns the media timing/fetch worker independently of Eww.
It publishes an atomic snapshot under `~/.local/state/glyphos`; the Eww listener
renders two lines in the top-center black pill. The taskbar keeps its two rows
and has no GlyphOS logo; launcher branding remains.

Metadata cleanup handles local filenames, YouTube video tags, feature/production
credits and common artist/title delimiters. Lookup tries local `.lrc`/`.txt`,
LRCLIB exact then ranked fuzzy search, NetEase song search followed by lyric-ID
lookup, and plain lyrics from Genius pages, Google-discovered Genius links and
lyrics.ovh. Provider coverage and network availability vary. Plain lyrics are
estimated over track duration; missing results show scrolling metadata and retry
with bounded backoff. Cached lyrics and personal media files are excluded from Git.

Playback position is read from MPRIS on each 100 ms tick; seeks re-anchor display.
`lyrics-timing.py earlier`, `later`, `reset`, `set <ms>`, or `status` controls a
persistent offset (default -500 ms). Super+Ctrl+Left/Right adjust by 250 ms and
Super+Ctrl+Backspace resets it. Negative offsets delay line transitions.

Restart with `systemctl --user restart --no-block glyphos-lyrics.service`.
`lyrics-test-volume.py` is an optional bounded diagnostic for the named MF Gabhru
test track; it is not enabled at startup and is not a general volume policy.

Run the repository's `tests/lyrics_provider_test.py` and `tests/lyrics_web_test.py`
for offline provider/parser fixtures. Existing live-island diagnostics affect the
running desktop and should be reviewed before use.

## Interactive volume OSD

Volume Up/Down changes the default sink by 5%, capped at 100%. Mute toggles once
on press; holding it for three seconds opens pavucontrol (or qpwgraph fallback).
Releasing early cancels the hold. The non-focusable Eww glass card includes a live
slider and mute button. It fades after two seconds; hover pauses hiding and leaving
restarts the countdown. One lazy IPC worker blocks when idle and samples volume
only while visible. Slider writes are coalesced at 25 ms intervals.

Manual trigger: `~/.config/glyphos/scripts/volume_osd.sh show`.
Widget/style definitions live in `config/eww/volume_osd/` and are included by the
main Eww configuration. Install pavucontrol for the mixer command.

## Drag-and-snap layouts

Hold Super and drag a window to the top-center edge, then release over a destination
in the picker. Normal titlebar drags also activate it when window movement is detected.
Presets: halves, thirds, quadrants and a one-third sidebar. Super+Escape cancels.
The current monitor's reserved bars, scale and origin determine target bounds.

Snapping converts participating workspace windows to floating geometry. Other normal
windows on that monitor/workspace fill remaining cells; excess windows subdivide those
cells vertically. Empty cells remain if there are insufficient windows. True fullscreen,
pinned, hidden and special-workspace windows are excluded. Application minimum sizes
can prevent exact placement; arbitrary apps and multi-monitor drags need manual checks.

`glyphos-snap.service` listens to the Hyprland event socket, plus non-consuming mouse
press/release hooks because socket2 does not publish a full drag lifecycle. Direct IPC
cursor sampling runs only while a drag is armed; the worker blocks when idle. Preview
animation uses 16 ms GTK ticks over 180 ms, with an empty input region and no keyboard
grab. This targets roughly 60 FPS, which depends on compositor/hardware performance.

The Eww picker is under `config/eww/snap_layout/`; the input-transparent native GTK
preview is rendered by `snap_engine.py`. A single last-layout snapshot is stored privately
at `~/.local/state/glyphos/snap/last-layout.json`. It is a record, not an automatic undo.
Offline geometry checks: `python3 tests/snap_layout_test.py`.

The two-row taskbar reserves an additional 12 px of transparent space beneath the
controls. Window borders remain visible in both themes, and saved floating geometry
is clamped below current monitor reservations. Use Super + left-drag anywhere inside
a window; the taskbar controls themselves are not a draggable application titlebar.

## GlyphOS Files and phone storage

Super+E and the desktop/dock Files buttons open the GTK4 file manager. Its layout
follows the supplied reference: compact window controls, back/forward/up buttons,
a pill-shaped breadcrumb and search field, outline sidebar icons, five file columns
(Name, Size, Modified, Permissions, Type), and live disk/application-memory status.
Data uses standard sans-serif typography; breadcrumbs and capacity tags use Ndot 55.
No music panel appears by default. Space opens an explicit selected-file preview.

Directory scans, fd searches and bounded image/text reads run off the GTK thread.
Rows are virtualized and inserted in batches. `/` focuses search; Ctrl+L opens a
path prompt; Ctrl+H toggles hidden entries. Right-click exposes Open, Preview,
New Folder, Copy, Paste, Rename and Trash; F2 renames, Delete prompts before trash.
Copy/paste refuses overwrites. Local Share opens the user's Public folder, not a
network server. Audio previews require an available GTK media backend and do not
autoplay. Cairo rendering avoids this machine's incomplete Vulkan support; no
60 FPS guarantee or fabricated FPS number is displayed.

`glyphos-phone-mesh.service` delegates UDP discovery (1714–1764), TLS pairing and
SFTP to KDE Connect. Install KDE Connect on the phone, enable filesystem sharing,
and install `sshfs` on the PC. Backend verification details appear in the Pair
Device dialog; pair requests require confirmation on the phone, and incoming
requests require explicit acceptance. A custom six-digit PIN on both devices is
not implemented by this bridge. Backend verification-key format and RSA/EC key
choice are retained; existing credentials are never replaced.

Successfully paired certificates are pinned as SHA-256 fingerprints in private
local state. Unknown/unpaired or changed certificates cannot automatically mount.
The storage Kill Switch persists an auto-mount pause and cancels in-flight mount
requests before unmounting. Connect Storage explicitly resumes mounting. This is
a storage disconnect, not a global KDE Connect/network kill switch. Transport and
SSH host-verification behavior remain KDE Connect's implementation.

Trust, mount paths and device names are runtime data excluded from Git. On this
machine discovery was verified with zero devices; real phone pairing/mounting
still requires a phone and installation of the missing sshfs package.
Offline checks: `python3 tests/file_manager_mesh_test.py`.
