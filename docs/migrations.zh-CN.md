# 迁移指南

[English](migrations.md)

消费项目升级必须通过 pull request 完成，不能在受保护的默认分支上直接批量替换
workflow tag。

## 升级流程

1. 在隔离环境安装目标 foundation tag。
2. 运行 `cpp-foundation doctor --root .`，记录确认可接受的告警。
3. 运行 `cpp-foundation template-diff --root .`，识别 foundation 管理文件的漂移。
4. 使用相同项目名和版本生成临时项目，选择性应用已审核的变更；不要覆盖应用文件或
   Conan lockfile。
5. 将所有 foundation workflow 引用统一修改为同一个目标 tag。
6. 运行快速 CI 与质量门禁、深度质量、安全和 operations smoke。
7. 通过分支保护合并，并在下一个生产 tag 前执行 release dry-run。

## 0.2.1 升级至 0.2.2

- 可复用任务现在为安装与构建步骤一致设置 `CONAN_HOME`。
- 质量 workflow 将 Clang 分析 profile 与 GCC 覆盖率 profile 分离。
- 如果尚未配置，应在质量 workflow 中增加
  `coverage-profile: conan/profiles/linux-gcc-x64`。

## 0.2.2 升级至 0.2.3

- 即使本机未安装 `cmake-format`，生成的 CMake 格式也保持确定性。
- 生成临时项目并一次性采用规范化的多行 CMake 命令；该变更只涉及源码格式，不应
  改变 target 或构建行为。

## 0.2.3 升级至 0.3.0

- 安装新版 CLI，并在修改 workflow 引用前运行 `doctor`。
- 使用 `template-diff` 审查生成的质量资产漂移。非零结果只是变更清单，
  不代表可以覆盖消费项目拥有的文件。
- 对单维护者公开仓库，`bootstrap_github.py` 默认要求零审批；团队仓库应显式传入
  `--required-approvals 1` 或更高值。
- `--required-check` 可以重复传入，应使用 GitHub 报告的精确检查名称。
- Ubuntu Docker major 自动更新会被忽略；平台升级必须重新提供兼容性证据。

0.3.0 不包含 manifest schema 迁移，当前仍使用 `schema_version = 1`。
