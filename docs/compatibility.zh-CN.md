# 支持的版本

[English](compatibility.md)

本页回答两个问题：哪些环境会被持续测试，以及生成项目的各部分由谁负责。

## 持续测试的环境

0.6 发布线支持下面的生产环境：

| 部分 | 支持版本 |
| --- | --- |
| 主机和发布文件 | Ubuntu 24.04、Linux x86-64 |
| C++ | C++20 |
| 编译工具 | CMake 3.21 或更高版本、Ninja |
| 编译器 | GCC 13；Clang 18 用于额外检查 |
| C++ 依赖 | Conan 2.8.1，并由项目维护 lockfile |
| GitHub Actions | GitHub 提供的 `ubuntu-24.04` runner |
| 命令行工具 | Python 3.11 或更高版本 |

其他版本可能也能工作，但本仓库不会持续测试。生产环境如果要使用其他编译器、操作系统
或处理器，应先在真实平台完成编译、测试、性能检查和部署演练。

macOS 适合编辑代码和执行部分命令，但不能生成本项目正式支持的 Linux 生产发布包。

## 各部分由谁负责？

| Foundation 工具提供 | 项目团队决定并维护 |
| --- | --- |
| 可复用的 GitHub Actions 任务 | 项目使用哪个 foundation 版本 |
| 默认编译器和源码检查 | 应用代码、行为和测试 |
| 初始质量设置和 Conan profile | 第三方依赖和 lockfile |
| 发布和部署文件格式 | 应用版本和发布审批 |
| 事务、备份和 evidence 命令 | 健康、性能和备份命令 |
| Docker、systemd 和监控示例 | 生产主机、凭据和目标 |

`cpp-foundation template-diff` 只报告 foundation 提供的初始文件有哪些差异，不会覆盖
应用代码、`foundation.toml`、lockfile 或项目自己的限制。

## 版本规则

- 每个发布都有不可修改的版本 tag，项目应使用准确 tag；
- 在 `1.0.0` 之前，中间版本号变化可能要求生成项目作出修改，这些修改会写入
  [迁移指南](migrations.zh-CN.md)；
- 只改变最后一位的版本用于兼容修复；
- 最新 minor 版本接收修复，旧版本仍可下载，但不会建立单独维护分支；
- 一项能力通常会提前至少一个 minor 版本说明废弃，再进行删除；不安全行为可能更早
  移除；
- 升级 Ubuntu 发布线属于需要审核的项目变更，不会自动完成。

修改已有项目使用的版本前，请按照
[维护生成的项目](maintenance.zh-CN.md#升级-cpp-project-foundation)操作。
