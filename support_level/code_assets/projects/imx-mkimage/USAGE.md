# imx-mkimage

- 真实源码目录：`./imx-mkimage/`
- 最近观察分支（使用前重新核对）：`lf-6.12.49_2.2.0`
- 最近观察版本（使用前重新核对）：`lf-6.12.49-2.2.0`
- 主要链路：`flash.bin` 打包工具
- 对外编译清单：`COMPILE_CHECKLIST.yaml`
- 内部编译 profile：`COMPILE_PROFILE.yaml`
- 项目硬门禁：`COMPILE_POLICY.yaml`

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

## 项目级受控打包入口

imx-mkimage 现在作为独立 consumer/assembler 管理：它只约束自己的源码、
参数、隔离执行、输入槽位和最终 `flash.bin`，不替 OEI、ATF、U-Boot 等
producer 定义编译方法。

`COMPILE_CHECKLIST.yaml` 复制到 `records/compile/imx-mkimage/compile.yaml`，填写
revision、SOC、recipe、producer/fixed input 选择和本轮 intent 后，
只执行 `compile-tool prepare <compile.yaml>` 和 `compile-tool run <compile.yaml>`。
原始 make 命令由 profile 生成，AI 不填写。

`COMPILE_PROFILE.yaml` 定义 `oei`、`atf`、`uboot_bin`、`uboot_spl`、`optee`、
`smfw`、`firmware` 和 `m_payload` artifact 输入槽位；M payload 允许多个，
但只能引用 M SDK 公共清单导出的 `nxp.mcore.bin`。公共清单没有裸 M 文件入口。
`oei_enabled=YES` 时必须选择 `oei` artifact，并和 consumer 的 silicon
revision 一致。

`soc.mak` 是 recipe 依赖和 M 镜像文件名的事实源。compile-tool 从清单选择的
源码 ref 读取 `<SOC>/soc.mak`，自动提取当前 target 实际需要的 M payload，
不把 `m7/m33s/m70/m71` 列表复制到额外 YAML，也不让 AI 阅读 Makefile 全文。

`compile_targets/flashbin/RECIPE_CONTRACTS.yaml` 只补充 `soc.mak` 没有表达的
producer 类型、身份关系和当前非 M 输入合同。当前完整 producer/fixed-input
组合仍只覆盖 `iMX94/iMX95` 的
`flash_a55` 和 `flash_all`；未登记 recipe 不会静默执行。

`COMPILE_POLICY.yaml` 独立要求 make 命令显式传 `REV=<value>`，并强制所有
step 在项目自己的 `isolated_git` 副本中执行。

OEI、ATF、两条 U-Boot、OP-TEE 和 SMFW 已有独立单清单。
已知 i.MX95 B0 和 i.MX943 A0 的 AHAB/DDR firmware 由
`compile_targets/flashbin/FIXED_ASSETS.yaml` 绑定 SHA-256。M payload 已由独立
`m_freertos_sdk` producer 接通；SCFW 尚未完成项目自治迁移，完整旧链路仍可继续使用
`records/compile-manifest.yaml` 深度模式。

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
- M 核 BIN artifact，只有所选 recipe / 软件栈 / case 需要时才带入
- DDR / ELE / AHAB 等固定 firmware blob

输入集合由上层 `flashbin` 编排和软件栈决定。
不要只因为某个文件在目录里存在，就默认它应该进入本次 `flash.bin`。

项目级路径中，输入通过同 case producer manifest 的具名 artifact 引用，工具
验证 producer 成功状态、hash、type 和身份参数。它不会自动跨 manifest 执行
producer；应先完成 producer，再 assess imx-mkimage。

当前 `soc.mak + producer identity` 联合约束：

- `iMX95/flash_all` 从 `soc.mak` 得到 `m7_image.bin`，对应 producer 必须是
  `soc=imx95, core_role=m7`，固定暂存为
  `iMX95/m7_image.bin`；
- `iMX94/flash_all` 从 `soc.mak` 得到 `m33s/m70/m71` 三个文件，对应 producer
  必须是 `soc=imx943, core_role=m33s/m70/m71`，固定暂存为
  `iMX94/m33s_image.bin`、`m70_image.bin`、`m71_image.bin`；
- producer 文件缺失、哈希变化、SoC/core role/type 错误或传入 ELF 都会阻断。

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
