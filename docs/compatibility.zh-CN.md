# 兼容性与支持策略

[English](compatibility.md)

## 支持基线

以下组合会被持续验证，也是 0.3 发布线唯一支持的生产基线：

| 层级 | 支持基线 |
| --- | --- |
| 主机与发布资产 | Ubuntu 24.04、Linux x86-64 |
| 语言 | C++20 |
| 构建 | CMake 3.21 或更高版本、Ninja |
| 编译器 | GCC 13；Clang 18 兼容构建与分析 |
| 依赖 | Conan 2.8.1，由项目维护 profile 和 lockfile |
| 自动化 | GitHub-hosted `ubuntu-24.04` runner |
| Python CLI | CPython 3.11 或更高版本 |

其他平台和版本均属于扩展 profile，需要提供原生构建、性能和运维证据，不能直接继承
此矩阵的支持结论。特别是 macOS 可用于开发与编排，但不能产出受支持的 Linux 发布资产。

## 所有权边界

| Foundation 负责 | 消费项目负责 |
| --- | --- |
| 可复用 workflow 契约与固定版本的 Actions | 项目选择的 workflow tag |
| 默认编译、质量和安全策略 | 应用源码、行为和测试 |
| 生成的质量配置和 Conan profile | Conan 依赖图和 lockfile |
| 归档、provenance、SBOM 和部署格式 | 发布版本与上线审批 |
| 事务、备份和证据机制 | 健康、canary、benchmark 和备份 hook |
| 参考 Compose、systemd 和监控资产 | 生产凭据、主机和 SLO |

`cpp-foundation template-diff` 只比较 foundation 管理的生成文件，不会改写应用源码、
manifest、依赖 lockfile、部署策略或性能预算。

## 版本与支持生命周期

- 发布 tag 不可变，消费项目固定到明确的语义版本。
- 在 `0.x` 阶段，minor 版本可以改变生成或可复用契约，但必须提供迁移记录；patch
  版本只包含向后兼容修复。
- 最新 minor 接收修复；旧 minor 仍可下载，但不单独维护安全或修复分支。
- 除非旧行为会保留已知安全或完整性问题，否则弃用能力至少提前一个 minor 记录。
- Ubuntu 发布线变更必须作为显式兼容性工作审核，自动 Docker 更新会保持在受支持的
  24.04 minor 线内。

消费项目变更固定 tag 前，应依次执行 `doctor`、`template-diff`、项目必需的 PR 门禁，
并至少运行一次 operations smoke profile。
