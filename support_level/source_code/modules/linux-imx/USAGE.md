# linux-imx

- 真实源码目录：`./linux-imx/`
- 当前参考分支：`lf-6.12.y`
- 当前参考版本：`lf-6.12.49-2.2.0`
- 主要链路：`linux-bsp`

## 使用规则

1. 先确认任务是不是落到通用 `linux-imx` BSP 内核线
2. 先核对当前 ref
3. 只读检查可直接在这里做
4. 要改内核、编译、出 `Image/dtb/modules`，复制到 `../../work/<case>/` 再做

## 已吸收：`imx943-linux` 输入角色

对 `i.MX943` Linux kernel-side lane：

- `linux-imx` 是 generic Linux 的 board-generic kernel source owner 候选之一
- owner 负责的是：
  `Image`
  `dtb`
  `.ko`
- 不负责：
  deploy transport
  runtime proof

关键边界：

- 如果 caller 只说 `RTE`，没有 version，不要替它选 branch
- 如果当前问题其实还是 boot chain 早期失败，不要为了板子起不来就默认重编 Linux

## 第一轮吸收后的 lane 认知

- generic Linux：
  更偏向 `linux-imx`
- `RTE`：
  要再看是不是应切到 `real-time-edge-linux` 和 `meta-real-time-edge`

所以这里当前能稳定吸收的是：

- kernel-side artifact owner 边界
- generic Linux 侧的 source owner 语义

还不是所有 `i.MX943` Linux lane 的唯一源码答案

## 待补全

- 不同芯片/版本的编译方式
- 典型产物位置
- 相关旧 skill 的吸收结果
