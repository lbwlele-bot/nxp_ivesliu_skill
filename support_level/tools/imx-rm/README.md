# imx-rm

`imx-rm` 是一个给大体积 `i.MX` 参考手册用的轻量辅助工具。

它面向的是参考手册 PDF，
作用不是整本打开，而是先在 PDF 旁边建立一套索引和缓存，
这样后面查目录、查章节、查主题时，不用每次都重新扫整本手册。

## 一句话先记住

`imx-rm` 现在不是 RAG，也不是全文搜索引擎。

它更像一个：

- `RM 章节索引器`
- `章节路由器`
- `小范围摘录缓存器`

也就是说，它当前最擅长的是：

- 先把问题路由到可能相关的章节
- 再把那几个章节抽出来
- 把这一小包证据缓存下来，供后续 agent 或人继续读

它当前还不是：

- 对整本 RM 做 embedding 的向量检索器
- 对寄存器表格做强结构解析的表格引擎
- 自动理解完整 bring-up 依赖图的知识库

## 当前架构

可以把它记成四步：

1. `build`
   先给 PDF 建 sidecar 索引
2. `lookup`
   把自由问题路由到若干候选章节
3. `extract`
   把指定章节或页码范围抽成文本缓存
4. `workset`
   把一组相关章节打成一个小工作集

对应的数据流是：

`catalog -> chosen PDF -> TOC/section/alias/topic 索引 -> query 路由 -> section extract -> workset cache`

## 当前依赖

当前主输入源是本地 RM PDF，不是 HTML。

文本抽取目前主要依赖系统里的 `pdftotext -layout`，
所以它本质上是：

- 先用 PDF 目录和章节结构定位
- 再把目标页抽成近似保留版面的纯文本

它不是直接把 PDF 当图片去读；
图片路线更适合后续人工或视觉补充，不是这个工具当前的主路径。

## RM 发现机制

当前不再只盯一个固定目录。

默认枚举根只有一个：

1. `support_level/SoC_material/*/RM/*.pdf`

用户显式传入的绝对路径不参与枚举排序，
而是在 `resolve` 时始终最高优先级。

`list --json` 会给出完整 catalog，
包括：

- `pdf_path`
- `pdf_name`
- `chip_guess`
- `revision`
- `document_identifier`
- `source_root`
- `source_name`
- `state`

如果同一个 chip 在同一优先级根里出现多个候选，
工具不会静默拍板，
而是返回歧义，让上层 agent 或人来选。

当前索引侧文件包括：

- `meta.json`
- `toc.json`
- `section_spans.json`
- `aliases.generated.json`
- `aliases.json`
- `topic_bundles.json`
- `CONTENTS.generated.md`
- `cache/sections/`
- `cache/worksets/`

另外当前 alias 是三层合并：

- 共享 `ontology.json`
- 文档自动抽取 alias
- chip overlay 手工补充

## 每类索引文件是干什么的

- `meta.json`
  记录 PDF 身份信息，例如标题、revision、页数、sha256、建索引时间。
- `toc.json`
  从 PDF 目录页抽出来的章节树，解决“有哪些章/节、起始页在哪”。
- `section_spans.json`
  在 `toc.json` 基础上补出每个章节的页码范围，解决“这一节到底覆盖哪几页”。
- `aliases.generated.json`
  从 TOC、`chip-specific`、`external signals`、顶层 `memory map and register definition` 自动抽出的 alias 和 signal 变体。
- `aliases.json`
  合并共享术语表、自动抽取 alias 和 chip overlay，解决“query 里说的词和 RM 里的正式叫法不完全一样”。
- `topic_bundles.json`
  定义一些主题包，例如 `boot-path`、`low-power`、`peripheral-bring-up`，解决“这类问题通常先看哪些章节类型”。
- `CONTENTS.generated.md`
  给大模型或人快速扫读的入口页，固定包含文档身份、章节树和高频入口章节速览。
- `CONTENTS.md`
  如果存在，视为人工维护的 curated 入口页，优先级高于 `CONTENTS.generated.md`。
- `cache/sections/`
  缓存单个章节或页码范围的抽取文本。
- `cache/worksets/`
  缓存一个小型多章节工作集，同时写 JSON 和 Markdown。

## 查询时它到底在做什么

当你执行 `lookup imx95 "tpm3 ext_clk"` 这类命令时，它不是整本全文暴力搜。

它大致会做这些事：

1. 先把 query 规范化
   例如大小写统一、`tpm3` 拆成 `tpm` 和实例 `3`
2. 做 alias 扩展
   例如 `pad`、`ext_clk`、`gpc`、`ccm` 之类会扩成共享词表、自动抽取 alias 和 chip overlay 里的相关词
3. 判断 intent
   例如这是偏 `clock`、`pinmux`、`power`、`register`、`boot` 还是某类 `peripheral`
4. 识别 peripheral family / instance
   例如识别出 `tpm3` 属于 `tpm` family 且实例是 `3`
5. 给每个章节打分
   主要看：
   - 标题命中
   - 路径命中
   - alias 命中
   - intent 命中
   - peripheral family / instance 命中
   - 是否像 companion 章节，例如 `external signals` 或 `memory map`
6. 返回排序后的候选章节，并带上命中解释和 alias 来源

所以它的核心思想不是“哪段文本最像”，而是“哪一节最像这个问题应该先去看的地方”。

## `workset` 和 `lookup` 的区别

- `lookup`
  只负责给出候选章节列表，告诉你“先看哪里”。
- `extract`
  把一个明确目标章节或页码范围抽出来。
- `workset`
  在 `lookup` 基础上，尽量拼一个小证据包。

对外设类 query，`workset` 现在是多跳的：

- 第 1 跳先挑 1-2 个 owner 章节
- 第 2 跳再按 query 派生 companion 章节
  例如：
  - `pad/extclk/rx/tx/...` -> `pinmux/iomux/external signals`
  - `register/base/address/irq/dma` -> `memory map/register`
  - `clock/pll/osc/ccm` -> `clock`
  - `power/gpc/suspend/wakeup` -> `power`
  - `security/trdc/domain` -> `security`
- 最后把这些章节都抽出来并缓存

所以 `workset` 更像：

- 不是最终答案
- 而是“下一轮阅读该用的有界材料包”

## 常见命令各自适合什么场景

- `list`
  看当前有哪些 RM 已经被发现/索引。
- `build`
  新增或刷新 sidecar 索引。
- `toc`
  先从章节树找入口，适合“我大概知道主题，但还没想好查哪节”。
- `lookup`
  适合自由问题，先路由章节。
- `extract`
  已经知道具体章节号或页码范围时，直接抽文本。
- `workset`
  适合把一个主题打成小材料包，供后续持续阅读。

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
  例如 `matched_by`、`consult_reason`、`selected_by`、`topic_inference`、`alias_source`、`hop`、`hop_reason`。
- 共享术语表放在 [ontology.json](/home/ives/桌面/NXP_v2/support_level/tools/imx-rm/ontology.json)，
  建索引时会和自动抽取 alias、每颗芯片自己的 overlay 一起合并。
- `workset` 会同时缓存 Markdown 和 JSON，
  这样后续 agent 可以在一个有界证据集上继续总结，
  不必重新整本打开 PDF。
- `CONTENTS.md` 与 `CONTENTS.generated.md` 的读取优先级固定为：
  `CONTENTS.md` -> `CONTENTS.generated.md` -> `toc.json`
- 当前最强的能力是“章节级路由和小范围阅读”，
  不是“对 RM 事实做完全结构化知识图谱”。
- 当前对段落和普通章节效果较好；
  对复杂寄存器表、矩阵表、跨章节依赖链，仍然依赖后续人工或上层 agent 继续判断。
- 对“精确基地址/驱动接线/DTS wiring”这类问题，
  `imx-rm` 适合提供章节命名和边界，
  但不一定是最快的最终证据源，代码树往往更直接。
- 当前两个基准问题：
  - `imx943 tpm3 ext_clk`
  - `imx95 lpuart rx pad`
