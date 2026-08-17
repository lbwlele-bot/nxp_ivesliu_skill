# imx-sm

- 真实源码目录：`./imx-sm/`
- 最近观察分支（使用前重新核对）：`master`
- 最近观察版本（使用前重新核对）：`lf-6.18.2-1.0.0`
- 主要链路：`SMFW` / `flash.bin` 上游输入

## 角色

`imx-sm` 用来生成 System Manager firmware。
在当前启动固件链里，它通常作为 `imx-mkimage` 的上游输入，
典型产物是：

```text
m33_image.bin
```

本页只负责 `SMFW` 项目自己的源码核对、配置选择、构建命令和产物交接。
是否需要 `RTE` 专用配置、是否要同步 RTE patch bucket、最终 recipe 是
`flash_a55` 还是 `flash_all`，先由：

- `../../../software_stacks/rte.md`
- `../../../compile_targets/flashbin/README.md`

决定。

## 使用前提

进入本页前，至少先确认：

- 目标 SoC / board
- 软件栈和版本家族
- 目标配置名，例如 `mx95evk` 或其他 `configs/` 下的配置
- 是否需要 RTE 专用配置
- `arm-none-eabi` 工具链位置
- 最终是否作为 `flash.bin` 输入交给 `imx-mkimage`

如果目标是完整 `flash.bin`，不要直接从这里开始；
先回到 `../../../compile_targets/flashbin/README.md` 判断完整输入集合。
如果任务属于 `RTE`，先读 `../../../software_stacks/rte.md`。

## 共享源码规则

1. 先用 `git status --short --branch` 和 `git describe --tags --always --dirty` 核对当前 ref
2. 只读检查可直接在共享源码目录做
3. 要改、要编、要生成输出，复制到 `../../../work/<case>/` 再做
4. 不要在共享源码目录里长期留下构建输出

## 配置线索

源码里的配置入口在：

```text
configs/
```

当前可见的代表性配置包括：

```text
configs/mx94evk.cfg
configs/mx95evk.cfg
configs/other/mx95rte.cfg
```

`configs/other/mx95rte.cfg` 是 RTE 相关候选配置。
是否使用它由当前 RTE 软件线和 case 目标决定，
不要从 `mx94rte` 或其他相近名字推导 `i.MX95`。

## 构建命令形态

`make cfg` 会从 `configs/<config>.cfg` 生成目录 `configs/<config>/`。
这个生成目录不会被 `make really-clean` 删除，残留内容可能使新的 cfg
没有完全生效。因此当前工作区的完整刷新命令是：

```bash
cd /home/ives/桌面/NXP_v2/support_level/work/<case>/imx-sm
rm -rf configs/mx95evk
make really-clean
make config=mx95evk cfg
make config=mx95evk all
```

只能删除不带 `.cfg` 后缀的生成目录。不要删除 `configs/mx95evk.cfg`，
也不要删除整个 `configs/`。

RTE 配置如果已经由上层判定为当前目标，命令形态是：

```bash
cd /home/ives/桌面/NXP_v2/support_level/work/<case>/imx-sm
rm -rf configs/other/mx95rte
make really-clean
make config=other/mx95rte cfg
make config=other/mx95rte all
```

这些是命令形态，不是固定 case 配方。
实际 `config=`、toolchain、patch、debug 和输出目录必须按当前 case 确认。
flashbin 工作流中的这个顺序由 `compile-tool` 的 SMFW policy 强制检查。

## 产物交接

典型输出是：

```text
build/<config>/m33_image.bin
```

如果当前目标是完整 `flash.bin`，
把 `m33_image.bin` 交给当前 case 里的 `imx-mkimage` 工作目录，
再回到：

```text
../../../compile_targets/flashbin/README.md
```

继续完成最终打包。

不要把单独生成 `m33_image.bin` 理解成 `flash.bin` 已经完成。

## RTE 局部动作边界

当上层已经判定当前任务属于 RTE 链路时，本项目局部需要关注：

- 只同步真正属于 `SMFW` 的 RTE patch bucket
- patch 是否触及当前目标 SoC、配置和 `m33_image.bin` 链路
- RTE 配置是否明确落到当前目标，例如 `configs/other/mx95rte.cfg`

完整 RTE 规则仍以 `../../../software_stacks/rte.md` 为 owner。

## 不该在这里判断的事

- 不在这里决定完整 `flash.bin` 输入集合
- 不在这里决定 `flash_a55` / `flash_all`
- 不在这里决定 RTE 对 ATF / OP-TEE / U-Boot / Linux 的要求
- 不在这里解释 `uuu`、烧写或运行态验证

这些分别属于 `compile_targets/flashbin/`、`software_stacks/`、
`tools/uuu/` 和 `board-exec`。
