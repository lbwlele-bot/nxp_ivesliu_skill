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
- 让“源码可编辑的 SDK 路线”和“固定压缩包 SDK 路线”分清

它不等于：

- 某个板子的 payload 构建入口
- 某个当前运行态的判断入口

## 已吸收：主机环境准备 认知

像下面这些链路，第一轮会经过 manifest / workspace 这一层：

- `MCUX SDK` 源码可编辑路线
- west / workspace 初始化路线
- 一些 Zephyr / 最新 SDK 相关路线

共同边界：

- 共享 workspace / 最新 workspace
  和 case 本地可修改 workspace 要分开
- 不要在共享基线里直接构建或打 patch

## 待补全

- manifest 对应的芯片/版本关系
- 常用拉取方式
- 相关旧 skill 的吸收结果
