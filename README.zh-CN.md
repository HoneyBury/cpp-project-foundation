# C++ Project Foundation

[English](README.md) | [简体中文](README.zh-CN.md)

`cpp-project-foundation` 是一个由清单驱动的 C++ 服务工程基础设施。它将构建、
依赖、安全、发布、部署和运维契约抽取为可复用能力，同时不引入任何具体产品的
服务拓扑。

首个受支持的生产配置有意保持较窄的范围：

- Ubuntu 24.04 x86-64
- GCC 13、C++20、CMake、Ninja 和 sccache
- Conan 2.8.1，以及由项目维护的 profile 和 lockfile
- 每个生成项目包含一个可独立部署的服务
- 默认使用 GitHub-hosted Actions runner，长时间门禁可按需配置 self-hosted runner

多服务编排、应用协议、数据库、SDK 生成和云平台策略属于扩展点，不是 foundation
核心中的隐藏假设。

## 创建项目

克隆本仓库，然后通过持续维护的参考模板生成服务：

```bash
python3 -m venv .venv/foundation
.venv/foundation/bin/pip install -e .
.venv/foundation/bin/cpp-foundation init \
  --name order-service \
  --version 0.1.0 \
  --output ../order-service
```

生成的项目独立维护自己的 `foundation.toml`、Conan 依赖图和 lockfile。启用可复用
CI workflow 前，应审查 manifest，并针对已批准的依赖图重新生成 lockfile。

## Manifest

`foundation.toml` 是通用平台与应用代码之间的边界。它声明构建目标、发布输入和
失败即关闭的运维 hook。工具不会猜测服务名称，也不会在观察到失败后自动修改阈值。

```toml
schema_version = 1

[project]
name = "order-service"
version = "0.1.0"

[build]
target = "order_service"
test_target = "order_service_tests"
profile = "conan/profiles/linux-gcc-x64"
lockfile = "conan/locks/linux-gcc-x64-release.lock"

[release]
executables = ["build/release/bin/order-service"]
include = ["deploy"]

[operations]
activate = ["docker", "compose", "-f", "deploy/docker-compose.yml", "up", "-d"]
verify = ["sh", "deploy/verify.sh"]
deactivate = ["docker", "compose", "-f", "deploy/docker-compose.yml", "down"]
canary = ["bin/order-service", "--check"]
benchmark = ["bin/order-service", "--benchmark", "200000"]
```

## 能力等级

### P0：工程与供应链基线

- 隔离的 Conan 2.8.1、显式 remote、profile 和不可变依赖图 lockfile
- CMake/Ninja/CTest 和 sccache
- 可复用的 GitHub CI
- OSV、ASan/UBSan、TSan 和有界 libFuzzer 任务
- 完整 SHA 固定的 Action、最小权限 token、CODEOWNERS 和分支保护初始化脚本
- foundation 自身的可复用 workflow 使用不可变语义版本 tag，消费者显式升级平台；
  所有第三方 Action 固定到完整 SHA
- 候选提交、runner、构建配置和 lockfile provenance

### P1：不可变发布与部署

- 安全的运行时归档、SHA-256、SPDX 2.3 SBOM 和候选 provenance
- GitHub artifact attestation 和不可变 tag 发布
- 归档路径穿越防护和摘要校验
- 幂等安装、串行化部署操作、升级、回滚、状态和验证
- 失败候选清理和自动恢复上一部署
- 仅包含运行时的 Dockerfile、加固的 Compose、systemd 和 Prometheus/Grafana 参考配置

### P2：运维证据

- 只创建不覆盖的证据记录，以及内容寻址的原始摘要
- 用于异地主机保留的证据包校验
- 默认使用 age 加密的备份创建、校验和隔离恢复
- 由应用定义的外部 canary 和固定窗口聚合
- 有界 smoke、2h 和 8h soak profile
- 使用显式吞吐与 P99 阈值的重复性能门禁

## 常用命令

```bash
cpp-foundation --manifest foundation.toml validate
cpp-foundation --manifest foundation.toml package --output-dir dist
cpp-foundation verify-release --archive dist/project-v0.1.0-linux-x64.tar.gz \
  --checksum dist/project-v0.1.0-linux-x64.tar.gz.sha256

sudo cpp-foundation deploy --root /opt/project --state-root /var/lib/project \
  install --archive /tmp/project-v0.1.0-linux-x64.tar.gz \
  --checksum /tmp/project-v0.1.0-linux-x64.tar.gz.sha256
sudo cpp-foundation deploy --root /opt/project --state-root /var/lib/project \
  activate --deployment-id <deployment-id>
```

长时间运维门禁默认不启用。普通 pull request 只运行两秒的有界稳定性 smoke。
所有生成的 workflow 默认使用 GitHub-hosted `ubuntu-24.04` runner，2h profile 也可
使用该默认值。启用 `overnight-8h` 前，消费项目必须显式配置已授权的 self-hosted
runner，因为 GitHub-hosted 任务的执行时间上限更短。

## 生产边界

- 模板无法配置 GitHub 分支规则、runner group、environment 或 secret。首次提交到
  `main` 后，使用 `scripts/bootstrap_github.py --apply` 完成仓库侧配置。
- 消费项目通过不可变发布 tag `HoneyBury/cpp-project-foundation@v0.1.1` 引用公开的
  可复用 workflow。
- 公开仓库自动运行 GitHub-hosted attestation。私有消费项目仍会发布 SHA-256、
  provenance JSON 和 SPDX；受支持的企业仓库可以显式启用原生 attestation。
- Conan profile 可以共享，但每个消费项目必须维护自己的依赖图 lockfile。
- 备份归档默认必须配置 age recipient。明文模式仅供测试使用。
- 本地证据包会报告 `off_host_copy_verified=false`；必须由另一台主机校验并记录传输。
- foundation smoke 通过不代表已经满足可用性、容量或高可用目标。

进一步阅读：[foundation-contract.md](docs/foundation-contract.md)、
[architecture.md](docs/architecture.md) 和 [operations.md](docs/operations.md)。
