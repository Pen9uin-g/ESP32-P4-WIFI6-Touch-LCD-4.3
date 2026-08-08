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

目前尚未确认组件注册表中与本地 4.3 英寸 BSP 快照等价的精确产物。未来迁移必须锁定
候选版本、比较公开头文件和 Kconfig、保持本板 480 × 800 ST7701/GT911/音频/SDIO
行为，并在删除本地副本前通过完整 Actions 矩阵。

不要基于新的许可证假设替换或重新分发 `esp_extractor` 静态库。任何来源或许可边界变更
都需要维护者确认源码来源及权利。本文件只记录技术边界，不构成第三方许可授权。
