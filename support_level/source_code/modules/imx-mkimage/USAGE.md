# imx-mkimage

- 真实源码目录：`./imx-mkimage/`
- 当前参考分支：`lf-6.12.49_2.2.0`
- 当前参考版本：`lf-6.12.49-2.2.0`
- 主要链路：`启动固件`

## 使用规则

1. 先确认任务是不是落到 `flash.bin` 打包或相关镜像拼装
2. 先核对当前 ref
3. 只读检查可直接在这里做
4. 要改、要编、要打包，复制到 `../../work/<case>/` 再做

## 已吸收：旧 `imx943-flashbin` 第一轮信息

这条旧 skill 说明了 `i.MX943` 的 mkimage 启动镜像链路。

它统一覆盖：

- 通用 Linux `flash_a55`
- `RTE 3.3` `flash_a55`
- `RTE 3.4` `flash_a55`
- `RTE 3.4` `flash_all`

### 这条链依赖哪些模块

最小依赖模块：

- `imx-mkimage`
- `imx-atf`
- `uboot-imx` 或 `real-time-edge-uboot`
- `imx-oei`
- `imx-sm`
- `imx-optee-os`（仅 `RTE` / `OP-TEE` 路径需要）

### 分支模型

- 通用 Linux + `flash_a55`
- `RTE 3.3` + `flash_a55`
- `RTE 3.4` + `flash_a55`
- `RTE 3.4` + `flash_all`

当前不把 `RTE 3.3 flash_all` 当成已有可直接复用的对称路径。

### 通用命令形态

`flash_a55`：

```bash
make SOC=iMX94 OEI=YES LPDDR_TYPE=<lpddr4|lpddr5> flash_a55
```

`RTE 3.4 flash_all`：

```bash
make SOC=iMX94 OEI=YES LPDDR_TYPE=<lpddr4|lpddr5> flash_all
```

### 共享规则

- 通用 Linux 通常不需要 `SPD=opteed`
- `RTE` 路径要求 `OP-TEE`
- `RTE` 路径里 `tee-raw.bin` 要按 `tee.bin` 参与打包
- `flash_a55` / `flash_all` 都是原始启动镜像，不是 FAT 运行时文件

### 最小产物边界

- `flash.bin`
- `u-boot.bin`
- `u-boot-spl.bin`
- `bl31.bin`
- `oei-m33-ddr.bin`
- `m33_image.bin`
- `tee.bin`（仅所选栈需要 `OP-TEE` 时）
- `m70_image.bin`
- `m71_image.bin`
- `m33s_image.bin`
  仅验证过的 `RTE 3.4 flash_all` 路径要求

### 当前版本缺口

这里要特别注意：

- 当前这份 `imx-mkimage` 基线是 `lf-6.12.49-2.2.0`
- 但旧 `imx943-flashbin` 里对 `RTE 3.4` 的期望家族是 `lf-6.18.2-1.0.0`

所以目前只能说：

- 旧 skill 的结构和命令形态已经开始吸收
- 但 `RTE 3.4` 这条链路还没有完成到“本目录现成可直接照抄执行”的程度

后续要继续对齐：

- 这份 `imx-mkimage` 是否要补出 `lf-6.18.2` 基线
- 还是从 `_to_absorb/` 里的旧资产拆出对应版本并转正

## 已吸收：旧 `imx95-rte33-build-flashbin` 第一轮信息

这条旧 skill 对 `i.MX95 RTE 3.3 flash.bin` 很关键的点，不是“又来一条新的打包命令”，
而是它把几个容易被混淆的归属事实钉死了。

### 这条链依赖哪些模块

最小依赖模块：

- `imx-mkimage`
- `real-time-edge-uboot`
- `imx-atf`
- `imx-optee-os`
- `imx-oei`
- `imx-sm`
- `M7` payload 基线

### 这条链路的最终打包目标

验证过的最终 packaging 目标是：

```bash
make SOC=iMX95 REV=B0 OEI=YES LPDDR_TYPE=lpddr5 flash_all
```

这里最重要的是：

- `REV` 是会影响输出结果的
- 不能猜
- 这条已验证链路是 `B0`
- `flash_all` 不能被静默替换成 `flash_a55`

### 这条链路里真正属于 `RTE` 的差异项

真正 `RTE` 特有的变化是：

- `ATF SPD=opteed`
- `OP-TEE` 必选
- `tee-raw.bin -> tee.bin`
- `ATF` patch 从 `meta-real-time-edge` 同步
- `SMFW` patch 从 `meta-real-time-edge` 同步
- `SMFW` 使用 `mx95rte`

不要把整条启动固件链都误理解成“全部是 case 特有新逻辑”。

### 验收 / 最终产物规则

对这条 `i.MX95 RTE 3.3` 链路，
除了 `flash.bin` 存在以外，还要继续确认：

- `tee.bin` 的来源确实是 `tee-raw.bin`
- `oei-m33-ddr.bin` 存在
- `m33_image.bin` 存在
- `m7_image.bin` 存在
- `OEI` 身份确实是 `MIMX95(B0)`

如果当前 workspace 里出现多个 `flash.bin`，
优先以 当前脚本 或当前 case 里明确声明的 最终输出为准，
不要只按“哪个路径先搜到”来选。

如果 `parse_container` 没直接打印字面量 `M7`，
当前这条链路可接受已验证的 `M7` TCM load address：
`0x303C0000`
作为更强的证据面。

### 与支撑层资产的关系

这条链路继续落地时，除了看源码模块，
还要回头读：

- `../../toolchain/README.md`
- `../../firmware/README.md`

原因不是“再看一遍目录”，
而是先把：

- A-core / M-core 工具链归属
- 固定固件 blob 根目录

说清楚，再做打包。

### 当前版本缺口

这里和前面的 `i.MX943` 情况不同：

- 旧 skill 里 `imx95 RTE 3.3` 参考的是 `lf-6.12.34-2.1.0`
- 本地当前 `imx-mkimage` 基线是 `lf-6.12.49-2.2.0`

所以这里当前吸收的是：

- 归属和差异项结构
- 关键命令形态
- 不能误判的构建身份
- 验收 / 最终产物规则

还没有把这条链路变成“当前目录现成同版本操作手册”。

## 已吸收：旧 `imx943-上板写入` / `imx943-uuu-ops` 第一轮信息

对 `i.MX943`，先要把产物类别分清，而不是先想传输命令。

### 产物类别

下面这些属于：

- `原始启动镜像`

例如：

- `flash.bin`
- `imx-boot-...-flash_a55`
- `imx-boot-...-flash_all`

它们都是 `imx-mkimage` boot image。
应走原始启动镜像路径，不应误当成 FAT 运行时文件。

相对地，下面这些才属于：

- `FAT 运行时文件`

例如：

- `Image`
- `dtb`
- `.ko`
- staged `A55` `.bin`

### 传输边界

对这类 `原始启动镜像`，
`uuu` 常见只是在做 传输：

```bash
sudo -n /home/ives/桌面/NXP/tools/uuu_1.5.243/uuu -b sd <flash.bin>
```

而不是在证明运行态已经完成。

高风险误区：

- `imx-mkimage` boot image 不要重试成 `fat_write`
- `uuu` 成功返回，不等于 Linux / 登录 / 运行态验证已完成

## 已吸收：旧 `imx8dxl-板控` 第一轮信息

对 `i.MX8DXL`，`flash.bin` 还带一个非常强的阶段语义。

### 第一阶段 基线

从 `SDPS` 开始的第一条：

```bash
uuu -b sd <基线_flash.bin>
```

它的重要意义通常是：

- 把板子从 `SDPS` 带到当前 `FB`

### 第二阶段中继

只有 第一阶段 已经成功把板子带到 `FB`，
第二阶段如：

```bash
uuu -b sd <flash_m4_flash.bin>
```

才成立。

高风险误区：

- `flash_m4` 不是 第一阶段 bring-up image
- 它不能直接替代 基线 `flash.bin` 从 `SDPS` 开始单独使用

## 待补全

- 不同 SoC 的打包入口
- 不同版本下的输入件约束
- 相关旧 skill 的吸收结果
