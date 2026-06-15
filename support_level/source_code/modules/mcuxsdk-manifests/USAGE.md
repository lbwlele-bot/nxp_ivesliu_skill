# mcuxsdk-manifests

- 真实源码目录：`./mcuxsdk-manifests/`
- 当前参考分支：`main`
- 当前参考版本：`v26.03.00`
- 主要链路：`mcore-rtos`

## 使用规则

1. 先确认任务是不是落到 `MCUX SDK manifest` 选择
2. 先核对当前 ref
3. 只读检查可直接在这里做
4. 需要派生 workspace 时，在 case 目录下做，不直接污染共享基线

## 已吸收：workspace / manifest 选择边界

第一轮迁移后，这里的稳定角色是：

- 选择 manifest
- 派生 workspace
- 让 source-editable SDK lane 和固定 archive SDK lane 分清

它不等于：

- 某个 board-specific payload owner
- 某个 live runtime owner

## 已吸收：host bootstrap 认知

像下面这些 lane，第一轮会经过 manifest / workspace 语义：

- `MCUX SDK` source-editable lane
- west / workspace bootstrap lane
- 一些 Zephyr / latest SDK 相关 lane

共同边界：

- shared workspace / latest workspace
  和 case-local mutable workspace 要分开
- 不要在共享基线里直接 build / patch

## 待补全

- manifest 对应的芯片/版本关系
- 常用拉取方式
- 相关旧 skill 的吸收结果
