# linux

这是 Linux 内核侧编译对象。

它关心的是：

- kernel / dtb / modules 这一类产物
- 当前任务到底属于通用 Linux，还是 `Real-Time Edge Linux`

这里不负责决定 `flash.bin` 的打包 recipe。
Linux 线的选择可以影响 U-Boot、DTB、kernel、rootfs 或板级验证内容，
但不能直接推出 `imx-mkimage` 应该使用 `flash_a55`、`flash_all`
或其他 `soc.mak` recipe。

常见依赖：

- `../../code_assets/projects/linux-imx/`
- `../../code_assets/projects/real-time-edge-linux/`
- `../../toolchain/`
- 必要时还会回看 `../../board_knowledge/` 和 `../../firmware/`

正常进入方式：

- 先由 `compile` 判断当前属于哪条 Linux 线
- 再确认本次只需要 Linux 侧产物，还是这些产物还要进入完整启动镜像链路
- 再进入对应项目 `USAGE.md`
- 需要 case 构建时，复制到 `../../work/<case>/` 再做

与 `flashbin` 的关系：

- 如果只是改 kernel / dtb / modules，
  本对象负责把 Linux 侧产物准备好
- 如果最终要生成可烧写启动镜像，
  Linux 侧产物准备好以后还要回到 `../flashbin/`
- `flashbin` 负责确认 boot image 输入集合和最终打包 recipe

不要这样用：

- 不要因为某个 workspace 里带了 Linux 相关配套目录，就直接从 workspace 开始编
- 不要在源码资产目录里原地生成 case 输出
- 不要把通用 Linux 或 Real-Time Edge Linux 直接等同于某个 `flash.bin` recipe
