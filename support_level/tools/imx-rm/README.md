# imx-rm

`imx-rm` is a lightweight helper for large i.MX reference manuals stored under
`/home/ives/桌面/NXP/pre_download/RM`.

It avoids whole-document loading by building a sidecar index next to each PDF:

- `meta.json`
- `toc.json`
- `section_spans.json`
- `aliases.json`
- `topic_bundles.json`
- `cache/sections/`
- `cache/worksets/`
- a merged alias and ontology layer that combines shared defaults with chip-specific overlays

## Commands

```bash
/home/ives/桌面/NXP/tools/imx-rm/imx-rm list
/home/ives/桌面/NXP/tools/imx-rm/imx-rm list --json
/home/ives/桌面/NXP/tools/imx-rm/imx-rm build all
/home/ives/桌面/NXP/tools/imx-rm/imx-rm toc imx943 boot
/home/ives/桌面/NXP/tools/imx-rm/imx-rm lookup imx943 "serial downloader boot mode" --json
/home/ives/桌面/NXP/tools/imx-rm/imx-rm lookup imx95 "suspend wakeup and gpc clock interaction"
/home/ives/桌面/NXP/tools/imx-rm/imx-rm lookup imx95 "tpm3 ext_clk" --json
/home/ives/桌面/NXP/tools/imx-rm/imx-rm lookup imx95 "lpuart rx pad" --json
/home/ives/桌面/NXP/tools/imx-rm/imx-rm extract imx943 4.10 --context-pages 1 --json
/home/ives/桌面/NXP/tools/imx-rm/imx-rm extract imx943 4.3.4 --context-pages 1
/home/ives/桌面/NXP/tools/imx-rm/imx-rm workset imx95 "suspend wakeup and gpc clock interaction" --json
/home/ives/桌面/NXP/tools/imx-rm/imx-rm workset imx95 "tpm3 ext_clk" --json
/home/ives/桌面/NXP/tools/imx-rm/imx-rm workset imx943 boot-path
```

## Notes

- The command name is `imx-rm`, not `rm`, to avoid clobbering the system
  delete command.
- The current lookup phase is intentionally deterministic and TOC-driven.
- `list`, `lookup`, `extract`, and `workset` support `--json` for skill-facing
  calls.
- `lookup`, `extract`, and `workset` JSON now carry machine-facing reason
  fields such as `matched_by`, `consult_reason`, `selected_by`, and
  `topic_inference`.
- The shared vocabulary now lives in [ontology.json](/home/ives/桌面/NXP/tools/imx-rm/ontology.json)
  and is merged with each chip's sidecar aliases during index build.
- Worksets are cached as Markdown plus JSON so later agents can summarize from
  a bounded evidence set instead of reopening the full PDF.
