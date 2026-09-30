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

## 0.3.0 升级至 0.3.1

无需迁移生成文件或 manifest。0.3.1 替换了 0.3.0 中不可移植的 wheel 下载校验文件；
请更新 foundation workflow 和安装 tag。

## 0.3.1 升级至 0.4.0

- 增加生成的 `.github/dependabot.yml`。它跟踪可复用 Actions 和固定的 Python 工具，
  同时将 Docker 更新限制在受支持的 Ubuntu 24.04 发布线。
- Operations job 在现有 JSON 证据之外增加 Markdown summary；无需迁移 manifest 或
  evidence schema。
- PyPI 发布是可选能力，需要先完成 [publishing.zh-CN.md](publishing.zh-CN.md) 中的
  trusted-publisher 外部配置；通过 GitHub tag 安装仍然受支持。

## 0.4.0/0.4.1 升级至 0.5.0

- Manifest schema 仍为 1，但验证改为严格模式。删除未知字段，并确保
  `build.fuzz_targets`、`release.executables`、`release.include` 和运维命令均为
  非空字符串数组。
- `operations.hook_timeout_seconds` 必须为正数；可观测性 URL 必须是绝对 HTTP(S)
  URL，`prometheus_retention_days` 必须为正整数。
- 部署安装现在必须传入 `--checksum`。升级 CLI 前，应独立传输生成的 `.sha256`
  文件并更新主机自动化。
- 发布校验会拒绝未登记文件、重复归档成员和可执行位漂移。请使用 0.5.0 重新构建
  发布包，不要重新封装旧归档。
- 将所有可复用 workflow 引用统一更新为 `v0.5.0`，然后执行 `doctor`、
  `template-diff`、完整 PR 门禁和 operations smoke。
