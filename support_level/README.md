# support_level

这里放 `NXP_v2` 的重资源。

当前结构优先服务于 `NXP_v2` 的长期支撑层资产。

当前目录：

- `Image/`
- `SoC_material/`
- `board_knowledge/`
- `tools/`
- `linux_document/`
- `source_code/`
- `m_freertos_sdk/`
- `toolchain/`
- `firmware/`
- `work/`

说明：

- `source_code/` 放共享源码基线
- `m_freertos_sdk/` 放 `MCUX SDK / FreeRTOS SDK` 发布压缩包资产，不当成普通 Git 源码树
- `firmware/` 放 DDR firmware、AHAB 等固定二进制输入
- `board_knowledge/` 放板级操作时已经被实测证明、后续可复用的知识
- `tools/` 放主机侧工具，长期形态是 `工具目录 + USAGE.md + 程序本体`
- `work/` 放 case 日志、产物和临时修改
- `toolchain/`、`firmware/`、`m_freertos_sdk/` 可在各自目录下补最小 README 作为入口

这里的文档主要负责：

- 这层里有什么
- 它们放在什么位置
- 该进哪一层 README 或 `USAGE.md`

文档分工：

- 每一层目录下的 `README.md` 负责说明这一层里有什么、怎么分布、该往哪一层继续走
- 每个源码模块或具体工具旁边的 `USAGE.md` 负责操作手册

如果已经明确要动某个源码模块，再去模块目录旁边读取 `USAGE.md`。

当前已收成长期模块入口的源码，简要包括：

- `imx-atf`
- `imx-mkimage`
- `imx-oei`
- `imx-optee-os`
- `imx-sm`
- `linux-imx`
- `mcuxsdk-core`
- `mcuxsdk-manifests`
- `meta-real-time-edge`
- `real-time-edge-linux`
- `real-time-edge-uboot`
- `uboot-imx`
