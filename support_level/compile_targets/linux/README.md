# linux

这是 Linux 内核侧编译对象。

它关心的是：

- kernel / dtb / modules 这一类产物
- 当前任务到底属于通用 Linux，还是 `Real-Time Edge Linux`

常见依赖：

- `../../code_assets/projects/linux-imx/`
- `../../code_assets/projects/real-time-edge-linux/`
- `../../toolchain/`
- 必要时还会回看 `../../board_knowledge/` 和 `../../firmware/`

正常进入方式：

- 先由 `compile` 判断当前属于哪条 Linux 线
- 再进入对应项目 `USAGE.md`
- 需要 case 构建时，复制到 `../../work/<case>/` 再做

不要这样用：

- 不要因为某个 workspace 里带了 Linux 相关配套目录，就直接从 workspace 开始编
- 不要在源码资产目录里原地生成 case 输出
