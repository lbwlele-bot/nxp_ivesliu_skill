# firmware

这里放固定二进制输入。

它不放源码，也不放 case 里临时生成的产物。

适合放的内容包括：

- DDR firmware
- ELE / AHAB container
- vendor firmware package 解包结果
- 其它不应和 `code_assets/projects/` / `code_assets/workspaces/` 混在一起的固定输入

## 使用规则

1. 先确认当前任务是不是在找固定二进制输入
2. 先按 SoC 根目录找
3. 再进具体 vendor package 目录核对文件名和版本
4. 不要只因为“某个文件出现在某个包里”，就把那个包目录名当成唯一 provenance

## 当前目录模型

当前已经有这些 SoC 根：

- `imx8dxl/`
- `imx943/`
- `imx95/`

每个 SoC 根下面允许保留 vendor package 的原始解包形态。
所以你看到的常常不是“一个文件一个平铺目录”，
而是：

```text
firmware/
  <soc>/
    <vendor-package>/
      ...
```

## 已吸收：`imx95-rte33-build-flashbin` 的 firmware 边界

对 `i.MX95 RTE 3.3 flash.bin`，
旧 skill 的稳定要求不是“再下载一份 firmware”，
而是先确认：

- canonical reusable root 在 `../support_level/firmware/imx95/`
- 先看本地有没有所需 vendor package
- 没有时才考虑补下载

当前这个 SoC 根里已能看到：

- `firmware-ele-imx-2.0.3-286c884/`
- `firmware-imx-8.29-8741a3b/`

## 多 SoC payload 注意事项

vendor package 解包目录本身可能包含多颗 SoC 的 payload。

例如一个 `firmware-ele-imx-*` 目录里，
可能同时看到：

- `mx943...`
- `mx95a0...`
- `mx95b0...`

所以：

- “文件在某个 vendor package 目录里”
  不等于“它天然只属于这个 SoC 根”
- 真正 output-affecting 的，是：
  具体文件名
  具体 revision
  以及当前链路要求的 SoC / rev 身份

对 `i.MX95` 这类链路，尤其要防止：

- 把 `A0` / `B0` 混看
- 只看目录名字，不看实际文件名字
- 把错误 revision 的 blob 误判成 传输 问题

## 当前推荐读取方式

如果任务是 `flash.bin` build：

1. 先读相关源码项目 `USAGE.md`
2. 再来这里确认固定输入根目录
3. 明确记录：
   - 当前要用哪个 package
   - 当前要用哪个 SoC / rev 对应文件

如果任务是 `i.MX8DXL`，优先看：

- `validated-lf-6.18.2-1.0.0/`

如果任务是 `i.MX95 RTE 3.3`，
当前先把 `imx95/` 当成本地 canonical root，
不要再反过来把 `imx943/` 下带出来的 `mx95*` 文件当默认入口。

## 当前不该怎么用

- 不要把 `firmware/` 和 `code_assets/projects/` / `code_assets/workspaces/` 混读
- 不要在这里生成临时 build 输出
- 不要让 case 操作手册直接写死一个旧共享根路径而跳过这里
- 不要在 revision 不清楚时继续往下烧写或打包
