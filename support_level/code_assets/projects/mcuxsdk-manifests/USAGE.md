# mcuxsdk-manifests

- 真实源码目录：`./mcuxsdk-manifests/`
- 最近观察 ref：`main` / `v26.03.00`，使用前重新核对
- 主要链路：`mcore-rtos`

这是 `MCUX SDK` 的 manifest / west workspace 入口，低频使用。

只有在需要看 MCUX SDK workspace 由哪些 repo、board manifest、middleware、
RTOS 组成时，才进这里。

## 什么时候用

- 查某个 MCUX SDK manifest 版本会拉哪些 repo
- 查某块板在 manifest 里对应哪些 repo / example 类别
- 初始化或比较一个 case-local MCUX SDK west workspace
- 判断 `mcuxsdk-core` 在完整 MCUX SDK workspace 里的位置

## 最小入口

- `mcuxsdk-manifests/west.yml`：manifest 总入口
- `mcuxsdk-manifests/submanifests/base.yml`：基础 repo 组成，可看到
  `core -> mcuxsdk-core`
- `mcuxsdk-manifests/submanifests/devices/i.MX.yml`：i.MX device repo 入口
- `mcuxsdk-manifests/boards/*.yml`：板卡级 repo / example 清单
- `mcuxsdk-manifests/scripts/west_commands.yml`：west 扩展命令入口

`boards/*.yml` 只能说明 workspace 组成，不能证明本机已有可编译的 release SDK 包。

## 边界

- 要编本地已有 M 核 SDK demo，先去
  `../../../compile_targets/m_freertos_sdk/README.md`
  和 `../../../release_packages/m_freertos_sdk/`
- 要查 SDK core 源码，去 `../mcuxsdk-core/USAGE.md`
- 需要 `west init`、`west update`、改 manifest 或生成派生 workspace 时，
  在当前 case 的 `../../../work/<case>/` 下做，不污染共享基线
- 缺目标版本 manifest 时，让用户提供或下载；不要猜路径、猜版本

一句话：这里只回答“MCUX SDK workspace 由什么组成”，不回答“当前 M 核
release 工程怎么编、产物怎么进 `flash.bin`”。
