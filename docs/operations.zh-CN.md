# 发布与运维指南

[English](operations.md)

本指南用于打包和运维生成的服务。所有命令都应先在测试环境演练，再用于生产主机。

示例使用 `example` 作为服务名，请替换成自己项目的名称和路径。修改 `/opt` 或
`/var/lib` 的命令通常需要 `sudo`。

## 第一次发布前

确认以下事项：

- 项目已在 Ubuntu 24.04 x86-64 和 GCC 13 环境中编译，所有测试通过；
- `foundation.toml` 中的程序路径和运维命令正确；
- Git 工作区干净，发布提交已经审核；
- 应用数据、凭据和备份位于发布目录之外；
- 服务的 `verify` 命令会执行有意义的检查，服务不健康时返回非零状态。

工具无法替应用设计有效的健康检查，这项决定由应用团队负责。

## 创建发布包

先编译 Release 程序，再打包：

```bash
cmake --build build/release --parallel
ctest --test-dir build/release --output-on-failure
git status --short
cpp-foundation package --output-dir dist
```

`git status --short` 必须没有输出。如果源码目录还有未提交修改，打包会拒绝执行，因为
此时无法确认文件准确对应哪一个经过审核的提交。

`dist/` 目录包含：

- `.tar.gz` 发布归档；
- `.sha256` 校验文件；
- SPDX 软件清单；
- 记录源码提交和编译环境的 JSON 文件。

发布或复制归档前先验证：

```bash
cpp-foundation verify-release \
  --archive dist/example-v1.0.0-linux-x64.tar.gz \
  --checksum dist/example-v1.0.0-linux-x64.tar.gz.sha256
```

传输时应保留归档和校验文件两个独立文件。验证会同时检查外层归档和内部登记的每个文件。

## 部署目录

部署命令使用两个根目录：

- `--root /opt/example`：保存发布文件和小型部署记录；
- `--state-root /var/lib/example`：保存事务记录和操作锁。

这两个目录不用于保存应用数据。数据库、上传文件、凭据、备份和长期运维记录应放在单独
管理的位置。

## 安装发布包

安装命令会校验并解压归档，但不会启动服务：

```bash
sudo cpp-foundation deploy \
  --root /opt/example \
  --state-root /var/lib/example \
  install \
  --archive /tmp/example-v1.0.0-linux-x64.tar.gz \
  --checksum /tmp/example-v1.0.0-linux-x64.tar.gz.sha256
```

JSON 输出中包含 `deployment_id`，下一条命令需要使用它。使用相同归档重复安装是安全的，
命令会返回已经存在的记录。

## 启动第一个版本

```bash
deployment_id="粘贴安装输出中的部署ID"
sudo cpp-foundation deploy \
  --root /opt/example \
  --state-root /var/lib/example \
  activate \
  --deployment-id "$deployment_id"
```

工具会先运行应用的 `activate` 命令，再运行 `verify` 命令。如果其中任何一步失败，工具
会清理新版本并恢复之前的版本。

检查结果：

```bash
sudo cpp-foundation deploy \
  --root /opt/example \
  --state-root /var/lib/example \
  status
sudo cpp-foundation deploy \
  --root /opt/example \
  --state-root /var/lib/example \
  verify
```

## 升级和回滚

先安装新归档，再使用新的部署 ID：

```bash
new_deployment_id="粘贴新安装输出中的部署ID"
sudo cpp-foundation deploy \
  --root /opt/example \
  --state-root /var/lib/example \
  upgrade \
  --deployment-id "$new_deployment_id"
```

返回上一个已运行版本：

```bash
sudo cpp-foundation deploy \
  --root /opt/example \
  --state-root /var/lib/example \
  rollback
```

回滚只切换运行版本，不会还原应用数据。如果新版本会修改数据，应用团队必须另外准备并
验证数据迁移和回滚方案。

## 恢复中断的部署

断电或进程被终止后，事务可能停留在 `started` 状态。此时 `status` 会报告未完成事务，
后续激活也会被阻止。

先查看状态和
`/var/lib/example/transactions/<transaction-id>/record.json` 中的事务记录，然后运行：

```bash
sudo cpp-foundation deploy \
  --root /opt/example \
  --state-root /var/lib/example \
  recover
```

恢复命令会停止候选版本，还原旧的 `current` 和 `previous` 指向，然后重新启动旧版本。
如果恢复命令失败，事务会继续保持未完成状态。修复报告的主机或应用问题后重试
`recover`，不要通过删除事务记录绕过阻止。

## 检查健康和指标 URL

普通 `doctor` 不会访问网络。确认服务应该已经运行后，可以明确要求检查
`foundation.toml` 中的 URL：

```bash
cpp-foundation doctor --root . \
  --probe-observability \
  --probe-timeout 5
```

应从能代表真实访问路径的电脑执行。只在服务主机检查成功，不代表外部用户一定能访问。

## 创建并验证加密备份

生产备份需要一个 [`age`](https://age-encryption.org/) recipient。请按照组织的密钥管理
流程获取 recipient 和 identity。不要把私有 identity 放进发布目录或 Git 仓库。

创建备份：

```bash
cpp-foundation backup create \
  --source /var/lib/example/data \
  --output /var/backups/example/data-20260930T120000Z.tar.gz.age \
  --age-recipient age1...
```

命令还会在归档旁生成 `.json` 摘要。验证两个文件：

```bash
cpp-foundation backup verify \
  --archive /var/backups/example/data-20260930T120000Z.tar.gz.age \
  --summary /var/backups/example/data-20260930T120000Z.tar.gz.age.json \
  --age-identity /secure/path/backup-identity.txt
```

应把备份复制到独立存储，并定期测试恢复。只保存在服务主机上的备份是不够的。

## 安全测试恢复

恢复到一个与真实数据分开的新目录：

```bash
cpp-foundation backup restore \
  --archive /var/backups/example/data-20260930T120000Z.tar.gz.age \
  --summary /var/backups/example/data-20260930T120000Z.tar.gz.age.json \
  --destination /var/tmp/example-restore-test \
  --age-identity /secure/path/backup-identity.txt
```

目标目录不能已经存在。恢复后还要使用应用自己的方法确认数据确实可以读取。只验证归档
本身，不能证明应用一定理解恢复后的数据。

## 保留运维记录

Canary、稳定性和性能检查会生成 JSON 摘要。把重要摘要写入只新增、不覆盖的 evidence
目录：

```bash
cpp-foundation evidence \
  --root /var/lib/example/evidence \
  record \
  --kind daily \
  --record-id 2026-09-30 \
  --summary runtime/operations/summary.json
cpp-foundation evidence \
  --root /var/lib/example/evidence \
  verify
cpp-foundation evidence \
  --root /var/lib/example/evidence \
  package \
  --output /var/backups/example/evidence-2026-09-30.tar.gz
```

打包输出必须位于 evidence 根目录之外。把归档和校验文件复制到另一台主机或存储系统，
然后在那里再次验证校验值。

## 简单故障处理表

| 情况 | 第一步操作 |
| --- | --- |
| 新版本激活失败 | 查看事务记录；自动回滚应该已经执行 |
| `status` 显示未完成事务 | 查看记录，然后执行 `deploy recover` |
| 当前版本不健康 | 运行 `verify`、查看服务日志，再考虑 `rollback` |
| 备份验证失败 | 保留文件、停止使用该备份，并调查复制过程或密钥 |
| Evidence 验证失败 | 不要覆盖异常文件，应保留并调查原因 |

处理故障时记录命令、时间、部署 ID 和结果。把日志附加到问题记录前，先删除密钥和个人
信息。
