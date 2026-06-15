# uuu

- 程序入口：`./uuu`
- 当前版本：`libuuu_1.5.243-0-g230f1b1`
- 工具角色：USB transport / 下载态探测 / raw image 写入 / FAT 文件写入

## 先读什么

先确认四件事：

1. 当前板是否真的处在期望 USB 状态
2. 当前要操作的是：
   - 下载态探测
   - raw boot image
   - FAT runtime file
3. 当前文件的 artifact class 是否已经分清
4. 这次要证明的是 transport，还是后续 runtime

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

常见 built-in script：

```bash
./uuu -b sd <flash.bin>
./uuu -b sd_all <flash.bin> <wic>
./uuu -b fat_write <file> mmc 1:1 <name>
```

## 使用边界

- `uuu` 是 transport owner，不是 runtime proof owner
- `-b sd` 常用于 raw boot image
- `-b fat_write` 常用于 `Image` / `dtb` / `.ko` 这类 FAT runtime file
- 不要把 `imx-mkimage` boot image 误当成 `fat_write` 文件

## 当前注意事项

- 同样是 `uuu -b sd`，从 `SDPS` 开始和复用 live `FB` session，不是同一种证明
- `uuu` 成功返回，只能先说明 transport / write 成立，不自动证明 Linux / login / runtime owner 已接管
- 板型相关的 USB 枚举解释、first-stage / second-stage relay 语义，不写在这里，去对应板级层读取

当前已拆进 `board_knowledge/` 的板型入口：

- `../../board_knowledge/imx943evk19a0/README.md`
- `../../board_knowledge/imx8dxlevk/README.md`
- `../../board_knowledge/imx93evk14/README.md`
