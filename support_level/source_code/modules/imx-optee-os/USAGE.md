# imx-optee-os

- 真实源码目录：`./imx-optee-os/`
- 当前参考分支：`lf-6.12.49_2.2.0`
- 当前参考版本：`lf-6.12.49-2.2.0`
- 主要链路：`boot-firmware`

## 使用规则

1. 先确认任务是不是落到 `OP-TEE` / `tee.bin`
2. 先核对当前 ref
3. 只读检查可直接在这里做
4. 要改、要编、要出产物，复制到 `../../work/<case>/` 再做

## 已吸收：`imx943-flashbin` 输入角色

在旧 `imx943-flashbin` 里，`OP-TEE` 不是 generic Linux 默认输入，
而是 `RTE` / secure-world 路径的条件输入。

对 `i.MX943`：

- generic Linux 通常不要求 `tee.bin`
- `RTE` 路径要求 `OP-TEE`
- 产物关系是：
  `tee-raw.bin -> tee.bin`
  然后再交给 `imx-mkimage`

当前版本观察：

- 本地这份 `imx-optee-os` 目前是 `lf-6.12.49-2.2.0`
- 但旧 skill 里 `RTE 3.4` 对应的期望家族是 `lf-6.18.2-1.0.0`

这说明当前 `RTE 3.4` lane 在 `OP-TEE` 这一步也还没完成版本对齐。

## 已吸收：`imx95-rte33-build-flashbin` 输入角色

对 `i.MX95 RTE 3.3 flash.bin`：

- `OP-TEE` 不是可选补件
- 而是 `RTE secure-world delta` 的核心 owner 之一

关键点：

- 产物来源是 `tee-raw.bin`
- 对外参与打包时必须转成 `tee.bin`
- acceptance 里要验证：
  `tee.bin` 真的是从 `tee-raw.bin` copy / rename 来的

高风险误区：

- 只看到 `tee.bin` 存在，不足以证明链条是对的
- 还要确认它和 `tee-raw.bin` 的来源关系

## 待补全

- 不同芯片/版本构建方式
- 典型产物名
- 相关旧 skill 的吸收结果
