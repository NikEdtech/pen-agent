# Architecture

pen-agent is a thin, safe agent layer over [`grbl-pen-plotter`](https://github.com/NikEdtech/grbl-pen-plotter).

```
┌─────────────────────────────────────────────────────────┐
│  Agent host (Claude Desktop / Cursor / Codex / …)       │
│    skills/pen-agent/SKILL.md                            │
└───────────────┬──────────────────────────▲──────────────┘
                │ MCP stdio / streamable HTTP│ capture_photo
                ▼                            │
┌─────────────────────────────────────────────────────────┐
│  pen-agent                                              │
│   FastMCP tools  →  PenService (RLock, dry-run, limits) │
│   handwriting / postcard templates                      │
│   OpenCV webcam                                         │
└───────────────┬─────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────┐
│  grbl-pen-plotter                                       │
│   ports · GRBL client · stream · SVG/text · preview     │
└───────────────┬─────────────────────────────────────────┘
                │ USB serial (cu.usbserial* / COMn / ttyUSB*)
                ▼
              GRBL pen plotter
```

## Trust boundaries

- **Dry-run default** keeps agents from moving metal by accident.
- **`confirm=true`** is a second explicit gate for live plots.
- **HTTP Bearer token** protects the Windows always-on endpoint on LAN/Tailscale.
- **Job lock** prevents two agents from streaming at once.
