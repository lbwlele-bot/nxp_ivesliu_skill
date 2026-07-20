# imx-mkimage

- 真实源码目录：`./imx-mkimage/`
- 最近观察分支（使用前重新核对）：`lf-6.12.49_2.2.0`
- 最近观察版本（使用前重新核对）：`lf-6.12.49-2.2.0`
- 主要链路：`flash.bin` 打包工具

## 角色

`imx-mkimage` 是最终 boot image 打包工具。

它不负责决定整条启动固件链需要哪些输入，
也不负责决定软件栈是 generic Linux 还是 `RTE`。
这些上层判断先由：

- `../../../compile_targets/flashbin/README.md`
- `../../../software_stacks/rte.md`

完成。

本页只负责：当上层已经决定要用 `imx-mkimage` 打包时，
这个项目本身怎么核对、准备输入、运行 `soc.mak` recipe、交出产物。

## 使用前提

进入本页前，必须已经钉死：

- 目标 SoC，例如 `iMX94` / `iMX95`
- 板型、DDR 类型、必要的 SoC revision
- 软件栈和版本家族
- 最终 recipe，例如 `flash_a55` / `flash_all`
- 是否需要 `OEI=YES`
- 是否需要 `OP-TEE` 输入
- 是否需要 M 核 payload 输入
- 固定 firmware blob 来源
- 各上游输入件的来源和版本

如果这些还没确定，先回到 `compile_targets/flashbin/README.md`。
如果任务属于 `RTE`，先读 `software_stacks/rte.md`。

## 共享源码规则

1. 先用 `git status --short --branch` 和 `git describe --tags --always --dirty` 核对当前 ref
2. 只读检查可直接在共享源码目录做
3. 要改、要打包、要生成输出，复制到 `../../../work/<case>/` 再做
4. 不要把旧 `work/` 里的 `flash.bin` 直接当作当前任务产物，除非它的来源、版本、配置都已经被当前 case 重新确认

## 打包输入契约

`imx-mkimage` 消费的是已经准备好的上游输入件。
典型输入包括：

- `bl31.bin`
- `u-boot.bin`
- `u-boot-spl.bin`
- `oei-m33-ddr.bin`
- `m33_image.bin`
- `tee.bin`，仅当所选软件栈需要 `OP-TEE`
- M 核 payload，只有所选 recipe / 软件栈 / case 需要时才带入
- DDR / ELE / AHAB 等固定 firmware blob

输入集合由上层 `flashbin` 编排和软件栈决定。
不要只因为某个文件在目录里存在，就默认它应该进入本次 `flash.bin`。

## 常见命令形态

`i.MX943` 在 `imx-mkimage` 中通常使用 `SOC=iMX94`：

```bash
cd /home/ives/桌面/NXP_v2/support_level/work/<case>/imx-mkimage
make SOC=iMX94 OEI=YES LPDDR_TYPE=<lpddr4|lpddr5> flash_a55
```

需要完整 payload 集合时，recipe 可能是：

```bash
cd /home/ives/桌面/NXP_v2/support_level/work/<case>/imx-mkimage
make SOC=iMX94 OEI=YES LPDDR_TYPE=<lpddr4|lpddr5> flash_all
```

`i.MX95` 这类 SoC 如果 `soc.mak` recipe 要求 revision，
必须显式传入，不能猜：

```bash
cd /home/ives/桌面/NXP_v2/support_level/work/<case>/imx-mkimage
make SOC=iMX95 REV=<rev> OEI=YES LPDDR_TYPE=<lpddr4|lpddr5> <recipe>
```

这些只是命令形态。
具体 recipe 和参数必须以当前 SoC 的 `soc.mak`、软件栈和 case 目标为准。

## 输出与交接

核心输出通常是：

```text
flash.bin
```

`flash.bin` 属于原始 boot image。
它可以交给 `compile_targets/flashbin` 做产物归档和 handoff，
再由 `board-exec` 决定烧写、下载态、串口和运行态验证。

`imx-mkimage` 不负责证明：

- `uuu` 传输是否成功
- 板子是否已经进入 `FB`
- U-Boot 是否已经运行
- Linux 是否已经启动
- M 核运行态是否成立

这些属于 `board-exec`、`tools/uuu` 或具体 `board_knowledge/<board>/`。

## 不该在这里判断的事

- 不在这里决定 `RTE` 是否需要 `OP-TEE`
- 不在这里决定 `ATF` 是否要 `SPD=opteed`
- 不在这里决定 `SMFW` / `ATF` 是否要同步 `meta-real-time-edge` patch
- 不在这里决定 U-Boot 应该走 `uboot-imx` 还是 `real-time-edge-uboot`
- 不在这里把 `flash_a55` / `flash_all` 当成上层 compile target
- 不在这里解释 `SDPS -> FB`、second-stage `uuu` 或 FAT 运行时文件写入

这些分别属于 `software_stacks/`、`compile_targets/flashbin/`、
`tools/uuu/` 和 `board_knowledge/`。
