# 在板载 LCD 上预览摄像头画面

[English](README.md)

本示例从 MIPI-CSI 摄像头采集图像，并显示到
ESP32-P4-WIFI6-Touch-LCD-4.3 板载的 4.3 英寸 480 × 800 ST7701
MIPI-DSI 屏幕。

默认配置选择 OV5647 MIPI 传感器的 RAW8、800 × 1280、50 fps 模式。应用从
V4L2 设备读取实际协商的摄像头尺寸，通过 ESP32-P4 的 PPA 转换图像，并将画面
居中裁剪到 LCD；应用不会缩放图像。因此，可见区域和方向取决于实际摄像头模块及
安装方向。

## 所需条件

- ESP32-P4-WIFI6-Touch-LCD-4.3 开发板。
- 连接到板载 15PIN MIPI-CSI 接口的兼容 OV5647 摄像头。
- ESP-IDF `v5.5.5` 或 `v6.0.2`；仓库 Actions 会编译验证这两个版本。
- 用于供电、烧录和串口输出的 USB 连接。

上电前请根据[官方产品文档](https://docs.waveshare.net/ESP32-P4-WIFI6-Touch-LCD-4.3/)
确认摄像头方向、排线触点方向及模块兼容性。

## 配置

仓库内的 `sdkconfig.defaults` 已选择 ESP32-P4、32 MB Flash、200 MHz PSRAM、
三个 LCD 帧缓冲、OV5647 支持以及板级 BSP 使用的 I2C 引脚。BSP 颜色格式可选择
RGB565（默认）或 RGB888，Actions 会编译验证两条路径。

如需更换摄像头配置，请先通过 `idf.py menuconfig` 检查传感器模式和板级支持包
设置。

## 构建、烧录与监视

在已激活 ESP-IDF 环境的本目录执行：

```console
idf.py set-target esp32p4
idf.py -p PORT flash monitor
```

请将 `PORT` 替换为开发板的 USB 转 UART 串口，按 `Ctrl-]` 退出监视器。Actions
构建成功只证明源码可编译；摄像头信号质量、图像方向和显示时序仍需在目标硬件上验证。
