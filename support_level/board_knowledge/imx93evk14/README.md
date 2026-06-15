# imx93evk14

## 适用范围

- 板型：`i.MX93 14x14 LPDDR4x EVK`
- 当前主机：Ubuntu 本机
- 来源：旧 `imx93-generic-deploy-cycle` / `imx93-generic-workflow` 已验证 deploy 事实

## 当前已知镜像根

当前 v2 里已落到本地的 full image bundle：

- `../../Image/LF_v6.6.52-2.2.0_images_IMX93EVK/`

这里面当前已知的重要文件包括：

- `imx-image-full-imx93evk.wic`
- `imx-boot-imx93-14x14-lpddr4x-evk-sd.bin-flash_singleboot`
- `imx93-14x14-evk.dtb`
- `Image-imx93evk.bin`
- `imx_mcore_demos/imx93-14x14-evk_m33_TCM_power_mode_switch.bin`

## deploy shape 分类

这块板当前已验证应先分 deploy shape，而不是先写命令。

### 1. Full Image Restore

适用于：

- 全量恢复
- 会覆盖当前介质内容
- 属于 persistent write

当前已知对应输入：

- `imx-image-full-imx93evk.wic`
- `imx-boot-imx93-14x14-lpddr4x-evk-sd.bin-flash_singleboot`

对应的典型 transport 形态是：

- `sd_all`

注意：

- 这类动作默认属于高风险 persistent write
- 没有明确允许前，不应直接执行

### 2. FAT Artifact Replace

适用于：

- 只替换运行时文件
- 例如 kernel / dtb / mcore demo

当前已知 runtime name 包括：

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
- `target medium` / `partition` / `runtime filename` 不明确时，不要猜着写

## 运行时文件默认认知

- `Image`
  属于 FAT runtime file
- `imx93-14x14-evk.dtb`
  属于 FAT runtime file
- `imx-boot-imx93-14x14-lpddr4x-evk-sd.bin-flash_singleboot`
  属于 raw boot blob，不是 FAT file
- `.wic`
  属于 full image restore 输入，不是单文件替换输入

## M33 相关已知基线

- 当前已知 good stock demo：
  `imx93-14x14-evk_m33_TCM_power_mode_switch.bin`
- 历史已知 `U-Boot` 路径可以通过 `bootaux` 带起 M33
- 不要把 `remoteproc stop` 当成 generic 默认动作

## handoff 边界

- 如果 deploy 后还缺 boot proof，下一层应转到 boot verify
- 如果 boot 已经完成，只缺 Linux shell proof，下一层应转到 login verify
- 如果已经 Linux-up 且目标是 app 层，deploy lane 不再继续占有

## 已吸收：boot-stage proof owner 边界

对 `i.MX93` board-generic lane：

- boot verify 负责判断当前到底在：
  `serial download`
  `U-Boot`
  Linux-up
- 它不负责：
  full image burn
  FAT artifact replace
  Linux build
  app-layer runtime
  risky `M33` / `remoteproc` debug

当前这条 lane 的强信号顺序仍应是：

1. board-control state
2. USB enumeration / transport identity
3. validated serial evidence

不要因为串口暂时安静，就先默认串口错了。

## 已吸收：boot verify 的 fallback / handoff 规则

- 如果 current state / target state / persistence class 还不清楚，
  先回到更上层 workflow，不要直接猜
- 如果当前 unresolved 的只有 Linux login，
  才交给 login verify
- 如果还可能停在 `serial download` 或 `U-Boot`，
  不要让 login verify 反过来替 boot verify 做阶段判断
- 如果任务又重新变成 deploy / overwrite / full image restore，
  就返回 deploy lane，不要在 boot verify 里硬做

## 已吸收：Linux shell proof owner 边界

对 `i.MX93` board-generic lane：

- login verify 负责：
  找到 active Linux login path
  留下最小 runtime proof
  判断是否已经能交给 app-layer
- login verify 不负责：
  判定板子是不是其实还停在 `U-Boot`
  猜 SSH 地址
  在多串口都不确定时冒险发状态改变命令

当前最小 runtime proof 集合先收：

- `uname -a`
- `cat /etc/os-release`
- `mount`
- `ip addr`

## 已吸收：host-check owner 边界

对 `i.MX93`：

- host check 只负责：
  本地资产
  工具解析
  serial candidate
  下一步需要的 hardware layer
- host check 不负责：
  执行 `uuu`
  执行 `bcu`
  打开 live serial
  宣称当前板子已经在某个 boot state

## 已吸收：OpenClaw app-layer 边界

- OpenClaw 属于 Linux-up 之后的 app layer
- 它不属于：
  serial download recovery
  `flash.bin`
  `U-Boot`
  Linux boot triage
- 只有当板子已经：
  Linux reachable
  并且 SSH reachable
  才应转到这条 lane
- 当前 app-layer 默认关注的是：
  board-local install
  `/root/.openclaw` runtime layout
  `openclaw-gateway.service`
  demo playback helper

## 注意事项

- 这块板的 deploy lane 先要分清：
  full image restore
  还是 FAT artifact replace
- version line 不明确时，不要默认 `LF_v6.6.52-2.2.0_images_IMX93EVK` 就一定是当前目标
- 任何会覆盖当前板卡或介质状态的动作，都必须先确认用户允许
