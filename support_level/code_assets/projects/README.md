# projects

这里放可按任务需要切换 ref 的单项目 Git 源码资产和 manifest 资产。

这层只回答三件事：

- 本地有哪些 Git 源码项目或 manifest
- 它们真实放在哪里
- 它们能不能当成标准源码基线或 manifest 基线来读

使用规则：

- 默认只读
- 可以浏览、比对、切 branch / tag / commit
- 不在这里直接做 case 构建
- 一旦问题变成“我要编什么”，回 `compile` 判断编译对象
- 这里的源码树是可切换共享工作副本，不把当前 checkout 当成固定任务版本
- 进入具体 case 前，按软件栈 / release / case 要求确定目标 ref，再核对并按需切换
- 如果要改代码、打 patch、编译或生成输出，复制到 `../../../work/<case>/` 再做

当前项目资产包括：

- `imx-atf`
  ARM Trusted Firmware，启动链上游输入之一。
- `imx-mkimage`
  `flash.bin` / 启动镜像拼装入口。
- `imx-oei`
  `i.MX943` 等链路里的 `OEI` 固定输入。
- `imx-optee-os`
  `RTE` / 安全世界路径里的 `OP-TEE` 来源。
- `imx-sm`
  `SMFW` 来源，属于启动固件输入之一。
- `linux-imx`
  通用 Linux BSP 内核源码线。
- `mcuxsdk-core`
  `MCUX SDK` 代码参考基线，不是默认 release 编译入口。
- `mcuxsdk-manifests`
  `MCUX SDK` manifest / workspace 初始化入口，不是默认 release 编译入口。
- `meta-real-time-edge`
  `RTE` Yocto meta layer，用来看 patch 来源和版本映射。
- `real-time-edge-linux`
  `RTE` Linux 内核源码线。
- `real-time-edge-uboot`
  `RTE` 路径下的 `U-Boot` 候选源码线。
- `uboot-imx`
  通用 `U-Boot` 源码线。
- `android`
  Android 源码发布包资产。

不可通过 Git 切版本的厂商 release 包，例如 `m_freertos_sdk` 和 `SCFW`，
放在 `../../release_packages/`。
