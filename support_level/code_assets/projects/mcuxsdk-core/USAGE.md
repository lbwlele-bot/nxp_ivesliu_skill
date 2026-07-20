# mcuxsdk-core

- 真实源码目录：`./mcuxsdk-core/`
- 最近观察分支（使用前重新核对）：`main`
- 最近观察版本（使用前重新核对）：`4cc1d817`
- 主要链路：`MCUX SDK` core 源码参考

## 角色

`mcuxsdk-core` 是 MCUXpresso SDK 的 core / driver / component 源码子仓。
它是完整 MCUX SDK 交付的一部分，不是完整 SDK workspace，
也不是默认的 `M` 核 release 编译入口。

源码 README 明确说明：完整 MCUX SDK 交付应从 `mcuxsdk-manifests`
这类上层 manifest / parent repository 进入。

本页只负责 `mcuxsdk-core` 这个子仓自己的源码核对和参考边界。
真正要编 `M` 核 FreeRTOS SDK 产物时，先走：

- `../../../compile_targets/m_freertos_sdk/README.md`
- `../../../release_packages/m_freertos_sdk/README.md`
- 必要时再回看 `../mcuxsdk-manifests/USAGE.md`

## 使用前提

进入本页前，先确认当前任务确实需要查 `MCUX SDK core` 源码，例如：

- 查 driver / middleware / FreeRTOS component 实现
- 对比 SDK core 组件版本
- 追踪 CMake / Kconfig / linker target 定义
- 为 release SDK 工程定位参考源码

如果当前目标是“编一个 M 核 demo / FreeRTOS payload”，
不要直接从这里开始。
先确认目标 SDK release 包是否在 `release_packages/m_freertos_sdk/`，
再由 `compile_targets/m_freertos_sdk/` 接手。

## 共享源码规则

1. 先用 `git status --short --branch` 和 `git describe --tags --always --dirty` 核对当前 ref
2. 只读检查可直接在共享源码目录做
3. 可以按任务需要做可逆 checkout / tag / branch 切换
4. 要改代码、拼完整 workspace、生成工程或构建输出，复制到 `../../../work/<case>/` 再做
5. 不要把这个共享子仓污染成某个 case 的 SDK workspace

## 本地线索

当前源码根下可见的关键入口包括：

```text
CMakeLists.txt
drivers/
middleware/
rtos/
devices/
arch/
scripts/west_commands.yml
```

其中：

- `drivers/`、`middleware/`、`rtos/` 是源码参考重点
- `CMakeLists.txt` 会加载 drivers、components、FreeRTOS 等子目录
- `scripts/west_commands.yml` 说明该仓参与 west / MCUX SDK workspace 工作流
- `examples/` 在 CMake 中是可选入口，不代表这个子仓本身就是完整 examples 交付

## 和其他层的关系

### 和 `release_packages/m_freertos_sdk`

`release_packages/m_freertos_sdk/` 是厂商 SDK 发布包资产。
如果目标是按板型和版本编 SDK demo，默认优先使用 release 包。

`mcuxsdk-core` 只能作为源码参考或备选分析入口，
不能替代目标板对应的官方 SDK release 包。

### 和 `compile_targets/m_freertos_sdk`

`compile_targets/m_freertos_sdk/` 是 M 核 SDK 编译对象 owner。
它负责判断这次成功标准是独立 M 核产物，
还是作为 `flash.bin` 的 payload 输入。

`mcuxsdk-core` 不负责决定 payload 是否进入 `flash.bin`。

### 和 `mcuxsdk-manifests`

`mcuxsdk-manifests` 更接近完整 SDK workspace 初始化入口。
如果任务需要完整多仓 workspace、west manifest 或 GitHub 版 MCUX SDK 组合，
先转到 `../mcuxsdk-manifests/USAGE.md`。

## 不该在这里判断的事

- 不在这里决定目标 SDK release 版本是否满足当前板型
- 不在这里缺包后用源码子仓硬替 release 包
- 不在这里决定 `flash_m4`、`flash_all` 或其他 boot image recipe
- 不在这里解释 U-Boot / Linux remoteproc / board-exec 如何加载 M 核 payload
- 不在这里把 Zephyr workspace、MCUX manifest 和 release SDK 混成一层

这些分别属于 `release_packages/`、`compile_targets/m_freertos_sdk/`、
`compile_targets/flashbin/`、`board-exec` 和 `code_assets/workspaces/`。
