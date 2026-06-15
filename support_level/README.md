# support_level

这里放 `NXP_v2` 的重资源。

当前结构优先服务于 `NXP_v2` 的长期支撑层资产，不再直接照搬旧根目录名。

建议目录：

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

约定：

- `source_code/` 放共享源码基线
- `m_freertos_sdk/` 放 `MCUX SDK / FreeRTOS SDK` 发布压缩包资产，不当成普通 Git 源码树
- `firmware/` 放 DDR firmware、AHAB 等固定二进制输入
- `board_knowledge/` 放板级操作时已经被实测证明、后续可复用的知识
- `tools/` 放主机侧工具，长期形态是 `工具目录 + USAGE.md + 程序本体`
- `work/` 放 case 日志、产物和临时修改
- `toolchain/`、`firmware/`、`m_freertos_sdk/` 应逐步补 `README.md` 作为按需读取入口

当前已完成的长期资产迁移：

- `tools/`
- `source_code/`
- `m_freertos_sdk/`
- `toolchain/`
- `Image/`
- `firmware/`
- `SoC_material/i.MX93/RM`
- `SoC_material/i.MX943/RM`
- `SoC_material/i.MX95/RM`

当前已补进的新 RM：

- `SoC_material/i.MX91/RM/IMX91RM.pdf`
- `SoC_material/i.MX8M/RM/IMX8MDQLQRM.pdf`
- `SoC_material/i.MX8MM/RM/PREVIEW_IMX8MMRM.pdf`
- `SoC_material/i.MX8MN/RM/IMX8MNRM.pdf`
- `SoC_material/i.MX8MP/RM/PREVIEW_IMX8MPRM.pdf`
- `SoC_material/i.MX8ULP/RM/IMX8ULPRM.pdf`

当前仍待补齐：

- `linux_document/` 下的正式 Linux BSP docs 包
- `SoC_material/` 里 RM 之外的硬件资料、原理图、板型资料
- 当前还没直接补进来的 RM：
  `i.MX8DXL`
  `i.MX8QXP`
  `i.MX8QM`
