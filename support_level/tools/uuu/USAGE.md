# uuu

- 程序入口：`./uuu`
- 当前版本：`libuuu_1.5.243-0-g230f1b1`
- 工具角色：USB 传输、下载态探测、原始启动镜像写入、FAT 文件写入

## 先读什么

先确认四件事：

1. 当前板是否真的处在期望 USB 状态
2. 当前要操作的是：
   - 下载态探测
   - 原始启动镜像
   - FAT 运行时文件
3. 当前文件的产物类别是否已经分清
4. 这次要证明的是传输是否成立，还是后续运行态是否成立

## 典型命令形态

查帮助或版本：

```bash
./uuu -h
./uuu -v
```

列 USB 已知设备：

```bash
./uuu -lsusb
```

常见内置脚本：

```bash
./uuu -b sd <flash.bin>
./uuu -b sd_all <flash.bin> <wic>
./uuu -b fat_write <file> mmc 1:1 <name>
```

## 使用边界

- `uuu` 负责的是传输动作，不负责运行态验证
- `-b sd` 常用于原始启动镜像
- `-b fat_write` 常用于 `Image` / `dtb` / `.ko` 这类 FAT 运行时文件
- 不要把 `imx-mkimage` 产出的启动镜像误当成 `fat_write` 文件

## 当前阶段相关的硬规则

- first-stage `uuu -b sd <flash.bin>` 的前提，是当前证据能够证明板子仍在下载态，而不是只凭“刚 reset 过”
- 复用当前 `FB` 会话做 second-stage 写入前，先证明第一阶段已经把板子拉进 `U-Boot fastboot / FB`
- second-stage 写入成立，只能先说明当前 `FB` 中继动作成立，不自动证明最终启动链或运行态已经成立
- 如果当前只是想证明板子还在下载态，优先先看 `uuu -lsusb` 这类强信号，不要让串口静音反过来替 USB 阶段做判断

## 当前注意事项

- 同样是 `uuu -b sd`，从 `SDPS` 开始和复用当前 `FB` 会话，不是同一种验证
- `uuu` 成功返回，只能先说明传输和写入成立，不自动证明 Linux、登录或运行态已经接管
- 板型相关的 USB 枚举解释、第一阶段 / 第二阶段中继语义，不写在这里，去对应板级文档读取

当前已拆进 `board_knowledge/` 的板型入口：

- `../../board_knowledge/imx943evk19a0/README.md`
- `../../board_knowledge/imx8dxlevk/README.md`
- `../../board_knowledge/imx93evk14/README.md`
- `../../board_knowledge/imx95evk19/README.md`
