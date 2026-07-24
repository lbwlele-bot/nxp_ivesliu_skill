# `flash.bin` artifact, transport and runtime model

## 核心结论

`flash.bin` 是 boot image 产物，不是一个独立完成阶段切换的主动 owner。

一次下载、写入或启动的真实语义由下面几项共同决定：

- `flash.bin` 内部包含什么组件
- 当前设备处在哪个 ROM / USB / boot 阶段
- 使用的传输工具和 recipe 做什么
- 目标是临时下载执行还是写入持久介质
- image 中的下一阶段软件启动后提供什么能力

因此不能只看到文件名或一条 UUU 命令，
就直接判断板子一定会进入 U-Boot、Fastboot 或最终系统。

## 四个独立问题

### 1. Artifact identity

先确认产物自身：

- 由哪个源码版本和 recipe 生成
- 面向哪个 SoC、silicon revision、板型和 DDR
- 包含哪些 boot firmware、U-Boot、M 核 payload 或其它组件
- 是已验证基线、case-local 修改，还是来源不明的旧产物

artifact identity 只说明“这个文件是什么”，
不说明当前设备会如何消费它。

### 2. Transport action

再确认本次传输动作：

- 工具当前匹配了哪个 USB 协议阶段
- recipe 会下载执行、写入存储，还是复用已有 Fastboot 会话
- 目标介质和写入位置是什么
- 当前动作是否依赖已经运行的 U-Boot/Fastboot

transport 成功只证明对应传输或写入动作成立，
不自动证明 image 能独立启动。

### 3. Current device stage

同一条 recipe 在不同设备阶段可能有不同语义。

常见阶段包括：

- ROM download / `SDPS`
- 二级下载阶段 / `SDPV`
- U-Boot Fastboot / `FB`
- U-Boot shell
- 已进入操作系统

第一次从 ROM 下载态开始的动作，
和已经存在 Fastboot 会话时再次执行写入，
不是同一个观察点，也不能互相替代证明。

### 4. Runtime result

最后确认运行结果：

- 哪个组件真正开始执行
- 是否只是建立了下一阶段可操作能力
- 是否从目标介质完成冷启动
- U-Boot、Linux、M 核或业务 payload 是否按预期接管

runtime 结论必须来自运行态证据，
不能只从 transport 返回值推出。

## 常见两阶段链路

某些 i.MX 上板流程会表现为：

```text
ROM download
  -> 下载并执行一个包含 U-Boot/Fastboot 能力的 boot image
  -> 建立当前 Fastboot 会话
  -> 复用该会话执行后续写入
  -> 从目标介质重新启动并验证运行态
```

这是特定 image 内容、设备阶段和传输 recipe 共同形成的链路，
不是所有 `flash.bin` 或所有 UUU 调用的固有语义。

## 证据边界

| 现象 | 能直接证明 | 不能自动证明 |
|------|------------|--------------|
| `flash.bin` 文件存在 | 有一个候选 artifact | 版本、内容和目标板匹配 |
| 构建成功 | 构建流程产生了文件 | 板上可以运行 |
| UUU 返回成功 | 对应传输或写入动作完成 | 最终 runtime 正常 |
| 设备进入 Fastboot | 当前 Fastboot relay 可用 | 写入内容可以独立冷启动 |
| 串口出现 U-Boot | U-Boot 已执行到可观察阶段 | Linux 或业务 payload 正常 |
| 从目标介质冷启动成功 | boot image 的主要启动链成立 | 所有异构核和业务功能正常 |

## 路由

根据当前 unresolved step：

- 查 artifact 来源、版本、现成基线和日志：`support`
- 生成或重打包 boot image：`compile`
- 探测当前 USB 阶段、执行传输、写入和启动验证：`board-exec`
- artifact、transport、device stage 和 runtime 仍被混淆：
  继续由 `understanding` 拆分问题

## 常见误判

- 把 `flash.bin` 当成运行时 owner
- 只根据文件名判断内部组件
- 把 UUU 成功当成最终启动成功
- 把现有 Fastboot 会话中的写入当成从 ROM 阶段重新验证
- 忽略目标板、revision、DDR 和 image recipe 的身份差异
