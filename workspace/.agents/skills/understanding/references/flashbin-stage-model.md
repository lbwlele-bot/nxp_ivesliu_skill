# `flash.bin` stage model

## 读完后要带走什么

遇到 `flash.bin` / `uuu` 问题时，不要先把它当成“文件在哪”或“命令怎么敲”。

先把问题拆成三层：

- artifact：这个产物是什么，由谁生成
- transport：它通过什么通道被送进板子
- runtime：它把系统带到哪个运行阶段，由谁继续接管

这三层没拆开时，后面的 `compile` 和 `board-exec` 很容易互相背锅。

## 核心模型：`flash.bin` 是阶段切换载体

不要把 `flash.bin` 仅仅理解成“一个待烧录文件”。

更准确地说，`flash.bin` 往往同时承担几种角色：

- boot-firmware 组件打包产物
- ROM 下载阶段的入口载体
- 把板子带到 `U-Boot` / `Fastboot` 能力的前置基线
- 后续更多写入动作能够成立的前提

所以讨论 `flash.bin` 时，先问的不是“这个文件在哪”，而是：

- 这个 `flash.bin` 由谁消费
- 它把系统从哪个阶段带到哪个阶段
- 它建立的是“最终运行态”，还是“下一阶段的可操作态”

## `uuu -b sd <flash.bin>` 常见含义

在很多 lane 里，第一次：

```bash
uuu -b sd <flash.bin>
```

它的重要意义不只是把某个镜像写进去，
而是把板子从：

- `SDPS`

带到：

- `U-Boot`
- `Fastboot`
- 或至少是一个可继续通过 `FB` 操作的状态

所以第一次 `uuu -b sd` 的真正价值，经常是：

- 建立可继续烧录的运行时 relay

而不是“这一次就已经完成了所有最终内容”。

## 第一轮和第二轮 `uuu` 不一定语义相同

当第一次 `uuu -b sd flash.bin` 已经把板子带到了 live `Fastboot` session，
那么第二次：

```bash
uuu -b sd <another-flash-image>
```

之所以还能成功，
往往依赖的是：

- 第一次建立起来的 `U-Boot/Fastboot` 会话还活着

而不一定依赖：

- 第二个镜像本身再次提供完整 `U-Boot`

这意味着：

- 同样是 `uuu -b sd`
- 第一次和第二次的语义并不相同

第一次更像：

- `ROM/SDPS -> U-Boot/Fastboot`

第二次更像：

- `reuse existing Fastboot session for another write`

## 证据强度

一个产物至少有三种身份：

- artifact identity：它是什么打包产物
- transport identity：它通过什么通道被送进去
- runtime identity：它最终由谁接管、在哪个阶段生效

同一个 `flash.bin`：

- 在 `uuu` 看来，可能只是一个 raw boot image input
- 在 ROM 看来，是下载入口
- 在 `U-Boot/Fastboot` 语境里，可能是建立后续 relay 的基础
- 在最终运行链里，又可能只是更大运行结构里的起点

所以不能从“文件名一样”直接推出“运行角色一样”。

常见现象的证明强度：

| 现象 | 通常只能证明 | 不能自动证明 |
|------|--------------|--------------|
| `uuu` 返回成功 | transport 动作完成 | 最终 runtime 正常 |
| 串口出现 `U-Boot` | stage 切到了 `U-Boot` | Linux 或业务 payload 正常 |
| 进入 `FB` / Fastboot | relay 可用 | 写入内容已经能独立启动 |
| 镜像被写入存储 | 写入动作完成 | owner 已经接管运行 |

## 读完后怎么路由

根据当前 unresolved step 选择下游：

- 需要找现成 `flash.bin`、固件、脚本、日志、版本来源：进 `support`
- 需要生成或重打包 `flash.bin` / boot-firmware：进 `compile`
- 需要让板子从 `SDPS` 进 `U-Boot` / `FB` / 写入 / 启动验证：进 `board-exec`

## 常见误判

- 把“`uuu` 成功”当成“系统已经能运行”
- 把“同名 `flash.bin`”当成“同一个运行角色”
- 把“写进存储”当成“下一阶段 owner 已经接管”
- 忘了区分第一次 `uuu` 建立 relay 和后续 `uuu` 复用 relay
