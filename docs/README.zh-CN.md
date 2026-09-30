# 文档导航

[English](README.md)

只需要阅读与当前工作有关的文档。创建第一个项目之前，不必读完所有设计和运维说明。

## 初次使用者

1. 阅读[入门指南](getting-started.zh-CN.md)，完成工具安装、项目创建、编译和测试。
2. 日常开发时参考[项目维护指南](maintenance.zh-CN.md)。
3. 准备打包或部署服务时，再阅读[运维指南](operations.zh-CN.md)。

## 项目负责人

- [兼容性说明](compatibility.zh-CN.md)列出了支持的操作系统和工具版本。
- [迁移指南](migrations.zh-CN.md)说明升级 foundation 版本时需要检查什么。
- [职责与安全规则](foundation-contract.zh-CN.md)说明工具负责哪些文件，应用团队负责哪些
  决定。

## 生产运维人员

- [运维指南](operations.zh-CN.md)包含发布检查、部署、回滚、中断恢复、备份和记录保留。
- [架构说明](architecture.zh-CN.md)简要展示编译、发布和部署之间的关系。

## Foundation 仓库维护者

- [贡献指南](../CONTRIBUTING.md)说明本地检查和 pull request 流程。
- [Python 发布说明](publishing.zh-CN.md)说明 GitHub Release 和 PyPI 发布流程。
- [安全说明](../SECURITY.md)说明如何报告安全问题。

## 简单词汇表

| 名称 | 简单解释 |
| --- | --- |
| Manifest | 项目设置文件 `foundation.toml` |
| Lockfile | 编译时使用的第三方依赖准确版本 |
| Workflow | GitHub Actions 自动任务 |
| Hook | 应用提供的命令，例如健康检查命令 |
| Evidence | 保存检查执行结果的 JSON 文件或归档 |
| SBOM | 发布包包含的软件清单 |
