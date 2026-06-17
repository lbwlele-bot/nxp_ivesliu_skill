# m_freertos_sdk

这是 `M` 核 `FreeRTOS SDK` 编译对象。

它的默认编译入口不是普通 Git 源码项目，
而是 `MCUX SDK / FreeRTOS SDK` 发布包。

常见依赖：

- `../../m_freertos_sdk/`
- `../../toolchain/`
- 必要时再回看：
  `../../code_assets/projects/mcuxsdk-core/`
  `../../code_assets/projects/mcuxsdk-manifests/`

正常进入方式：

- 先确认目标板和目标版本的 SDK 发布包是否已经在本地
- 再把 SDK 解压到 `../../work/<case>/`
- 真正做 case 构建时，从 case 目录里的 SDK 工程开始

不要这样用：

- 不要默认从 `../../code_assets/projects/mcuxsdk-core/` 直接起编译
- 不要缺包就自己去网上拉，先找用户要或确认本地已有包
- 不要在 `../../m_freertos_sdk/` 原地修改或生成输出
