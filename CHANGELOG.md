# Changelog

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
