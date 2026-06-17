# imx-scfw-porting-kit

- 真实源码/包目录：`./imx-scfw-porting-kit/`
- 当前参考版本：`1.18.0`
- 主要链路：`启动固件`

## 使用规则

1. 先确认任务是不是确实落到 `SCFW` patch、配置或重编
2. 先核对当前拿来参考的是源码展开目录、发布包，还是 case 内副本
3. 只读检查可直接在这里做
4. 要改、要编、要出产物，复制到 `../../work/<case>/` 再做

## 当前定位

这是 `i.MX8` 系列 `SCFW` 的 porting kit / 源码资产入口。

当前优先服务的复用场景是：

- `i.MX8DXL` `SCFW` patch
- `SCFW` 构建输入和产物关系确认
- `flash.bin` / `flash_m4` 链路里的 `SCFW` 来源核对

它不负责：

- 板级下载和运行验证
- 客户 release 包的完整交付流程

这些动作应转到对应 case、`compile` 或 `board-exec`。
