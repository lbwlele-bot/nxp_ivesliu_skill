# support_level

这里放 `NXP_v2` 的重资源。

当前结构优先服务于 `NXP_v2` 的长期支撑层资产。

当前目录：

- `Image/`
- `SoC_material/`
- `board_knowledge/`
- `code_assets/`
- `compile_targets/`
- `tools/`
- `linux_document/`
- `m_freertos_sdk/`
- `toolchain/`
- `firmware/`
- `to_absorb/`
- `work/`

说明：

- `code_assets/` 放长期保留的代码资产，下面再分 `projects/` 和 `workspaces/`
- `compile_targets/` 放编译对象入口，由 `compile` owner
- `m_freertos_sdk/` 放 `MCUX SDK / FreeRTOS SDK` 发布压缩包资产，不当成普通 Git 源码树
- `firmware/` 放 DDR firmware、AHAB 等固定二进制输入
- `board_knowledge/` 放板级操作时已经被实测证明、后续可复用的知识
- `tools/` 放主机侧工具，长期形态是 `工具目录 + USAGE.md + 程序本体`
- `to_absorb/` 放待归纳的高价值信息，保留来源 case，后续再决定吸收到哪一层
- `work/` 放 case 全过程记录、日志、产物和临时修改
- `toolchain/`、`firmware/`、`m_freertos_sdk/` 可在各自目录下补最小 README 作为入口

这里的文档主要负责：

- 这层里有什么
- 它们放在什么位置
- 该进哪一层 README 或 `USAGE.md`

文档分工：

- 每一层目录下的 `README.md` 负责说明这一层里有什么、怎么分布、该往哪一层继续走
- 每个源码项目或具体工具旁边的 `USAGE.md` 负责操作手册

如果已经明确要看某个源码项目，再去项目目录旁边读取 `USAGE.md`。

当前已收成长期源码项目的资产，简要包括：

- `imx-atf`
- `imx-mkimage`
- `imx-oei`
- `imx-optee-os`
- `imx-sm`
- `linux-imx`
- `mcuxsdk-core`
- `imx-scfw-porting-kit`
- `meta-real-time-edge`
- `real-time-edge-linux`
- `real-time-edge-uboot`
- `uboot-imx`
- `android`
