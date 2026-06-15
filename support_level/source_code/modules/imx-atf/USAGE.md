# imx-atf

- 真实源码目录：`./imx-atf/`
- 当前参考分支：`lf_v2.12`
- 当前参考版本：`lf-6.18.2-1.0.0`
- 主要链路：`boot-firmware`

## 使用规则

1. 先确认这次任务是不是确实落到 `ATF`
2. 先用 `git status --short --branch` 和 `git describe --tags --always --dirty` 核对当前 ref
3. 只读检查可直接在这里做
4. 要改、要编、要出产物，复制到 `../../work/<case>/` 再做

## 已吸收：`imx943-flashbin` 输入角色

在旧 `imx943-flashbin` 里，`ATF` 是 `i.MX943 flashbin` 链的上游输入之一。

对 `i.MX943`：

- generic Linux 路径通常不要求 `SPD=opteed`
- `RTE` 路径要求 `SPD=opteed`
- 最终提供给 `imx-mkimage` 的关键产物是 `bl31.bin`

当前版本观察：

- 本地这份 `imx-atf` 是 `lf-6.18.2-1.0.0`
- 这一点和旧 skill 里 `RTE 3.4` 的期望家族一致

## 已吸收：`imx95-rte33-build-flashbin` 输入角色

对 `i.MX95 RTE 3.3 flash.bin`：

- `ATF` 不再只是共享 boot-firmware 输入
- 它还承担明确的 secure-world delta

关键点：

- 必须用 `SPD=opteed`
- 需要同步 `meta-real-time-edge` 的 `ATF` patch bucket
- 最终仍然向 `imx-mkimage` 提供 `bl31.bin`

高风险误区：

- 不要把整个 `meta-real-time-edge` patch set 全灌进 `ATF`
- 这里只该吃 `ATF` 自己的 patch bucket

## 待补全

- 不同芯片/版本的构建命令
- 相关旧 skill 的吸收结果
- 典型产物和上下游依赖
