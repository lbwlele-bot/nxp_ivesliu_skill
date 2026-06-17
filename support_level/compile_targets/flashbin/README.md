# flashbin

这是启动固件 / `flash.bin` 打包对象。

它关心的不是某一个单独源码仓库，
而是最终 boot image 打包链能不能成立。

常见依赖：

- `../../code_assets/projects/imx-mkimage/`
- `../../code_assets/projects/imx-atf/`
- `../../code_assets/projects/uboot-imx/` 或 `../../code_assets/projects/real-time-edge-uboot/`
- `../../code_assets/projects/imx-optee-os/`
- `../../code_assets/projects/imx-oei/`
- `../../code_assets/projects/imx-sm/`
- `../../firmware/`
- 必要时还会依赖 `M` 核 payload 输入

正常进入方式：

- 先由 `compile` 钉死：
  SoC / 软件栈 / 版本 / 打包目标 / 最终产物类别
- 再进入相关项目 `USAGE.md`
- 再来这里确认固定输入和打包边界

不要这样用：

- 不要把 `firmware/` 当源码项目
- 不要只看某一个仓库就认定整条 `flash.bin` 链可编
- 不要直接复用旧 `work/` 产物而跳过链路核对
