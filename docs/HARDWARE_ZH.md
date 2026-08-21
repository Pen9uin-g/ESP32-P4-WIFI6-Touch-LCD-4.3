# 基于原理图的硬件审计

[English](HARDWARE.md)

本审计对比仓库内的[产品原理图](../schematic/ESP32-P4-WIFI6-Touch-LCD-4.3-schematic.pdf)、
产品配置及[上游 PR #191](https://github.com/waveshareteam/Waveshare-ESP32-components/pull/191)
中的已审核 BSP 更新。该 BSP 在 ESP Component Registry 发布前，产品 manifest 仍需保留
临时审核源码锁定。本审计属于仓库审查，不能替代对实际硬件版本的核对。

## 已确认的产品接口

| 功能 | 原理图 / BSP 核对结果 |
| --- | --- |
| 主控与无线芯片 | ESP32-P4 应用处理器及 ESP32-C6-MINI-1 无线协处理器 |
| 外置 Flash | U10 为 GD25Q256，即 256 Mbit（32 MB）NOR；全部产品示例默认配置已统一选择 32 MB |
| 显示 | 4.3 英寸 480 × 800 ST7701、2-lane MIPI-DSI；背光 GPIO26，LCD 复位 GPIO27 |
| 触摸 | GT911 通过 I2C 连接；SCL GPIO8、SDA GPIO7；已审核 BSP 更新与 Arduino 适配层均不指定 INT 或 RST，依次探测 `0x5D`、`0x14` 后轮询 |
| 音频 | ES8311 编解码器、ES7210 输入前端、NS4150B 功放；MCLK GPIO13、SCLK GPIO12、LRCK GPIO10、DOUT GPIO9、DIN GPIO11、功放使能 GPIO53 |
| MicroSD | SDMMC D0/D1/D2/D3 为 GPIO39/40/41/42，CMD GPIO44，CLK GPIO43 |
| USB | 包含独立的 USB 高速 OTG 与 USB 转 UART 通路 |

## 板卡版本与时钟选择

仓库当前公开原理图标注的 PCB 版本为 `Rev1.2`，本次审计没有取得分别对应
Rev1.3/Rev3.x 的公开原理图。它可以证明共用的 40 MHz 晶振及外设接线，但不能证明两个
产品版本的 PCB 差异。已确认的软件与芯片配置差异如下：

| 配置 | Rev1.3 兼容配置 | Rev3.x 默认配置 |
| --- | --- | --- |
| ESP-IDF 最低芯片版本 | `REV_MIN_100`，选择 pre-v3 | `REV_MIN_300` |
| IDF 默认选择的 CPU 频率 | 360 MHz | 400 MHz |
| 本仓库使用的 PSRAM 频率 | 200 MHz | 250 MHz |
| MIPI DSI PHY PLL 参考时钟 | PLL_F20M，20 MHz | 40 MHz XTAL |
| 屏幕链路与像素时钟 | 2 lane × 500 Mbps；DPI 30 MHz | 相同 |
| ST7701 时序 | 480 × 800；H 42/12/42；V 2/8/60 | 相同 |

`REV_MIN_100` 是 ESP-IDF 可选的 v1.0 最低版本，也是 Rev1.3 应使用的配置；
`REV_MIN_1` 表示 v0.1，不能用来代表 Rev1.3。BSP 将 MIPI 总线 PHY 时钟源设为零，
由 ESP-IDF 在 pre-v3 芯片上选择 PLL_F20M、在 Rev3.x 上选择 XTAL。旧的
`MIPI_DSI_PHY_CLK_SRC_DEFAULT` 兼容宏始终表示 PLL_F20M，在 Rev3.x 显示初始化中可能
触发中止。30 MHz 像素时钟与 576 × 870 总时序在两个配置下均约为 59.87 Hz。
LDO3 的 2.5 V 是 DPHY 供电，不是时钟。

Arduino-ESP32 `3.3.11` 与上述 ESP-IDF 配置并不等价。其有效的
`ChipVariant=postv3` FQBN 会选择预编译库中的 `CONFIG_ESP32P4_REV_MIN_301` 和 200 MHz
PSRAM；仅可用于 P4 Rev3.1 或更新版本，不覆盖 Rev3.0，也不提供 ESP-IDF 的 250 MHz PSRAM 配置。

## 本次审计有意不修改的项目

- 原理图提供 `TP_INT` 与 `TP_RST` 网络，但 BSP 更新和 Arduino 适配层均不指定这两条线。
  GT911 依次探测 `0x5D`、`0x14` 后轮询；只有取得对应硬件版本的确认接线并完成实板验证后，
  才能增加 GPIO 配置。
- 公开产品页和原理图没有标识板载 CAN/RS485 收发器、总线接口或已验证的收发器引脚映射。
  扩展排针可以连接外部物理层，但不能只根据 ESP32-P4 外设能力推断本板具有 CAN/RS485。
- 原理图中有三个按键器件，但 BSP 声明按钮数量为零，也未定义按键 GPIO API。是否暴露
  这些按键需要产品级行为决策和实板验证。
- Actions 编译不能验证 MIPI 时序、摄像头信号质量、触摸中断、音频通路、SDIO 通信或
  USB 电气行为。

这些待确认项应结合源设计/网表及已知硬件版本解析，并在修改 BSP 能力标志或引脚前
完成实板验证。
