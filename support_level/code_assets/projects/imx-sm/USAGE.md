# imx-sm

- 真实源码目录：`./imx-sm/`
- 当前参考分支：`master`
- 当前参考版本：`lf-6.18.2-1.0.0`
- 主要链路：`启动固件`

## 使用规则

1. 先确认任务是不是落到 `SM` / `SMFW`
2. 先核对当前 ref
3. 只读检查可直接在这里做
4. 要改、要编、要出产物，复制到 `../../work/<case>/` 再做

## 已吸收：`imx943-flashbin` 输入角色

在旧 `imx943-flashbin` 里，`SMFW` 是 `i.MX943 flashbin` 的固定输入之一。

对 `i.MX943`：

- 它和 `ATF`、`OEI`、`U-Boot` 一起，构成 `imx-mkimage` 上游输入
- `flash_all` 仍然属于 boot image 打包链，不是单独的运行态文件拷贝

当前版本观察：

- 本地这份 `imx-sm` 的版本家族是 `lf-6.18.2-1.0.0`
- 这一点和旧 skill 里 `RTE 3.4` 的期望家族一致

## 已吸收：`imx95-rte33-build-flashbin` 输入角色

对 `i.MX95 RTE 3.3 flash.bin`：

- `SMFW` 既是共享 启动固件 输入
- 又带一个明确 case 特有差异：
  配置必须是 `configs/other/mx95rte.cfg`

关键点：

- 不要从 `mx94rte.cfg` 推导 `i.MX95`
- patch 同步 只同步真正属于 `SMFW` 且触及 `MIMX95` / `mx95rte` 的 patch
- 最终要向打包链提供 `m33_image.bin`

## 待补全

- 不同芯片/版本的构建入口
- 产物和上游依赖
- 相关旧 skill 的吸收结果
