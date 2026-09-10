# SoC_material

这里放按 SoC 组织的资料资产，例如：

- RM
- 原理图
- 硬件设计资料
- 其他芯片级参考文档

这一层首先回答：

- 某颗 SoC 的资料是否已经在本地
- RM / 原理图 / 其他资料分别放在哪
- 已有资料是否带有工具生成的 sidecar

## 当前本地资料入口

当前本地已经按 SoC 整理了以下资料根：

- `i.MX8DXL/`
- `i.MX8M/`
- `i.MX8MM/`
- `i.MX8MN/`
- `i.MX8MP/`
- `i.MX8ULP/`
- `i.MX91/`
- `i.MX93/`
- `i.MX943/`
- `i.MX95/`

Git 只保存这份入口说明，不保存原始 PDF 和生成的全文索引。
具体资料是否存在、版本是否匹配，仍以当前本地目录为准。

## RM 内容读取规则

对 `i.MX` RM 内容类问题，默认必须先使用：

- [../tools/imx-rm/USAGE.md](../tools/imx-rm/USAGE.md)

推荐顺序是：

1. 用 `lookup` 或 `workset` 定位章节
2. 用 `extract` 抽取证据
3. 再根据证据决定是否需要补读原始 PDF

原始 `RM/*.pdf` 仍是权威来源，
但直接翻 PDF 是 fallback。

只有下面情况才直接回到原始 PDF：

- `imx-rm` 找不到对应 RM
- 索引构建或章节抽取失败
- 工具结果明显缺章节或误路由
- 问题需要确认 PDF 版面、图、复杂表格
- 用户明确要求直接查原始 PDF

## 目录约定

典型形态是：

```text
SoC_material/
  i.MX95/
    RM/
      IMX95RM.pdf
      IMX95RM.index/
```

其中：

- `RM/*.pdf` 是原始参考手册
- `RM/*.index/` 是 `imx-rm build` 生成的 sidecar 索引目录
- `tools/imx-rm/USAGE.md` 是 `imx-rm` 的工具使用入口

如果只是在找资料位置，留在这一层。
如果已经明确要操作 `imx-rm`，进入工具目录读取 `USAGE.md`。
