# board_knowledge

这里放 **板级操作的支撑层知识**。
它不是抽象经验库，也不是 SoC 文档库，而是为了让后续做板子操作时，能快速拿到那些已经确定、能复用、能直接指导动作的知识。

它和 `SoC_material/`、`tools/` 不一样：

- `SoC_material/`
  放芯片或板子的静态资料，如 RM、原理图、硬件文档
- `tools/`
  放工具本身
- `board_knowledge/`
  放 **实际测过以后，确定可复用的板级操作知识**

换句话说，这一层回答的是：

- 这块板平时怎么识别
- 这块板常用入口怎么进
- 这块板哪些操作前提已经被证实
- 这块板有哪些确定能复用的注意事项

## 这里该放什么

只放已经被现场验证过、下次很可能还会直接复用的内容，例如：

- 某块板默认主 console 是哪个串口
- 某块板进入下载态时，`uuu -lsusb` 会看到什么
- 某块板常见的 USB/串口枚举顺序
- 某块板已经验证过的启动模式切换顺序
- 某块板实测有效的烧写前提和恢复前提
- 某块板对 `serial download` / `U-Boot` / `Linux-ready` 的默认判定入口
- 某块板从上板写入 / reset 之后，下一手该进入哪类判断才不容易乱

如果有些知识一半来自资料、一半必须靠现场测才能定，
那资料本体继续放 `SoC_material/`，
最终能沉淀到这里的，只能是“已经测完、已经定下来的那一半”。

## 这里不该放什么

- 没测过的猜测
- 只是从 RM 或文档里读到、但没在现场验证过的说法
- 一次性的 case 噪声
- 纯命令清单
- 纯工具安装说明

## 沉淀规则

- 先测，再写
- 没有现场证据，不进这里
- 资料可以辅助理解，但不能替代实测结论
- 结论必须能说清：
  板型
  版本
  现象
  结论
- 一块板一个目录，逐步补齐

## 建议结构

```text
board_knowledge/
  <board-id>/
    README.md
```

例如：

```text
board_knowledge/
  imx943evk19a0/
    README.md
```

每块板的 `README.md` 里优先放：

- 默认串口认知
- 默认 USB 下载态认知
- 已验证的基础进入方式
- 已验证的操作前提
- 已验证的高频注意事项
- 已验证的启动阶段判断边界
- 已验证的上板写入 -> 启动 -> 登录交接边界

如果某块板有稳定的串口映射，
同时放一个机器可读文件：

```text
board_knowledge/
  <board-id>/
    serial.yaml
```

`serial.yaml` 只放给 `tools/serial-console` 消费的串口事实：

- profile 完整程度：`verified` / `partial` / `unknown`
- 已验证适配器接口数量
- USB interface 顺序，例如 `if00` / `if01`
- 默认 baudrate
- role 到 interface / `/dev/serial/by-id/*` / `ttyUSB*` 的映射
- 哪些 role 默认抓取、哪些是必要端口
- 映射的 case 和 session 证据
- 串口侧已验证风险

串口工具的命令语义不写在这里；
工具用法继续看 `../tools/serial-console/USAGE.md`，
字段定义看 `../tools/serial-console/PROFILE_SCHEMA.md`。

未完整确认的板必须标记为 `partial`。
已知 role 可以直接复用，但不能因为当前插上了两个或四个串口，就给剩余接口
补猜 Linux、M 核或系统控制固件角色。
