# imx-rm

- 程序入口：`./imx-rm`
- 当前版本：工作区本地脚本
- 工具角色：大体积 `i.MX` RM 的 catalog、章节路由、章节摘录、workset 收敛

## 先读什么

先确认四件事：

1. 当前目标 SoC 或具体 RM PDF 是否明确
2. 当前动作是在做：
   - 列出本地 RM catalog
   - 给 RM 建 sidecar 索引
   - 从自然语言问题定位候选章节
   - 抽取指定章节文本
   - 为跨章节问题生成 workset
3. 问题是否需要跨章节 companion，例如 `pinmux`、`clock`、`power`、`security`
4. 这次要证明的是 RM 章节事实，还是源码 / DTS / driver 里的落地实现

## 典型命令形态

列出本地 RM：

```bash
/home/ives/桌面/NXP_v2/support_level/tools/imx-rm/imx-rm list --json
```

给某份 RM 建索引：

```bash
/home/ives/桌面/NXP_v2/support_level/tools/imx-rm/imx-rm build imx943
```

按问题定位候选章节：

```bash
/home/ives/桌面/NXP_v2/support_level/tools/imx-rm/imx-rm lookup imx943 "tpm3 external clock" --json
```

为跨章节问题生成 workset：

```bash
/home/ives/桌面/NXP_v2/support_level/tools/imx-rm/imx-rm workset imx943 "tpm3 external clock" --json
```

抽取目标章节：

```bash
/home/ives/桌面/NXP_v2/support_level/tools/imx-rm/imx-rm extract imx943 130.4 --context-pages 1
```

## 使用边界

- `imx-rm` 面向本地 RM PDF，不直接抓远端 HTML
- `imx-rm` 是结构优先的章节工具，不是向量数据库或完整 RAG
- `lookup` 偏单跳章节解释，适合先看 owner chapter
- `workset` 偏多跳证据收敛，适合外设相关的 `pinmux / clock / power / security` 问题
- `extract` 只抽指定章节或页码范围，不替代后续人工判断
- 精确基地址、DTS 节点、驱动绑定、Linux 行为这类问题，RM 只能作为辅助证据，主证据应回到 `code_assets/`

## 当前注意事项

- 默认枚举 `support_level/SoC_material/*/RM/*.pdf`
- 用户显式传入具体 PDF 路径时，按该路径解析
- 每份 PDF 的 sidecar 索引目录位于同目录的 `<PDF stem>.index/`
- `CONTENTS.md` 是人工整理入口，优先级高于 `CONTENTS.generated.md`
- `CONTENTS.generated.md`、`toc.json`、`section_spans.json`、`aliases.json`、`topic_bundles.json` 都是工具生成或使用的索引文件
- `build --force` 会重建 generated sidecar，普通 `build` 会按 PDF hash、schema version 和 ontology hash 判断是否复用缓存

更完整的原理和数据结构说明见：

- [README.md](/home/ives/桌面/NXP_v2/support_level/tools/imx-rm/README.md)
