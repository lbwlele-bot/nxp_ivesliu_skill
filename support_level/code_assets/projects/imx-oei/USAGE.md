# imx-oei

- 真实源码目录：`./imx-oei/`
- 最近观察分支（使用前重新核对）：`master`
- 最近观察版本（使用前重新核对）：`lf-6.18.2-1.0.0`
- 主要链路：`OEI` / `flash.bin` 上游输入

## 角色

`imx-oei` 用来生成 ROM 可加载执行的 `OEI` 镜像。
在当前启动固件链里，它通常作为 `imx-mkimage` 的上游输入，
典型产物是：

```text
oei-m33-ddr.bin
```

本页只负责 `OEI` 项目自己的源码核对、构建命令和产物交付。
是否需要 `OEI=YES`、目标 SoC revision 是什么、最终 recipe 是
`flash_a55` 还是 `flash_all`，先由：

- `../../../compile_targets/flashbin/README.md`
- 必要时 `../../../software_stacks/rte.md`

决定。

## 使用前提

进入本页前，至少先确认：

- 目标 SoC / board
- DDR 类型和板级配置
- 目标 SoC revision
- 需要的 OEI 类型，例如 `ddr` 或 `tcm`
- 最终是否作为 `flash.bin` 输入交给 `imx-mkimage`
- `arm-none-eabi` 工具链位置

如果目标只是“重新打完整 `flash.bin`”，不要直接从这里开始；
先回到 `compile_targets/flashbin/README.md` 判断完整输入集合。

## 共享源码规则

1. 先用 `git status --short --branch` 和 `git describe --tags --always --dirty` 核对当前 ref
2. 只读检查可直接在共享源码目录做
3. 要改、要编、要生成输出，复制到 `../../../work/<case>/` 再做
4. 不要在共享源码目录里长期留下构建输出

## 板型和目录线索

源码里的板型目录在：

```text
boards/
```

当前可见的代表性目录包括：

```text
boards/mx943lp5-19/
boards/mx95lp5/
```

选择 `board=<name>` 时，要和当前 SoC、板型、DDR、封装和
revision 要求一起核对，不能只按目录名猜。

## 构建命令形态

官方 README 给出的 DDR OEI 命令形态是：

```bash
cd /home/ives/桌面/NXP_v2/support_level/work/<case>/imx-oei
make board=mx95lp5 oei=ddr DEBUG=1
```

典型输出：

```text
build/mx95lp5/ddr/oei-m33-ddr.bin
```

TCM init OEI 的命令形态是：

```bash
cd /home/ives/桌面/NXP_v2/support_level/work/<case>/imx-oei
make board=mx95lp5 oei=tcm DEBUG=1
```

典型输出：

```text
build/mx95lp5/tcm/oei-m33-tcm.bin
```

这些是命令形态，不是固定 case 配方。
实际 `board=`、`oei=`、`REV`、`DEBUG` 等参数必须按当前 case 决定。

## 产物交接

如果当前目标是完整 `flash.bin`，
把 `oei-m33-ddr.bin` 交给当前 case 里的 `imx-mkimage` 工作目录，
再回到：

```text
../../../compile_targets/flashbin/README.md
```

继续完成最终打包。

不要把单独生成 `oei-m33-ddr.bin` 理解成 `flash.bin` 已经完成。

## 核对重点

- `OEI` 会影响最终 boot image 的身份和行为
- 对需要指定 SoC revision 的链路，不能只检查文件存在
- 需要核对生成产物是否对应当前目标 revision、board 和 DDR
- 对 `i.MX95` 这类链路，生成后的 `build/<board>/ddr/build_info.h`
  是重要核对点

## 不该在这里判断的事

- 不在这里决定完整 `flash.bin` 输入集合
- 不在这里决定 `flash_a55` / `flash_all`
- 不在这里决定 `RTE` 软件线差异
- 不在这里解释 `uuu` 传输失败或板级运行态

这些分别属于 `compile_targets/flashbin/`、`software_stacks/`、
`tools/uuu/` 和 `board_knowledge/`。
