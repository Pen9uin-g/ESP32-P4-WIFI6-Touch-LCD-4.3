# ESP-Brookesia Phone 示例

[English](README.md)

本示例在 ESP32-P4-WIFI6-Touch-LCD-4.3 上运行 ESP-Brookesia Phone 风格的系统
界面及本地注册的 Squareline 应用。应用会启动板级显示和触摸栈、从 Brookesia 注册表
安装应用，并刷新状态栏时钟。

所需的 `brookesia_core` 与 `brookesia_app_squareline_demo` 源码已包含在 `components/`
目录中；构建本示例不需要另行克隆 ESP-Brookesia 仓库。

## 默认配置

仓库内的 `sdkconfig.defaults` 已选择 ESP32-P4、32 MB QIO Flash、200 MHz PSRAM
和三个显示缓冲。为控制默认资源占用，配置会关闭 Brookesia AI 框架、动画播放器、
服务、扬声器系统及未使用的 Boost 库。Actions 还会在 ESP-IDF `v5.5.5` 与 `v6.0.2`
下分别编译启用 AI 的配置，避免其条件依赖路径在任一受支持版本线上静默回归。

本仓库中的 ESP-Brookesia 属于预览集成。Actions 会验证代码可在 ESP-IDF
`v5.5.5` 与 `v6.0.2` 下编译；界面布局、触摸行为、性能及可选服务仍需在
480 × 800 目标开发板上测试。

## 构建、烧录与监视

在已激活 ESP-IDF 环境的本目录执行：

```console
idf.py set-target esp32p4
idf.py -p PORT flash monitor
```

请将 `PORT` 替换为开发板的 USB 转 UART 串口，按 `Ctrl-]` 退出监视器。如需启用
Brookesia 可选子系统，请在构建前使用 `idf.py menuconfig`；这些功能可能增加托管组件
依赖及 Flash、PSRAM 和任务资源占用。

与本产品适配有关的问题请提交到本仓库的
[Issue 列表](https://github.com/waveshareteam/ESP32-P4-WIFI6-Touch-LCD-4.3/issues)。
