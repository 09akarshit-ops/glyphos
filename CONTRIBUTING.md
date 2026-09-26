# Contributing to GlyphOS

This started as a personal desktop customization project and is still under active, fast-moving
development. Contributions are welcome, but a few notes:

## Before opening a PR

- Widget code lives in `config/eww/eww.yuck` (structure) and `config/eww/eww.scss` (styling).
  Check parentheses/brace balance before submitting — `eww` fails silently on mismatched
  brackets and can break the entire desktop shell.
- Keep the light, minimal aesthetic — no dark-mode-only additions, no gradients or heavy shadows.
- Test any change with `eww kill; pkill -9 eww; sleep 1; eww daemon; sleep 1; eww open <window>`
  before submitting.

## Reporting bugs

Open an issue with:
- What you expected to happen
- What actually happened (a screenshot helps a lot)
- Output of `eww logs` if the issue is visual/rendering related

## Feature requests

Open an issue describing the feature. Check the [Roadmap](./README.md#roadmap) first —
it might already be planned.
