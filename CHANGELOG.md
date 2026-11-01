# Changelog

## 2026-11-02 — desktop integration, media policy and Night Light

- Add a right-click Night Light intensity slider inside Control Center. Persist
  intensity, coalesce rapid changes, and restore the previous shader on disable.
- Add Codex and Spotify dock icons; unify white icon styling, hover lift and
  running-window indicators. Keep transparent individual icon backgrounds.
- Route system window controls to the Settings layer and remove duplicate controls.
- Add Spotify F11 fullscreen handling with the Island retained above fullscreen.
- Exclude YouTube/Instagram and unidentified browser media from music artwork and
  lyrics; preserve native players and identified Spotify web playback.
- Refine idle glass surfaces, playback artwork handoff and white desktop lettering.
- Include the selected wallpaper and document its awww/swww runtime command.

Validation: Night Light shader/restoration tests; dock running-app detection;
Settings control routing; Spotify fullscreen restoration; browser media filtering;
Start/Power lifecycle; artwork handoff; fullscreen Island; VLC queue guards and snap
partitions. Live Night Light and screenshot verification are recorded in the gallery.


## 2026-10-30 — dock customization, dark desktop and Start refinement

- Add persistent dock app lists, ordering, hiding/restoration, color preferences,
  application selection, icon removal, and confirmed uninstall flows. Super+Alt+D
  restores Dock Options. Uninstall is disabled for protected components and shortcuts.
- Fix actual icon/gap right-click handling and premature layer-focus dismissal;
  retain circular icons and restore the original light dock palette.
- Add Settings, Music and Photos to the dock; remove the separate desktop app row.
- Use a clean charcoal wallpaper derived from the supplied reference, with baked-in
  UI and the corner logo removed. Render live white weather/clock lettering.
- Match Now Playing to the reference card, raise it 24px, and fix rounded shadow
  clipping. Give the player a brighter glow and the dock a restrained glow.
- Restore the player artwork layer and share a cached blurred cover with the dock.
  Preserve artwork during handoff, retry blur failures, reject stale results and
  bound resolver work to one in-flight request.
- Preserve Classic Light and Charcoal reference snapshots for future theme work.
- Refactor Start to dark frosted search/tiles, compact transparent sidebar items,
  standard Inter typography and an upward entrance. Attach Power options inline
  without closing Start. Preserve all launcher commands and input handlers.
- Make Super+P save PNG screenshots to Pictures, copy them with image/png MIME,
  and notify on success or partial failure.

Validation: fixture tests for dock persistence/order/removal/color, Start/Power
lifecycle, artwork handoff/retry/stale-result handling and screenshot success/failure
paths; real icon/gap right-click checks and visual inspection of rounded glow,
artwork and Start. No application uninstall or destructive power action was tested.
Current artwork was inspected without issuing playback controls. Personal dock
preferences, clipboard contents, credentials and runtime media data remain excluded.

## 2026-10-29 — boot, taskbar and file navigation fixes

- Add VLC queue controls to Now Playing and the expanded Island, with selectable
  real MPRIS playlist entries in a compact panel below the Island. Defer Spotify
  queues; label shuffle lists as playlist order rather than predicted playback order.
- Restore the idle Now Playing card’s off-white surface, border, shadow and spacing;
  brighten playback artwork and constrain long lyric lines to the Island’s width.
- Recover artwork for reversed local title/artist metadata and correctly parse
  song-first filenames with featured-artist credits for synchronized lyrics.
- Add standard previous/play-pause/next media key bindings for compatible players.
- Repair browser attachment/save pickers by starting their portal with the active
  Wayland environment after the graphical session becomes available.
- Remove duplicate Files window controls; enable rubber-band multi-selection,
  group copy/trash/drag operations, and preserve single-file portal request limits.
- Match the unplugged battery outline to the charging icon without its bolt.
- Fix the taskbar opening-click dismissal race and transient layer focus changes.
- Make Super+I open Settings maximized within the usable desktop bounds.
- Document Plasma Login autologin into Hyprland with immediate startup Hyprlock;
  retain the standard greeter as a fallback and keep credentials out of the repository.

Validation: mocked VLC queue ordering/selection and fixture-only queue UI; real
OpenFile/SaveFile portal opening and cancellation; filename parsing and synchronized
Kala Doriya lookup; selection/group-copy fixtures; taskbar click-dismiss regression
and live Wi-Fi/Bluetooth/battery panel persistence; Settings geometry 1600×804 below
the 96px taskbar. The user confirmed direct-to-Hyprlock boot after reboot. No queue
selection tests changed live playback. End-to-end mouse rubber-band interaction
and a real VLC playlist selection still require manual verification.

## 2026-10-08 — personalized desktop and native file integration

- Add shared artwork backgrounds to the Dynamic Island and desktop Now Playing
  card, using local covers, MPRIS artwork URLs and matching catalog fallbacks.
- Center current lyrics with smooth slide/fade transitions and preserve separate
  per-recording timing adjustments. Expand the Island into an artwork-backed
  full-song lyric view with seeking, playback controls and a two-second grace period.
- Show only the Island above fullscreen windows; restore the original two-row
  taskbar on exit. Keep the off-white bar and transparent connectivity buttons.
- Rebuild the settings layout and GlyphOS Files around the reference designs.
- Register directory/image/media associations and a real asynchronous FileChooser
  portal supporting multi-selection, filtering, cancellation and save requests.
- Add phone discovery and trusted KDE Connect storage, optional direct SSHFS
  mounting, eject/recovery, recursive transfers and asynchronous image thumbnails.
- Add interactive volume OSD/media bindings, mute-hold mixer access and snap layouts.
- Refine lock-screen branding, profile layout and Account Help controls.

Validation: Python syntax and whitespace checks; snap, file manager, phone trust,
artwork and mobile storage fixtures. Live checks covered artwork/lyrics, 20% audio,
portal routing/cancellation and fullscreen Island enter/exit restoration. Direct
phone mounting remains untested: SSHFS installation and phone SSH setup are required.
Spotify artwork was tested through mocked MPRIS metadata, not a live Spotify session.
Private SSH keys, phone connection profiles and runtime state remain excluded.

## 2026-10-06 — desktop and global lyrics snapshot

- Restore the black Dynamic Island and retain the compact two-row taskbar, with
  the pill at top center and no taskbar logo. Enlarge active/secondary lyrics.
- Repair palette, clipboard and focus click actions; keep separate window controls,
  uniform circular dock icons, and remove trailing dock action buttons.
- Add clipboard Copy/Delete cards and immediate refresh without reopening overlays.
- Add metadata cleanup, local lyrics, ranked LRCLIB/NetEase lookup and plain-text
  web fallback. Use actual MPRIS position, persistent timing offsets, bounded
  fetches/caches, retry backoff and scrolling metadata when lyrics are missing.
- Package an independent lyrics user service and its Eww snapshot listener, plus
  required desktop, clipboard, indexing, theme and App Store helpers.
- Add Alt+Tab cycling, mouse configuration adjustments, and an optional Gemini
  browser launcher with separate profile and cgroup resource limits.
- Update manual installation/service instructions and exclude personal runtime data.

Verification includes offline provider/web fixtures and syntax checks. Earlier
live-session checks covered lyric line changes, timing controls, clipboard actions
and utility buttons. NetEase lookup was fixture-tested; its live endpoint timed
out in this environment. Provider coverage and compositor responsiveness on other
hardware remain unverified. This snapshot is not an ISO or a tagged release.
