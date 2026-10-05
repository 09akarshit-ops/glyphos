# Changelog

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
