# 在板载 LCD 上播放 MP4/AVI

[English](README.md)

本示例从板载 MicroSD 卡读取媒体文件，在 ESP32-P4 上解码，将视频显示到 4.3 英寸
480 × 800 MIPI-DSI LCD，并在音频设备可用时通过板载编解码器输出声音。本示例不使用
HDMI 转接板。

## 支持的媒体路径

- 已注册 MP4 和 AVI 容器解析器。
- 当前支持的图像编码为 MJPEG；兼容性检查会拒绝 H.264 及其他图像编码。
- 默认注册 AAC 和 MP3 音频解码器。
- 可在 `menuconfig` 中启用 FLAC、Opus、Vorbis 和 ADPCM 解码器。
- 如果音频设备初始化失败，应用仍会继续播放视频。

默认媒体路径为 `/sdcard/test_video.mp4`，播放结束后会重新开始。媒体尺寸和吞吐量
应适合屏幕及可用 PSRAM 带宽，实际播放稳定性仍需在开发板上验证。

## 准备 MicroSD 卡

1. 将存储卡格式化为 ESP-IDF FAT 文件系统组件支持的格式。
2. 将 MJPEG 视频复制到存储卡。
3. 将文件命名为 `test_video.mp4`，或在 `MP4/AVI Player Configuration` 菜单的
   `Video File Name` 中修改文件名。
4. 启动应用前插入存储卡。

## 构建、烧录与监视

在已激活 ESP-IDF 环境的本目录执行：

```console
idf.py set-target esp32p4
idf.py -p PORT flash monitor
```

请将 `PORT` 替换为开发板的 USB 转 UART 串口，按 `Ctrl-]` 退出监视器。仓库
Actions 会使用 ESP-IDF `v5.5.4` 和 `v6.0.2` 编译本示例，并覆盖 BSP 的 RGB565
与 RGB888 路径。CI 不会验证媒体兼容性、持续吞吐量、音质或硬件播放效果。
