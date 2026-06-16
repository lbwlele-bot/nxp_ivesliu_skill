# imx-rm

`imx-rm` 是一个给大体积 `i.MX` 参考手册用的轻量辅助工具。

它面向的是参考手册 PDF，
作用不是整本打开，而是先在 PDF 旁边建立一套索引和缓存，
这样后面查目录、查章节、查主题时，不用每次都重新扫整本手册。

当前索引侧文件包括：

- `meta.json`
- `toc.json`
- `section_spans.json`
- `aliases.json`
- `topic_bundles.json`
- `cache/sections/`
- `cache/worksets/`

另外还有一层共享别名和术语映射，
会把共用默认词表和芯片自己的补充词表合并起来。

## 常见命令

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

## 说明

- 命令名是 `imx-rm`，不是 `rm`，避免和系统删除命令冲突。
- 当前查询阶段故意保持确定性，主要按目录结构和主题索引来查。
- `list`、`lookup`、`extract`、`workset` 都支持 `--json`，方便给 skill 或脚本调用。
- `lookup`、`extract`、`workset` 返回的 JSON 里会带一些机器可读的原因字段，
  例如 `matched_by`、`consult_reason`、`selected_by`、`topic_inference`。
- 共享术语表放在 [ontology.json](/home/ives/桌面/NXP_v2/support_level/tools/imx-rm/ontology.json)，
  建索引时会和每颗芯片自己的别名文件一起合并。
- `workset` 会同时缓存 Markdown 和 JSON，
  这样后续 agent 可以在一个有界证据集上继续总结，
  不必重新整本打开 PDF。
