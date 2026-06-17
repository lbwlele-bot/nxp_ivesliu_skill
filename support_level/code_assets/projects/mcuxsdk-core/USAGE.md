# mcuxsdk-core

- 真实源码目录：`./mcuxsdk-core/`
- 当前参考分支：`main`
- 当前参考版本：`4cc1d817`
- 主要链路：`mcore-rtos`

这是 `MCUX SDK` 代码参考基线，不是 workspace 初始化入口，也不是默认、完全可信的 release 编译来源。
对 `M` 核 SDK 编译，首选始终是用户提供的 `m_freertos_sdk` 发布包；这里只有在缺少发布包上下文、需要查源码实现、对比组件或做备选分析时才回来看。

## 使用规则

1. 先确认任务是不是落到 `MCUX SDK` 基础代码
2. 先核对当前 ref
3. 只读检查可直接在这里做
4. 不要把这里当默认 release 编译入口；要改、要编、要集成，先确认为什么不能用 `m_freertos_sdk` 发布包，再复制到 `../../work/<case>/` 里处理

## 已吸收：`imx943-mcore-rtos` 基线应用角色

对 `i.MX943 M-core RTOS`：

- `MCUX SDK` core 是 `M7_0` / `M7_1` / `M33S` payload 的上游源码之一
- 第一轮吸收后的稳定基线应用认知是 stock `hello_world`
- 这里要先把各个核的 payload 约定说清，再交给 `flash_all`

当前稳定边界：

- `RTE 3.4`
  已验证
- `RTE 3.3`
  未支持 / 未验证

## 已吸收：Zephyr / 最新 SDK 边界

这里不要把：

- `MCUX SDK` 源码基线
- manifest / workspace 初始化
- Zephyr 主机环境准备

混成一层。

第一轮迁移后：

- `mcuxsdk-core`
  更偏向 source / SDK core
- workspace / 代码树派生
  只在明确需要源码路线时再单独判断

## 已吸收：`i.MX8DXL M4` 构建边界

对 `i.MX8DXL M4` 这类 SDK / `FreeRTOS` 构建：

- 除非明确要求 `NOR flash` 或其他 flash 链接构建方式，
  默认优先非 `flash` linker / build 方式
- 名字里带：
  `flash_debug`
  `flash_release`
  `*_flash.ld`
  默认视为 flash-linked
- 名字里带：
  `debug`
  `release`
  `*_ram.ld`
  默认视为 RAM / TCM 装载方式
- 如果当前目标是 `flash_m4` 打包产物，
  优先标准目标：
  `make SOC=iMX8DXL REV=A1 flash_m4`
- 不要默认直接调用 `mkimage_imx8`

这类规则属于 SDK / M 核构建侧，
不属于板级默认事实。

## 待补全

- 哪些板型/版本直接复用这份基线
- 与 manifest、SDK、示例工程的关系
- 相关旧 skill 的吸收结果
