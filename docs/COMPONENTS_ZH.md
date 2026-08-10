# 组件与依赖边界

[English](COMPONENTS.md)

本仓库同时包含产品代码、本地板级支持、上游派生源码、托管依赖和一个预编译组件，
不能把所有 `components/` 目录都视为可删除或由组件注册表完整托管。

| 区域 | 分类 | 维护边界 |
| --- | --- | --- |
| `05_sdmmc/components/sd_card` | 示例本地源码 | 提供示例 05 使用的 SD 测试封装，应随该示例保留 |
| `08_lvgl_demo_v9/components/bsp_extra` 与 `12_usb_extend_screen/components/bsp_extra` | 产品应用扩展 | 提供板级编解码器、播放器和文件 API，不能只用基础 BSP 替换 |
| 示例 07–12 中的本地 `esp32_p4_wifi6_touch_lcd_4_3` | 产品 BSP 快照 | 本地组件优先于同名托管依赖；在确认注册表版本的 API、Kconfig 和硬件行为等价前应保留 |
| 示例 11 的 Brookesia 组件 | 内嵌/本地集成 | `brookesia_core` 和 Squareline 应用有意通过本地路径解析；嵌套测试工程不是产品 CI 工程 |
| `10_mp4_player/components/esp_extractor` | 预编译供应方组件 | 播放器依赖按目标区分的静态库；仓库中没有其源码及完整来源信息 |
| `idf_component.yml` 声明的依赖 | 托管依赖 | Actions 从 ESP Component Registry 解析；生成的 `managed_components/` 目录不是仓库源码 |

示例 10 将 `espressif/esp_audio_codec` 约束为 2.3 及以上、但低于 2.6 的版本。
2.6 及以上版本要求 ESP32-P4 芯片 revision 3.0，而本产品仓库内的默认配置有意支持
更早的 P4 revision。在产品支持的最低硬件版本改变前应保留该上界。

示例 11 的 Brookesia AI 路径只在 ESP-IDF `v5.5.5` 下编译。GMF 0.6 缺少 Brookesia
较新使用的 wake 与 keep-awake API，因此说话计时器和状态流程不会调用不可用的
keep-awake API。仅在启用可选 AI 框架时，`brookesia_core` 自身的 C++ 源码才添加
`-fpermissive` 以兼容 GMF 0.6 的 C 头文件；默认及非 AI 配置不会获得该标志。在能够整体
升级并验证这组 API 相互耦合的 GMF 依赖前，应在 IDF 6 下保持关闭 AI：`gmf_ai_audio`
0.7.2 的证据仅对应其 trigger wake/sleep API，不能证明存在 keep-awake API，也不能证明
单独升级组件是安全的迁移。

示例 12 会下载 `usb_device_uac` 1.2.0，但将其标记为非必需。只有启用 UAC 音频时才
链接该组件，因此最小 HID/显示配置不会无条件依赖 UAC 构建。较旧 IDF 仍可能编译下载的
目标。顶层 `project()` 创建托管组件目标后，`TARGET` 守卫仅为该 UAC 目标私有地定义
TinyUSB 音频；产品描述符和应用仍保持关闭。

目前尚未确认组件注册表中与本地 4.3 英寸 BSP 快照等价的精确产物。未来迁移必须锁定
候选版本、比较公开头文件和 Kconfig、保持本板 480 × 800 ST7701/GT911/音频/SDIO
行为，并在删除本地副本前通过完整 Actions 矩阵。

不要基于新的许可证假设替换或重新分发 `esp_extractor` 静态库。任何来源或许可边界变更
都需要维护者确认源码来源及权利。本文件只记录技术边界，不构成第三方许可授权。
