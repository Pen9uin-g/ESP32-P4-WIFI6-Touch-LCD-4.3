# 贡献指南

[English](CONTRIBUTING.md)

感谢改进 ESP32-P4-WIFI6-Touch-LCD-4.3 仓库。请将修改限定在本产品范围内，并保持
产品示例、本地组件、托管依赖与仓库内出厂镜像之间的边界。

## 提交 Pull Request 前

1. 从当前 `main` 分支开始，避免混入无关修改。
2. 明确受影响的示例、硬件版本、ESP-IDF 版本及所需配件。
3. 同步更新第一方英文与简体中文文档。
4. 环境中有 Python 时运行无外部依赖的检查：

   ```console
   python .github/tests/run_tests.py
   python .github/scripts/check_repository.py
   ```

5. 以 GitHub Actions 对已提交 PR 头提交的结果作为 ESP-IDF 编译依据。

## 仓库边界

- `examples/esp-idf/` 的直接子目录是产品示例；内嵌组件中的嵌套工程不是独立产品交付物。
- 不要提交生成的 `build/`、`managed_components/`、`sdkconfig` 或依赖解析输出。
- 不能仅因 manifest 引用了名称相似的注册表组件就删除本地 BSP 或应用组件；请遵守
  [组件与依赖边界](docs/COMPONENTS_ZH.md)中的等价性规则。
- 如果没有可复现源码来源、Flash 布局与偏移说明、校验和及发布负责人批准，不要替换、
  重新打包或更改出厂二进制的标签。
- 不要在提交或 Issue 中包含凭据、私有 URL、本地文件路径、设备标识或私密串口日志。

## Pull Request 证据

请说明修改内容、为何适用于本产品、哪个 Actions 运行验证了最终提交，以及哪些内容仍需
实板测试。不能把编译矩阵通过描述为烧录或硬件运行行为已经得到证明。

请使用仓库 Pull Request 模板；如果 Actions 暴露版本特定 API 或依赖问题，应采用范围
最小的修复。
