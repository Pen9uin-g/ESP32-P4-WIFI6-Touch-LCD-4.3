# CI 固件产物

[English](CI_FIRMWARE.md) · [CI 指南](CI_ZH.md)

ESP-IDF 工作流会为全部 39 个矩阵通道各生成一个临时、可烧录的诊断包。它使用该通道实际
生成的 `flasher_args.json`；绝不替代 [`firmware/`](../firmware/) 中不可变的出厂镜像。

## 前提和选择

请使用干净、非 detached 的本地分支，并确保恰有一个已打开、非草稿的 Pull Request，且其
头提交与完整本地 SHA 一致。工具只接受该精确 SHA 上成功的 `esp-idf-examples.yml` 运行，
并且只下载所选通道的精确产物名称。它会验证 ZIP 仅含一个清单，确认身份字段、校验和、
文件大小和偏移与所选通道一致、范围不重叠且全部位于 32 MiB 内。

在 Windows 上运行：

```text
Flash-CI-Firmware.cmd -Port COMx
```

`-ListOnly` 会列出全部 39 个通道，不访问 GitHub 或硬件。`-SelfTest` 只运行本地安全
检查。若不提供 `-Port`，仅当恰有一个即插即用显示名称同时包含 `CH343` 与 `COM` 时工具
才会自动填写；否则请明确传入 `-Port COMx`。

## 引导式实板测试

工具使用 `esp32p4`、921600 波特率和清单导出的写入参数。只有 esptool 成功退出且输出
`Hash of data verified` 时，通道才视为已烧录。随后必须在实际测试开发板后显式确认手工
PASS，才可进入下一个通道。进度按最终 SHA 保存，因此新的 SHA 会开始新的测试序列。

不得使用此流程烧录、替换、推断偏移或验证仓库中的出厂/恢复固件。出厂固件有独立的
所有权、发布证据和恢复说明。
