# 维护生成的项目

[English](maintenance.md)

本指南面向使用 `cpp-foundation init` 创建项目后，负责日常维护的开发者。内容包括普通
代码修改、依赖更新和 foundation 升级。生产部署请单独阅读[运维指南](operations.zh-CN.md)。

## 每次提交 pull request 前

可以使用下面这份简短清单：

1. 为修改的行为增加或更新测试；
2. 编译受影响的目标并运行 `ctest`；
3. 运行快速源码检查；
4. 如果修改了编译、发布或运维设置，检查 manifest；
5. 推送前查看 `git diff`。

```bash
cmake --build build/release --parallel
ctest --test-dir build/release --output-on-failure
cpp-foundation quality --root . --mode fast
cpp-foundation validate
git diff --check
```

修改 CMake、Docker、文档或公共质量设置时，再运行完整检查：

```bash
cpp-foundation quality --root . --mode deep
```

不要仅仅因为检查失败就降低覆盖率、性能或告警限制。应先理解失败原因。如果确实需要
修改限制，请在 pull request 中写明理由。

## 修改 C++ 依赖

依赖名称和期望版本写在 `conanfile.py` 中；`conan/locks/` 下的 lockfile 记录编译实际
使用的准确版本和修订号。

有意修改依赖时：

1. 编辑 `conanfile.py`；
2. 使用受支持的 profile 生成新 lockfile；
3. 使用该 lockfile 安装依赖，然后完整编译和测试；
4. 同时提交 `conanfile.py` 和 lockfile。

GCC profile 示例：

```bash
export CC=gcc-13
export CXX=g++-13
conan lock create . \
  --profile:host conan/profiles/linux-gcc-x64 \
  --profile:build conan/profiles/linux-gcc-x64 \
  --lockfile-out conan/locks/linux-gcc-x64-release.lock
conan install . \
  --profile:host conan/profiles/linux-gcc-x64 \
  --profile:build conan/profiles/linux-gcc-x64 \
  --lockfile conan/locks/linux-gcc-x64-release.lock \
  --output-folder=build/conan \
  --build=missing
```

不要为了让依赖错误消失而删除 lockfile。否则后续编译可能在没有审核的情况下选择不同
依赖。

## 修改 `foundation.toml`

Manifest 把项目自己的名称和命令交给通用工具使用。修改后运行：

```bash
cpp-foundation validate
cpp-foundation doctor --root .
```

主要部分如下：

| 部分 | 控制内容 |
| --- | --- |
| `[project]` | 项目名称和发布版本 |
| `[build]` | CMake 目标、Conan profile 和 lockfile |
| `[release]` | 放入发布包的程序和额外文件 |
| `[operations]` | 启动、检查和停止服务的命令 |
| `[observability]` | 可选检查使用的健康和指标 URL |

不要把密码、token 或私钥放进该文件。运维命令应在运行时从主机的密钥存储或环境中读取
凭据。

## 更新项目版本

版本号会出现在 `foundation.toml`、`CMakeLists.txt` 和 `conanfile.py` 中。应在同一个
pull request 中同时更新三个位置。`doctor` 和发布任务可以发现许多不一致问题，但一次
审核完整变更会更容易理解。

使用 `1.4.2` 这样的常规版本号：

- 兼容修复增加最后一位；
- 兼容的新功能增加中间一位；
- 项目达到 `1.0.0` 后，不兼容修改增加第一位。

## 升级 cpp-project-foundation

升级应使用独立 pull request。不要直接在现有项目目录上重新生成模板。

1. 阅读对应版本的[迁移说明](migrations.zh-CN.md)；
2. 使用 `pipx install --force` 安装目标 CLI 版本；
3. 在现有项目运行 `doctor` 和 `template-diff`；
4. 使用相同项目名和应用版本生成一个临时项目；
5. 只复制经过审核、确实需要采用的 foundation 变更；
6. 把所有 workflow 引用修改为同一个 foundation tag；
7. 合并前运行快速检查、完整检查和常规编译。

```bash
target_version="0.7.0"
pipx install --force "cpp-project-foundation==$target_version"
cpp-foundation doctor --root .
cpp-foundation template-diff --root .
cpp-foundation init \
  --name order-service \
  --version 0.1.0 \
  --output /tmp/order-service-new-template
```

`template-diff` 只读取文件。它会报告差异，但不代表可以覆盖业务代码、依赖选择或项目
自己的限制。

## 保持 GitHub Actions 正常工作

- 所有 foundation workflow 应使用同一个版本，例如 `v0.6.0`；
- 第三方 Action 应继续固定到模板提供的完整提交值；
- 像普通代码变更一样审核 Dependabot pull request，不要一次性合并所有更新；
- 重新运行失败任务前先调查原因，连续重试可能掩盖不稳定测试；
- 只有可选的八小时检查需要稳定的 self-hosted runner，普通检查使用 GitHub 提供的
  Ubuntu runner。

## 需要特别小心的文件

- 不要手工修改 `build/` 下的编译输出；
- 不要提交 `.venv/`、`.conan2/`、`.tools/`、`runtime/` 或任何密钥；
- 不要把应用数据或备份放在发布目录中；
- 不要替换已有 release tag 或已经发布的软件包版本，应发布一个新版本。

## 检查失败时怎样处理

先在本机使用最小命令重现问题。阅读第一条有实际意义的错误，不要只看最后的汇总。
下面这些诊断命令通常有帮助：

```bash
cpp-foundation doctor --root . --strict-tools
ctest --test-dir build/release --output-on-failure
cpp-foundation quality --root . --mode fast
git status --short
```

如果问题来自本工具而不是业务代码，报告问题时请提供 CLI 版本、操作系统、失败命令和
经过脱敏的简短错误。不要附带凭据或生产环境隐私信息。
