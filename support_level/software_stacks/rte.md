# Real-Time Edge software stack

这里是 `Real-Time Edge` 软件线的 owner。

`RTE 3.3`、`RTE 3.4` 这类名字不是单个源码仓库版本，
也不是 `imx-mkimage` 的某个 make target。
它们是跨项目的软件栈身份，会同时影响：

- 底层 LF / BSP release 家族
- 需要切到哪些源码 ref
- `flash.bin` 里包含哪些输入
- 是否需要 `OP-TEE`
- `ATF` 是否需要 `SPD=opteed`
- `SMFW` / `ATF` patch 是否来自 `meta-real-time-edge`
- `U-Boot` 使用通用线还是 Real-Time Edge 线
- Linux / Yocto 是否进入 Real-Time Edge 线
- 是否需要 M 核 payload 进入 boot image
- 需要哪些不可切版本的 release 包

这些是 RTE 规则，不是某颗芯片自己的规则，也不是 `imx-atf`
或 `imx-sm` 这类单个项目自己的全局规则。
单项目 `USAGE.md` 只记录被 RTE 选中以后自己的局部动作。

## 当前已知版本关系

这些关系用于路由和核对，不替代具体 case 的 release note、脚本或用户指定版本。

| 软件线 | 已知 LF / BSP 家族 | 当前说明 |
|--------|--------------------|----------|
| `RTE 3.3` | `lf-6.12.34` 家族 | 需要按具体 case 核对各源码 ref 和 release 包 |
| `RTE 3.4` | `lf-6.18.x` 家族 | 需要按具体 case 核对各源码 ref 和 release 包 |

如果用户只说 `RTE`，没有说版本，不要替用户选 `3.3` 或 `3.4`。

## RTE 固有约束

只要当前任务明确属于 RTE 链路，默认先按下面的跨项目约束建模，
再进入具体源码项目：

| 范围 | RTE 约束 | 具体项目文档只负责 |
|------|----------|--------------------|
| `ATF` | 需要 OP-TEE 安全世界 dispatcher，通常构建 `SPD=opteed`；需要按模块同步 `meta-real-time-edge` 的 ATF patch bucket | `imx-atf/USAGE.md` 只写 `bl31.bin` 怎么编、patch 怎么只落到 ATF |
| `OP-TEE` | RTE 链路通常需要 `tee-raw.bin -> tee.bin`，并把 `tee.bin` 作为 boot image 输入之一 | `imx-optee-os/USAGE.md` 只写 OP-TEE 自己怎么出产物 |
| `SMFW` | 需要按模块同步 `meta-real-time-edge` 的 SMFW patch bucket；目标配置可能落到 RTE 专用配置，例如 `configs/other/mx95rte.cfg` | `imx-sm/USAGE.md` 只写 SMFW 自己怎么补丁、编译、交付输入 |
| `U-Boot` | 不能默认走通用 `uboot-imx`，必须判断是否应使用 `real-time-edge-uboot` | U-Boot 项目文档只写选中该来源以后怎么核对 ref 和构建 |
| Linux / Yocto | 不能按 generic Linux 线直接推断源码、meta layer 或配置 | Linux / meta layer 文档只写被选中以后自己的构建入口 |
| `flash.bin` | 输入集合由 RTE 软件线决定，然后再选择 `soc.mak` recipe | `compile_targets/flashbin/` 只负责最终打包链路 |

高风险误区：

- 不要把 `RTE` 只理解成版本号对应关系
- 不要把 `RTE` 只写进 `imx-atf`、`imx-sm` 或 `U-Boot` 单个项目
- 不要把整套 `meta-real-time-edge` patch 全灌进一个项目
- 不要把 `RTE` 名称直接硬绑定到 `flash_a55` 或 `flash_all`
- 不要在 `imx-mkimage` 项目页里反推整条 RTE 软件线

## 对 `flash.bin` 的影响

进入 `compile_targets/flashbin/` 前，先确认当前 RTE 软件线和版本。

RTE 软件线可能改变：

- `imx-atf`
  是否使用 `SPD=opteed`，以及是否同步 RTE 的 ATF patch bucket
- `imx-optee-os`
  是否必须产出 `tee-raw.bin` 并转换为 `tee.bin`
- `imx-sm`
  是否使用 RTE 专用配置，例如 `configs/other/mx95rte.cfg`，以及是否同步 RTE 的 SMFW patch bucket
- `uboot-imx` / `real-time-edge-uboot`
  当前链路应使用哪条 U-Boot 来源
- `m_freertos_sdk` 或其他 M 核 payload
  是否作为 boot image 输入参与最终打包
- `imx-mkimage`
  最终选择哪个 SoC `soc.mak` recipe

`flash_a55`、`flash_all` 等仍然是 `soc.mak` recipe。
它们不能只从 `RTE 3.3` 或 `RTE 3.4` 名称直接推出。

## 对源码项目的影响

`code_assets/projects/` 下的 Git 源码项目是可切换共享工作副本。

进入具体源码项目前：

1. 先根据当前软件线和 case 要求确定目标 ref
2. 在源码项目里核对当前 ref
3. 如果不匹配，可以做可逆 checkout / tag / branch 切换
4. 如果要改代码、打 patch、编译或生成输出，复制到 `../work/<case>/`

项目 `USAGE.md` 只负责项目自己的构建方法和输入输出契约，
不负责承载完整 RTE 软件线判断。

## 对 release 包的影响

`release_packages/` 下的包不能通过 Git checkout 切版本。

如果 RTE 软件线要求某个特定 `m_freertos_sdk`、`SCFW` 或其他厂商 release 包版本：

- 本地已有对应版本：使用本地包
- 本地没有对应版本：让用户提供或下载官方包
- 不要拿相近版本硬代替
