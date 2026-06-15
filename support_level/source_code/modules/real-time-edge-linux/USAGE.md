# real-time-edge-linux

- 真实源码目录：`./real-time-edge-linux/`
- 当前参考分支：`detached-head`
- 当前参考版本：`Real-Time-Edge-v3.3-202512`
- 主要链路：`linux-bsp`

## 使用规则

1. 先确认任务是不是落到 `Real-Time Edge Linux` 内核线
2. 先核对当前 ref
3. 只读检查可直接在这里做
4. 要改、要编、要出 `Image/dtb/modules`，复制到 `../../work/<case>/` 再做

## 已吸收：`real-time-edge-linux-build` source/bootstrap 角色

这条 helper 的稳定 owner 不是 runtime，也不是 patch owner，
而是：

- reusable source baseline
- release tag mapping
- A-core toolchain mapping
- minimum proof that the tree is build-ready

关键边界：

- shared baseline 放在可复用根
- 真正 build / patch 在 case-local copy 里做
- tag、toolchain family、source line 要显式映射

## 已吸收：`imx943-linux` 的 `RTE` 分支认知

对 `i.MX943`：

- `RTE 3.3`
  有自己的 source / tag 语义
- `RTE 3.4`
  也有自己的 source / tag 语义

所以这里第一轮吸收的是：

- `RTE Linux` 的 source/bootstrap owner
- 版本到 toolchain family 的映射边界

而不是“在这里直接承诺所有 case-ready recipe”

## 待补全

- 不同 RTE 版本的构建方式
- 与 `meta-real-time-edge` 的关系
- 相关旧 skill 的吸收结果
