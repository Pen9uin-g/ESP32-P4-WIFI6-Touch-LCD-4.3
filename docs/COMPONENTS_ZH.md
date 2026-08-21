# 组件与依赖边界

[English](COMPONENTS.md)

本仓库同时包含产品代码、本地板级支持、上游派生源码、托管依赖和一个预编译组件，
不能把所有 `components/` 目录都视为可删除或由组件注册表完整托管。

| 区域 | 分类 | 维护边界 |
| --- | --- | --- |
| `05_sdmmc/components/sd_card` | 示例本地源码 | 提供示例 05 使用的 SD 测试封装，应随该示例保留 |
| `12_usb_extend_screen/components/bsp_extra` | 产品应用扩展 | 提供示例 12 实际使用的板级编解码器、播放器和文件 API，不能只用基础 BSP 替换 |
| 示例 06–12 中的基础 `esp32_p4_wifi6_touch_lcd_4_3` 依赖 | 临时上游源码锁定 | 每个基础 BSP manifest 仍从[上游 PR #191](https://github.com/waveshareteam/Waveshare-ESP32-components/pull/191)的提交 `ac94f5da7c0e44963828ab970337e89d23e04330` 解析。该旧锁定早于 Rev3.x 时钟和 GT911 无 INT/RST 修复，不能作为最终产品依赖 |
| 示例 11 的 Brookesia 组件 | 内嵌/本地集成 | `brookesia_core` 和 Squareline 应用有意通过本地路径解析；嵌套测试工程不是产品 CI 工程 |
| `10_mp4_player/components/esp_extractor` | 预编译供应方组件 | 播放器依赖按目标区分的静态库；仓库中没有其源码及完整来源信息 |
| `idf_component.yml` 声明的依赖 | 托管或 Git 依赖 | Actions 按声明从组件注册表或 Git 源解析；生成的 `managed_components/` 目录不是仓库源码 |

示例 10 将 `espressif/esp_audio_codec` 约束为 2.3 及以上、但低于 2.6 的版本。
2.6 及以上版本要求 ESP32-P4 芯片 revision 3.0，而显式的 Rev1.3 兼容配置仍支持
更早的 P4 芯片。在该兼容要求改变前应保留此上界。

示例 11 的 Brookesia AI 路径仅在 ESP-IDF `v5.5.5` 下编译；在该版本线上启用 AI 时，
其条件 manifest 规则会解析一致的 GMF 0.6 依赖集。GMF 0.6.x AI 组件在其 CMake 文件顶层
调用 `idf_build_set_property`，ESP-IDF v6.0 会在早期的 `component_get_requirements` 阶段
拒绝该调用，因此 AI 覆盖配置暂不进入 v6 通道。GMF 0.6 还缺少较新的 keep-awake API，
因此说话计时器和状态流程不会调用该不可用函数。仅启用 AI 的 `brookesia_core` C++ 源码
会添加 `-fpermissive` 以兼容 GMF 0.6 的 C 头文件；默认及非 AI 配置不会获得该标志。
今后升级 GMF 时必须保持 API 相互耦合的依赖集一致，恢复 v6 AI 通道，并同时验证两个
IDF 版本线，不能只推进其中一个组件。

示例 12 会下载 `usb_device_uac` 1.2.0，但将其标记为非必需。只有启用 UAC 音频时才
链接该组件，因此最小 HID/显示配置不会无条件依赖 UAC 构建。较旧 IDF 仍可能编译下载的
目标。顶层 `project()` 创建托管组件目标后，`TARGET` 守卫仅为该 UAC 目标私有地定义
TinyUSB 音频；产品描述符和应用仍保持关闭。

示例 12 的 `bsp_extra` 树仍是本地产品应用扩展。它不是基础 BSP 的替代品；在基础 BSP 从
锁定的上游源码解析时，应有意保留。示例 08 没有调用扩展 API，因此移除其未使用副本及
音频依赖。当前锁定不是 ESP Component Registry 发布版本。更新后的 PR #191 BSP 使用
ESP-IDF 按芯片版本选择的 MIPI PHY 时钟源，并在 INT、RST 均不指定时依次探测 GT911 的
`0x5D`、`0x14` 地址。其 ST7701 与 GT911 依赖已经是已发布的上游组件，因此本次产品修复
不需要再拆分单独的 LCD 驱动 PR。

必须遵循以下发布顺序：

1. 审核并合并更新后的组件/BSP PR #191；
2. 将 `waveshare/esp32_p4_wifi6_touch_lcd_4_3` 发布到 ESP Component Registry；
3. 用干净的 ESP-IDF 构建确认该在线版本可以解析；
4. 在单独的产品提交/PR 中，把 7 处临时 Git 映射全部切换到已发布 Registry 版本，
   并同步更新仓库策略检查；
5. 在最终产品提交上重新构建全部适用 ESP-IDF 通道。

不能通过提交新的 Git 地址或尚未发布的 Registry 版本来绕过发布顺序。Git/path 来源不能
作为面向 Registry 的最终产品依赖，未发布的语义版本也会导致依赖解析失败。本地构建可以
临时使用已审核 BSP 源码，但该覆盖不能进入产品 manifest。

Registry 发布后，应先解析并编译受影响示例，再在产品硬件上完成后续 HIL 流程：启动开发板，
验证 480 × 800 显示和 GT911 触摸，测试音频和 SDIO，并运行适用的 USB 或视频路径。
在把产品依赖更新视为已通过硬件验证前，应将硬件证据与 Actions 结果分开记录。

不要基于新的许可证假设替换或重新分发 `esp_extractor` 静态库。任何来源或许可边界变更
都需要维护者确认源码来源及权利。本文件只记录技术边界，不构成第三方许可授权。
