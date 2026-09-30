# 迁移指南

[English](migrations.md)

本页只适用于已经使用旧 foundation 版本的项目。新项目可以跳过。升级应使用独立的
pull request，方便审核和撤销模板变化。

## 升级流程

1. 阅读当前版本到目标版本之间的所有说明；
2. 使用 `pipx install --force` 安装目标 CLI 版本；
3. 运行 `doctor` 和 `template-diff`，这两个命令在修改文件前可以安全执行；
4. 使用相同项目名和应用版本生成临时项目；
5. 比较临时项目和真实项目，只复制已审核的变化，不要覆盖应用代码或 Conan lockfile；
6. 把所有 foundation workflow 引用改为同一个目标 tag；
7. 运行常规编译、快速检查、完整检查和 operations smoke；
8. 按项目正常审核流程合并，然后运行 release dry-run。

完整过程和示例命令请参考
[维护生成的项目](maintenance.zh-CN.md#升级-cpp-project-foundation)。

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

## 0.5.0 升级至 0.6.0

- Manifest 与 evidence schema 版本仍为 1，无需重写已有数据。
- 在主机 runbook 中加入 `deploy recover`。中断后遗留的 `started` 事务会阻止激活、
  升级和回滚，直到恢复命令还原事务前的发布版本。
- Evidence 打包现在只接受记录中引用的文件。应删除 evidence 根目录中的无关文件和
  链接；发现损坏的内容寻址文件时应调查原因，不能直接覆盖。
- Release manifest 新增稳定的运行时内容摘要。如果编译任务信息或软件清单创建时间
  不同，完整归档的字节仍可能不同。
- `doctor --probe-observability` 会按需对已配置的 health 和 metrics URL 执行 HTTP 探测；
  默认 `doctor` 仍不访问网络。
- 将所有可复用 workflow 引用更新为 `v0.6.0`，然后运行完整 PR 门禁和 operations
  smoke profile。

## 0.6.0 升级至 0.7.0

- Manifest schema 仍为 1。项目版本现在按照完整的 Semantic Versioning 规则检查，转换后
  会成为 C++ 关键字的项目名会被拒绝。已有的有效项目不需要重写 manifest。
- 从临时生成的 0.7.0 项目中审阅并加入 `CMakePresets.json`、`CONTRIBUTING.md`、
  `SECURITY.md`、CODEOWNERS 起始文件、pull request 模板和
  `scripts/bootstrap_github.py`。
- 为生成项目的 `ci.yml` 和 `quality.yml` 增加 `main` 分支的 `push` 触发。GitHub 报告
  准确的检查名称后，再单独配置分支保护。
- 审阅并采用真正访问运行服务的 `--healthcheck` 以及 Docker Compose health check。
  `--check` 保留为只检查程序本身的 smoke check，`--healthcheck` 用于检查运行中的服务。
- `template-diff` 现在会报告 workflow、部署文件和项目治理文件的变化。报告的变化可能
  是项目有意做出的修改，应人工检查，不能直接覆盖。
- 选择并审核项目许可证；已有项目不会被自动重新授权。
- 将所有可复用 workflow 引用更新为 `v0.7.0`，然后运行完整 PR 门禁、生成项目编译和
  operations smoke profile。
