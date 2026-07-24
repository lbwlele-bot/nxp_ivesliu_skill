# imx93evk14

## 适用范围

- 板型：`i.MX93 14x14 LPDDR4x EVK`
- 当前主机：Ubuntu 本机
- 来源：旧 `i.MX93` 通用上板流程中的已验证上板事实

## 当前已知镜像根

当前 v2 里已落到本地的完整镜像包：

- `../../Image/LF_v6.6.52-2.2.0_images_IMX93EVK/`

这里面当前已知的重要文件包括：

- `imx-image-full-imx93evk.wic`
- `imx-boot-imx93-14x14-lpddr4x-evk-sd.bin-flash_singleboot`
- `imx93-14x14-evk.dtb`
- `Image-imx93evk.bin`
- `imx_mcore_demos/imx93-14x14-evk_m33_TCM_power_mode_switch.bin`

## 上板写入形态分类

这块板当前已验证应先分上板写入形态，而不是先写命令。

### 1. 全量镜像恢复

适用于：

- 全量恢复
- 会覆盖当前介质内容
- 属于持久写入

当前已知对应输入：

- `imx-image-full-imx93evk.wic`
- `imx-boot-imx93-14x14-lpddr4x-evk-sd.bin-flash_singleboot`

对应的典型传输形态是：

- `sd_all`

注意：

- 这类动作默认属于高风险持久写入
- 没有明确允许前，不应直接执行

### 2. FAT 文件替换

适用于：

- 只替换运行时文件
- 例如 kernel / dtb / mcore demo

当前已知运行时文件名包括：

- `Image`
- `imx93-14x14-evk.dtb`
- `mcore-demos/imx93-14x14-evk_m33_TCM_power_mode_switch.bin`

这类动作的典型形态是：

1. 先用 trusted 14x14 boot blob 建立临时 fastboot 路径
2. 再用 `fat_write` 写目标文件

## 已验证的高频注意事项

- `-b sd` 建立的是临时 USB / fastboot 路径
- 不要假设前一次 fastboot 路径在 reset 或 unknown-state recovery 后还活着
- 不要对同一块板并行发多个 `fat_write`
- `target medium` / `partition` / 运行时文件名不明确时，不要猜着写

## 运行时文件默认认知

- `Image`
  属于 FAT 运行时文件
- `imx93-14x14-evk.dtb`
  属于 FAT 运行时文件
- `imx-boot-imx93-14x14-lpddr4x-evk-sd.bin-flash_singleboot`
  属于原始启动 blob，不是 FAT 文件
- `.wic`
  属于 full image restore 输入，不是单文件替换输入

## M33 相关已知基线

- 当前已知可用的标准 demo：
  `imx93-14x14-evk_m33_TCM_power_mode_switch.bin`
- 历史已知 `U-Boot` 路径可以通过 `bootaux` 带起 M33
- 本地 case 证据里，M33 console 曾出现在 `ttyUSB3`
- 机器可读串口映射见：
  `serial.yaml`
- 不要把 `remoteproc stop` 当成通用默认动作

## 串口与 BCU reset

2026-07-24 在当前 i.MX93 14x14 LPDDR4x EVK 上重新验证：

- FT4232H 固定枚举四个 COM：`if00-if03`
- 第三个 COM，`if02` / `ttyUSB2`：SPL、U-Boot、Linux console
- 第四个 COM，`if03` / `ttyUSB3`：M33 console
- 前两个 COM 当前不分配默认运行日志 role；`if01` 同时被 BCU 板控使用
- 默认抓取 `a-core` 和 `m33`，不盲抓全部四个接口

这块板允许 BCU reset，不继承 i.MX8DXL 的 manual-reset-only 特例：

```bash
sudo -n ../../tools/bcu/bcu reset -board=imx93evk14
```

当前实测 BCU reset 连续 3/3 次在退出后留下未绑定的 `if01`。板子和
A-core/M33 日志口不因此失效，但 fresh probe 会只看到三个 COM。恢复：

```bash
sudo -n ../../tools/serial-console/serial-console recover --board imx93evk14
../../tools/serial-console/serial-console probe --board imx93evk14
```

恢复后必须重新看到 `if00-if03` 四个 interface。不要写 EEPROM 来规避该
主机驱动绑定问题。

## 交接边界

- 如果上板写入后还缺启动阶段判断，下一层应转到启动验证
- 如果启动已经完成，只缺 Linux shell 验证，下一层应转到登录验证
- 如果已经证明 Linux 已起来且目标是应用层，上板写入这一层就不再继续占有

## 已吸收：启动阶段判断边界

对 `i.MX93` 板级通用路径：

- 启动验证 负责判断当前到底在：
  `serial download`
  `U-Boot`
  Linux 已起来
- 启动验证不负责：
  full image burn
  FAT 文件替换
  Linux 构建
  应用层运行态
  risky `M33` / `remoteproc` debug

当前这条路径的强信号顺序仍应是：

1. 板控状态
2. USB 枚举 / 传输身份
3. 已验证串口证据

不要因为串口暂时安静，就先默认串口错了。

## 已吸收：启动验证的回退 / 交接规则

- 如果当前状态 / 目标状态 / 持久化类别还不清楚，
  先回到更上层工作流，不要直接猜
- 如果当前未解决的只有 Linux 登录，
  才交给 登录验证
- 如果还可能停在 `serial download` 或 `U-Boot`，
  不要让 登录验证 反过来替 启动验证 做阶段判断
- 如果任务又重新变成上板写入 / 覆盖写入 / 全量镜像恢复，
  就返回上板写入这一层，不要在启动验证里硬做

## 已吸收：Linux shell 验证边界

对 `i.MX93` 板级通用路径：

- 登录验证 负责：
  找到实际 Linux 登录路径
  留下最小 运行态验证
  判断是否已经能交给 app-layer
- 登录验证 不负责：
  判定板子是不是其实还停在 `U-Boot`
  猜 SSH 地址
  在多串口都不确定时冒险发状态改变命令

当前最小运行态验证集合先收：

- `uname -a`
- `cat /etc/os-release`
- `mount`
- `ip addr`

## 已吸收：主机检查边界

对 `i.MX93`：

- 主机检查只负责：
  本地资产
  工具解析
  串口候选口
  下一步需要的硬件层
- 主机检查不负责：
  执行 `uuu`
  执行 `bcu`
  打开 live serial
  宣称当前板子已经在某个 boot state

## 已吸收：OpenClaw 应用层边界

- OpenClaw 属于 Linux 已起来之后的应用层
- 它不属于：
  serial download recovery
  `flash.bin`
  `U-Boot`
  Linux 启动问题分层判断
- 只有当板子已经：
  Linux reachable
  并且 SSH reachable
  才应转到这条路径
- 当前应用层默认关注的是：
  板端本地安装
  `/root/.openclaw` 运行态布局
  `openclaw-gateway.service`
  demo playback helper

## 注意事项

- 这块板的上板写入先要分清：
  full image restore
  还是 FAT 文件替换
- version line 不明确时，不要默认 `LF_v6.6.52-2.2.0_images_IMX93EVK` 就一定是当前目标
- 任何会覆盖当前板卡或介质状态的动作，都必须先确认用户允许
