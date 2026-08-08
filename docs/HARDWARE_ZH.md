# 基于原理图的硬件审计

[English](HARDWARE.md)

本审计对比仓库内的[产品原理图](../schematic/ESP32-P4-WIFI6-Touch-LCD-4.3-schematic.pdf)
与示例 07–12 使用的本地板级支持组件。它属于仓库审查，不能替代对实际硬件版本的核对。

## 已确认的产品接口

| 功能 | 原理图 / BSP 核对结果 |
| --- | --- |
| 主控与无线芯片 | ESP32-P4 应用处理器及 ESP32-C6-MINI-1 无线协处理器 |
| 外置 Flash | U10 为 GD25Q256，即 256 Mbit（32 MB）NOR；全部产品示例默认配置已统一选择 32 MB |
| 显示 | 4.3 英寸 480 × 800 ST7701、2-lane MIPI-DSI；背光 GPIO26，LCD 复位 GPIO27 |
| 触摸 | GT911 通过 I2C 连接；SCL GPIO8、SDA GPIO7、触摸复位 GPIO23 |
| 音频 | ES8311 编解码器、ES7210 输入前端、NS4150B 功放；MCLK GPIO13、SCLK GPIO12、LRCK GPIO10、DOUT GPIO9、DIN GPIO11、功放使能 GPIO53 |
| MicroSD | SDMMC D0/D1/D2/D3 为 GPIO39/40/41/42，CMD GPIO44，CLK GPIO43 |
| USB | 包含独立的 USB 高速 OTG 与 USB 转 UART 通路 |

## 本次审计有意不修改的项目

- 原理图提供 `TP_INT` 网络，而当前 BSP 将 GT911 中断引脚配置为未连接。抽取的原理图
  文本不能证明完整的网络到 GPIO 映射，因此直接修改驱动会引入未经证实的硬件假设。
- 原理图中有三个按键器件，但 BSP 声明按钮数量为零，也未定义按键 GPIO API。是否暴露
  这些按键需要产品级行为决策和实板验证。
- Actions 编译不能验证 MIPI 时序、摄像头信号质量、触摸中断、音频通路、SDIO 通信或
  USB 电气行为。

这些待确认项应结合源设计/网表及已知硬件版本解析，并在修改 BSP 能力标志或引脚前
完成实板验证。
