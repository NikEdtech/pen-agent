---
name: pen-agent
description: >-
  Give your agent a pen. Use when the user wants to write or draw on a physical
  GRBL pen plotter (JinGan / BtWriter class), generate handwriting (Latin or
  Cyrillic), thank-you postcards, SVG plots, dry-run previews, or webcam
  verification of the paper. Prefer dry-run + preview + human confirm before
  any live plot.
---

# pen-agent

You control a physical pen plotter through the **pen-agent** MCP server.

## Hard rules

1. **Default to dry-run.** Call `write_text` / `draw_svg` / `plot` with `dry_run=true` first.
2. Show the human the preview (`preview_path` or decode `preview_png_b64`).
3. Only plot live with `dry_run=false` **and** `confirm=true` after the human says the paper is loaded and origin is set.
4. On alarm or odd motion, call `abort` immediately.
5. After a live job, optionally `capture_photo` to verify the result.

## Typical flow

1. `list_ports` / `status` — is the machine connected?
2. Human parks carriage at sheet corner with pen raised → you call `home` (sets `G92`, not `$H`).
3. `write_text` or `draw_svg` with `dry_run=true`.
4. Share preview; wait for confirmation.
5. Live: same tool with `dry_run=false, confirm=true`.
6. `capture_photo` to see the page.

## Handwriting tips

- Use `template="thankyou"` for small-shop thank-you postcards.
- Keep `jitter_mm` around `0.08–0.12` and `baseline_wobble_mm` around `0.12–0.2` for natural look.
- Paper: `A4` / `A5` / `A6` / `postcard`.
- Cyrillic is supported (stick single-stroke font).

## Safety facts (JinGan)

- Pen down = `M3` + Z+, pen up = Z0 + `M5`.
- Soft-reset clears work zero — call `home` again.
- Never enable laser mode `$32=1`.
- One job at a time (server lock).
