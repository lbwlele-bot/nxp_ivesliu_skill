# flashbin

这是启动固件 / `flash.bin` 打包对象。

它关心的不是某一个单独源码仓库，
而是最终 boot image 打包链能不能成立，并产出一个可烧写、
可交给 `board-exec` 上板验证的完整 `flash.bin`。

这里的 `flashbin` 是编译对象入口，不等于 `imx-mkimage`
里某一个具体 make target。
`flash_a55`、`flash_all`、`flash_m7` 这类名字是 `soc.mak`
里的打包 recipe，必须在 SoC、板型、DDR、payload 集合、
启动介质和验证目标明确以后再选择。

常见依赖：

- `../../code_assets/projects/imx-mkimage/`
- `../../code_assets/projects/imx-atf/`
- `../../code_assets/projects/uboot-imx/` 或 `../../code_assets/projects/real-time-edge-uboot/`
- `../../code_assets/projects/imx-optee-os/`
- `../../code_assets/projects/imx-oei/`
- `../../code_assets/projects/imx-sm/`
- `../../firmware/`
- 必要时还会依赖 `M` 核 payload 输入

这些是候选依赖，不是每次都全量重建。
当前 case 真正需要哪些输入，由 SoC、软件栈、recipe、payload 集合和验证目标共同决定。

正常进入方式：

- 先由 `compile` 钉死：
  SoC / 板型 / DDR / 软件栈 / 版本 / 最终验证目标
- 再判断本次哪些输入必须重建，哪些固定输入或已有产物可以复用
- 对需要重建的输入，进入对应项目 `USAGE.md`
- 输入准备完成后，回到 `../../code_assets/projects/imx-mkimage/USAGE.md`
  做最终 `flash.bin` 打包

常见输入重建路由：

- 需要更新 SMFW：
  进入 `../../code_assets/projects/imx-sm/USAGE.md`，
  重建后回到 `imx-mkimage` 打完整 `flash.bin`
- 需要更新 ATF：
  进入 `../../code_assets/projects/imx-atf/USAGE.md`，
  重建后回到 `imx-mkimage`
- 需要更新 U-Boot：
  进入 `../../code_assets/projects/uboot-imx/USAGE.md`
  或 `../../code_assets/projects/real-time-edge-uboot/USAGE.md`，
  重建后回到 `imx-mkimage`
- 需要更新 OP-TEE / OEI：
  进入对应项目 `USAGE.md`，
  重建后回到 `imx-mkimage`
- 需要带入 `M` 核 payload：
  先进入 `../m_freertos_sdk/` 或其他对应 payload 编译对象，
  准备好 payload 后再回到这里完成 `flash.bin`

如果当前任务属于 `RTE` 链路，
先进入 `../../software_stacks/rte.md` 明确软件栈身份、LF 家族和
启动镜像输入差异，再回到这里选择完整 `flash.bin` 链路。

recipe 选择原则：

- 从目标 SoC 对应的 `soc.mak` 出发选择打包 recipe
- 选择依据是本次需要进入 boot image 的 payload 集合和板级验证目标
- 不要把 `generic Linux`、`Real-Time Edge` 等软件线名称
  直接硬绑定到 `flash_a55` 或 `flash_all`
- 如果用户说“需要重编 SMFW”，默认理解为：
  `flash.bin` 链路中的 SMFW 输入需要更新，
  不是只交付一个孤立的 SMFW 编译结果

## 已知链路事实

这些事实用于路由和防误判，不替代当前 case 的版本核对。

### `i.MX943`

- `imx-mkimage` 里通常使用 `SOC=iMX94`
- 常见链路默认需要 `OEI=YES`
- `OEI` 侧最终给 `imx-mkimage` 的关键输入是 `oei-m33-ddr.bin`
- `flash_a55` / `flash_all` 都是 `soc.mak` recipe，不是上层 compile target
- `RTE 3.3`、`RTE 3.4` 的差异先走 `../../software_stacks/rte.md`
- `RTE` 路径通常需要 `OP-TEE` 输入，最终给 `imx-mkimage` 的是 `tee.bin`
- `flash_a55` 和 `flash_all` 产物都属于原始 boot image，不是 FAT 运行时文件

### `i.MX95 RTE 3.3`

这条链路的关键点是构建身份和输入集合，不能只看一个 `make` 命令。

已验证过的打包形态是：

```bash
make SOC=iMX95 REV=B0 OEI=YES LPDDR_TYPE=lpddr5 flash_all
```

注意：

- `REV` 会影响输出，不能猜
- 已验证链路是 `B0`
- `flash_all` 不能被静默替换成 `flash_a55`
- `OEI` 不是只看 `oei-m33-ddr.bin` 是否存在，还要确认它对应目标 revision
- 对 `i.MX95 B0` 链路，优先核对 `build/mx95lp5/ddr/build_info.h`
  是否体现 `MIMX95(B0)`
- `ATF` / `SMFW` 的 RTE patch bucket 归 `software_stacks/rte.md` 管
- `SMFW` 的 RTE 配置要明确落到当前目标；已知候选是 `configs/other/mx95rte.cfg`
- M 核 payload 是否带入，由当前 RTE 链路和 case 目标决定

不要这样用：

- 不要把 `firmware/` 当源码项目
- 不要只看某一个仓库就认定整条 `flash.bin` 链可编
- 不要把 `flash_a55` / `flash_all` 当成上层 compile target
- 不要直接复用旧 `work/` 产物而跳过链路核对
