# `M` core owner model

## 读完后要带走什么

遇到 `M` 核 / 异构核问题时，第一问不是“镜像有没有烧进去”，也不是“命令怎么敲”。

第一问是：

- 这次谁拥有 `M` 核启动动作

owner 没分清之前，不要直接决定是改 boot-firmware、敲 `bootaux`，还是查 Linux `remoteproc`。

## owner 分层

| owner layer | 典型信号 | 主要问题归属 |
|-------------|----------|--------------|
| `flash.bin` / boot-firmware | M 核 payload 被早期 boot flow 打包或带起 | boot-firmware 打包、启动链、早期资源分配 |
| `U-Boot` | `bootaux`、U-Boot 命令、U-Boot 阶段加载 payload | U-Boot 环境、加载地址、payload 格式 |
| Linux | `remoteproc`、`rproc`、firmware name、resource table | Linux driver、firmware 搜索路径、资源表、内存 carveout |

同一个 M 核 binary，在不同 owner layer 下不是同一个问题。

## owner 会改变什么

owner layer 会直接改变：

- 产物应该怎么打包
- binary 放在哪里
- 是否需要 resource table
- 哪个阶段负责加载
- 验证点应该看串口、U-Boot 变量，还是 Linux sysfs / dmesg
- 失败时优先查 boot-firmware、U-Boot，还是 Linux runtime

所以“M 核起不来”不是单一问题，而是 owner 还没分类。

## 证据强度

| 现象 | 通常只能证明 | 不能自动证明 |
|------|--------------|--------------|
| binary 存在 | artifact 准备好了 | owner 会加载它 |
| `bootaux` 执行过 | U-Boot 发起过启动动作 | M 核运行逻辑正确 |
| Linux 下看到 `remoteproc` 节点 | Linux 有管理入口 | firmware 已加载并正常跑 |
| M 核串口有输出 | 某阶段已成功带起 M 核 | owner layer 一定是 Linux 或 U-Boot |

## 读完后怎么路由

根据 owner 分类选择下游：

- 需要找 M 核 binary、board 文档、已有日志、固件路径：进 `support`
- 需要生成 M 核 payload、重打包 boot-firmware、准备 resource table：进 `compile`
- 需要执行 `bootaux`、观察串口、操作 Linux `remoteproc`、确认当前核是否允许触碰：进 `board-exec`

## 必须先问清的问题

1. 这次目标是哪颗 M 核或哪类辅助核
2. 当前 case 里哪些核是保留核，哪些核允许触碰
3. 期望 owner 是 boot-firmware、U-Boot，还是 Linux
4. 当前证据只证明 artifact、transport、还是 runtime
