# Arduino 示例

[English](README.md)

这 10 个示例面向使用 Arduino-ESP32 `3.3.11` 的 ESP32-P4 Rev3.1 或更新版本。
已验证的核心配置为 `ChipVariant=postv3`、启用 PSRAM、32 MB Flash、80 MHz QIO，
并使用 13 MB 应用 / 7 MB 数据分区。该预编译核心使用 200 MHz PSRAM，不等同于
ESP-IDF Rev3.x 的 250 MHz 配置，也不支持 Rev3.0。

仓库完整保留了示例实际使用的 Arduino 库，包括其上游许可证、文档和源码树：

- `GFX Library for Arduino` `1.6.0`
- 示例 04 使用的 `lvgl` `9.3.0` 及完整 `lv_conf.h` 配置

复现已审核构建时不要再用 Library Manager 下载内容覆盖这些库。Actions 工作流直接
使用仓库内版本，保证本地与 CI 使用相同源码。

这些示例还需要本板专用的 `libraries/displays` 适配层。使用 Arduino IDE 时，请将
`examples/arduino/libraries/` 中的 `GFX_Library_for_Arduino`、`lvgl`、`lv_conf.h`
和 `displays` 原样复制到 sketchbook 的 `libraries/`，不要删减其中内容；在仓库根目录
使用 Arduino CLI 时，应显式传入整个目录：

```console
arduino-cli compile --fqbn <esp32p4-fqbn> \
  --libraries examples/arduino/libraries \
  examples/arduino/examples/01_HelloWorld
```

本板专用的 `libraries/displays` 包含 480 × 800 ST7701 配置：DPI 时钟 30 MHz、
两条 500 Mbps MIPI-DSI lane，并使用 ESP-IDF 按芯片版本选择的默认 MIPI PHY
时钟源。GT911 不指定 INT 或 RST，采用轮询方式；初始化时依次探测 `0x5D`、
`0x14`，再使用有响应的地址。

| 示例 | 功能 | 硬件条件 |
| --- | --- | --- |
| `01_HelloWorld` | 屏幕彩条、文字及绘图 | 开发板 |
| `02_AsciiTable` | 字符与布局测试 | 开发板 |
| `03_Drawing_board` | GT911 五点触控画板 | 板载触摸屏 |
| `04_LVGLV9_Arduino` | LVGL 9 控件及触摸 | 板载触摸屏 |
| `05_GFX_ESPWiFiAnalyzer` | Wi-Fi 信道可视化 | 板载 ESP32-C6 无线路径 |
| `06_Camera_Preview` | OV5647 MIPI-CSI 预览 | 兼容的 OV5647 摄像头 |
| `07_Camera_ISP_Tuning` | 通过串口调节摄像头 ISP | 兼容的 OV5647 摄像头 |
| `08_SD_Card` | 四线 SDMMC 挂载及文件测试 | microSD 卡 |
| `09_Audio_Playback` | ES8311 旋律播放 | 扬声器连接到板载输出 |
| `10_Mic_Record` | ES7210 PCM 采集统计 | 板载麦克风 |

公开产品资料和仓库内原理图没有标识板载 CAN/RS485 收发器，也未提供已验证的
收发器引脚。只有在确认外接物理层接线后才能使用相应总线；这些示例不会虚构
CAN/RS485 引脚映射。

编译通过只证明 API 与源码兼容性。显示、触摸、摄像头、音频、存储、无线、MIPI
时序及长时间运行仍需在对应硬件版本和所需配件上验证。
