# Board Serial Profiles

本目录随 `serial-console` 一起发布，保存工具运行所需的板级串口事实。

每个板型目录包含：

- `serial.yaml`：机器可读的适配器、interface、role 和默认捕获映射
- `README.md`：该板与串口直接相关的操作约束、已验证日志和证据边界

非串口板级事实，例如 silicon revision、boot image、M 核 loader 和完整 reset
能力，仍由工作区的 `board_knowledge` 维护。`serial-console` 本身不会执行
reset 或改变 boot mode。

## 当前状态

- `imx8dxlevk`：四路 onboard FT4232H 映射完整验证
- `imx93evk14`：四路 onboard FT4232H 映射完整验证
- `imx943evk19a0`：四路 onboard FT4232H 映射完整验证
- `imx95evk19`：部分映射，`if01` role 尚未确认

新增板型必须先保留 discovery 原始日志，再按 `../PROFILE_SCHEMA.md` 增加
profile；不得根据 COM 数量猜测 Linux、M 核或系统管理固件角色。
