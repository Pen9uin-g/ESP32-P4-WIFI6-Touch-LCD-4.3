# 持续集成

[English](CI.md)

[`ESP-IDF examples`](../.github/workflows/esp-idf-examples.yml) 工作流是本仓库的
编译门禁。每个 Pull Request、每次推送到 `main` 及手动触发都会运行；它不会烧录
硬件，也不会发布固件。

## 变更路由

| 变更 | Actions 行为 |
| --- | --- |
| `examples/esp-idf/<project>/` 下的直接示例源码 | 构建该工程及适用的条件配置 |
| 工作流、CI 辅助脚本、CI 测试或 `config/ci/` | 构建完整矩阵 |
| 仅 Markdown 或两个已审核的文档资产 | 运行带 docs-only 断言的预检，不创建 ESP-IDF 构建任务 |
| 仅治理模板、许可证或忽略规则 | 运行预检但不宣称差异仅含文档，不创建 ESP-IDF 构建任务 |
| Markdown 审计策略或其他未分类的非文档路径 | 报告该路径并保守运行完整矩阵 |
| 仓库内的出厂固件 | 运行预检并提示发布负责人审核，不把二进制当作示例构建 |
| 其他无法分类的路径 | 报告路径并保守运行完整矩阵 |
| 基准 SHA 全为零的首次/重建推送 | 运行完整矩阵，不只检查最末提交 |
| Git 差异为空或无法读取 | 路由任务失败，不猜测构建范围 |

重命名会同时按旧路径和新路径分类。Pull Request 使用基准提交与 PR 头提交比较，
不使用 GitHub 合成的 merge commit。产品工程只发现 `examples/esp-idf/` 的直接子目录，
因此内嵌组件的测试工程不会被提升为产品示例。

## 构建矩阵

默认矩阵使用 ESP-IDF `v5.5.5` 与 `v6.0.2` 编译全部 12 个产品工程，共 24 个任务。
完整源码影响运行还包含 17 个定向任务：

每个产品的 `sdkconfig.defaults` 都默认使用 Rev3.x，且每个默认任务仍会追加
`config/ci/rev3_x.defaults` 作为显式的 CI 断言。`config/ci/rev1_3.defaults` 覆盖层可用于
Rev1.3：在示例目录中执行
`idf.py -D SDKCONFIG_DEFAULTS="sdkconfig.defaults;../../../config/ci/rev1_3.defaults" build`。
它选择旧版 P4 芯片和 200 MHz PSRAM。由 PR #191 发布的 BSP Registry 版本 `1.0.1` 会让
ESP-IDF 为每个配置选择匹配的 MIPI PHY 参考时钟。7 个 BSP manifest 均使用精确在线版本
`==1.0.1`，因此完整源码影响运行会验证当前托管依赖。这些构建仍只属于编译证据，不能代替
实板屏幕时序或触摸验证。

- 示例 06 在两个 ESP-IDF 版本下各有 1 个 ES7210 至 ES8311 回声任务，共 2 个；
- 示例 07 至 12 在两个 ESP-IDF 版本下的 12 个 RGB888 任务；
- 示例 11 仅在 ESP-IDF `v5.5.5` 下有 1 个 Brookesia AI 启用任务；
- 示例 12 关闭 HID 触摸与 UAC 音频的 2 个 USB 最小配置任务。

因此完整矩阵共有 41 个 ESP-IDF 构建任务。音频回声覆盖配置会在两个受支持的 ESP-IDF
版本线上编译板载 ES7210 麦克风与 ES8311 扬声器路径。Brookesia AI 覆盖配置仅在 `v5.5.5`
上编译可选 AI 依赖路径：GMF 0.6.x AI 组件在其 CMake 文件顶层调用 `idf_build_set_property`，
ESP-IDF v6.0 在早期的 `component_get_requirements` 阶段会拒绝该调用，因此在一致的 GMF 集
升级前该通道保持 v5-only（见[组件说明](COMPONENTS_ZH.md)）。产品默认配置仍关闭 AI，以控制
运行资源占用。
[`config/ci/`](../config/ci/) 中的覆盖配置
会追加在各工程 `sdkconfig.defaults` 之后，只用于编译条件路径，不是出厂固件配置。
USB 最小通道会关闭 UAC 音频；`usb_device_uac` 会下载，但只在启用 UAC 音频时链接。
较旧 IDF 的构建图仍可能编译未链接目标。顶层 `project()` 创建托管组件目标后，`TARGET`
守卫仅为该 UAC 目标私有地定义 TinyUSB 音频；这不会启用产品描述符或应用音频。

全部产品默认配置将 bootloader 日志保持为 `WARN`。这样无需改变现有分区布局，也能让
Rev3.x QIO bootloader 保持在 `0x8000` 分区表之前的 `0x6000` 区域内；应用日志级别不变。

## CI 固件产物

每个成功构建通道之后，Actions 会使用该构建生成的 `flasher_args.json` 打包，并按工程、
ESP-IDF 版本和变体上传一个 ZIP。该包是用于诊断的示例 CI 产物，不是发布版本。它绑定到
PR 头 SHA（或 push SHA），包含校验和及由清单导出的偏移，且仅保留有限时间。受保护的
本地测试流程见 [CI 固件产物](CI_FIRMWARE_ZH.md)。

## 证据边界

工作流通过只能证明所选源码和配置在官方 ESP-IDF CI 容器中完成依赖解析并针对
`esp32p4` 编译成功，不能证明：

- 仓库内的出厂二进制由这些源码重新构建；
- 烧录、启动、外设时序、无线行为或长时间稳定性正常；
- 摄像头、显示、音频、USB、存储和触摸在实物硬件上工作正常；
- 出厂发布打包、烧录偏移或升级兼容性正确。

这些结论需要绑定到精确提交和硬件版本的独立实板或发布证据。

## Arduino 示例

独立的 Arduino 工作流使用 Arduino-ESP32 `3.3.11` 与有效的 P4
`ChipVariant=postv3` FQBN，在 `examples/arduino/examples/` 下每个目录发现一个规范
`.ino` 文件。其内置 P4 库为 `REV_MIN_301`/200 MHz PSRAM，因此该工作流要求 Rev3.1 或更新
版本，不声明 Rev3.0 或 ESP-IDF 的 250 MHz 配置。Pull Request 和推送中的示例局部源码变更
只选择对应示例；仓库内共享显示库或 Arduino 工作流/发现契约变更才选择全部 10 项。仅文档或
仅 ESP-IDF 变更仍运行预检，但不会创建 Arduino 编译任务；无法分类的 Arduino 路径会保守选择
全部 10 项。手动触发可选择单个示例或全部示例。仅 Arduino 源码路径的变更不会选择 ESP-IDF
矩阵。本仓库不声明 CAN 或 485 板载功能。

该工作流只在线安装锁定的 Arduino-ESP32 core。Arduino_GFX `1.6.0`、LVGL `9.3.0`、
完整 LVGL 配置以及本板显示/触摸适配层均保留在 `examples/arduino/libraries/`，每次编译
都通过 `--libraries` 使用这些仓库内源码；CI 不会再用 Library Manager 下载内容替换它们。
