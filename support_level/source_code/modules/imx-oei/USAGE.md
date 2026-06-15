# imx-oei

- 真实源码目录：`./imx-oei/`
- 当前参考分支：`master`
- 当前参考版本：`lf-6.18.2-1.0.0`
- 主要链路：`boot-firmware`

## 使用规则

1. 先确认任务是不是落到 `OEI`
2. 先核对当前 ref
3. 只读检查可直接在这里做
4. 要改、要编、要出产物，复制到 `../../work/<case>/` 再做

## 已吸收：`imx943-flashbin` 输入角色

在旧 `imx943-flashbin` 里，`OEI` 是 `i.MX943 flashbin` 的固定输入之一。

对 `i.MX943`：

- 通用命令形态里默认带 `OEI=YES`
- 最终要向 `imx-mkimage` 提供 `oei-m33-ddr.bin`

当前版本观察：

- 本地这份 `imx-oei` 的版本家族是 `lf-6.18.2-1.0.0`
- 这一点和旧 skill 里 `RTE 3.4` 的期望家族一致

## 已吸收：`imx95-rte33-build-flashbin` 输入角色

对 `i.MX95 RTE 3.3 flash.bin`：

- `OEI` 是 output-affecting identity 的关键来源之一
- 重点不是“有没有 `oei-m33-ddr.bin`”
- 而是它是否真的是目标 revision 对应的 `OEI`

关键点：

- 已验证 lane 要求 `r=B0`
- 要优先检查 `build/mx95lp5/ddr/build_info.h`
- 应看到：
  `MIMX95(B0)`

高风险误区：

- 某些看起来像 transport / `uuu` 的失败，实际应先怀疑 `OEI` revision 选错

## 待补全

- 不同芯片/板型的使用方式
- 编译命令
- 相关旧 skill 的吸收结果
