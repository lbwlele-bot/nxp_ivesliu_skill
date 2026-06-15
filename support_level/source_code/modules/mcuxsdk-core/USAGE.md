# mcuxsdk-core

- 真实源码目录：`./mcuxsdk-core/`
- 当前参考分支：`main`
- 当前参考版本：`4cc1d817`
- 主要链路：`mcore-rtos`

## 使用规则

1. 先确认任务是不是落到 `MCUX SDK` 基础代码
2. 先核对当前 ref
3. 只读检查可直接在这里做
4. 要改、要编、要集成，复制到 `../../work/<case>/` 再做

## 已吸收：`imx943-mcore-rtos` baseline-app 角色

对 `i.MX943 M-core RTOS`：

- `MCUX SDK` core 是 `M7_0` / `M7_1` / `M33S` payload 的上游 source owner 之一
- 第一轮吸收后的稳定 baseline app 认知是 stock `hello_world`
- owner 需要先把 per-core payload contract 说清，再交给 `flash_all`

当前稳定边界：

- `RTE 3.4`
  validated
- `RTE 3.3`
  unsupported / unvalidated

## 已吸收：Zephyr / latest-SDK 边界

这里不要把：

- `MCUX SDK` source baseline
- manifest / workspace bootstrap
- Zephyr host bootstrap

混成一层。

第一轮迁移后：

- `mcuxsdk-core`
  更偏向 source / SDK core
- workspace 派生与 manifest 选择
  再看 `mcuxsdk-manifests`

## 待补全

- 哪些板型/版本直接复用这份基线
- 与 manifest、SDK、示例工程的关系
- 相关旧 skill 的吸收结果
