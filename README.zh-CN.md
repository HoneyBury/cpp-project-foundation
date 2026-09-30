# C++ Project Foundation

[English](https://github.com/HoneyBury/cpp-project-foundation/blob/main/README.md)

用一条命令创建一个可以直接编译的 C++ 服务项目。生成的项目自带示例代码、测试、
CMake 和 Conan 配置、GitHub Actions、发布打包，以及可选的部署工具。

它是一个项目模板和命令行工具，不是应用框架。它不会替你决定业务逻辑、数据库，
也不会在没有明确命令的情况下自动部署。

## 它适合什么项目？

如果你希望获得下面这些能力，可以使用它：

- 新建一个 C++20 服务，并让本机和 GitHub Actions 使用相同的构建方式；
- 从项目开始就准备好测试、代码格式和常用安全检查；
- 生成带校验文件和软件清单的发布包；
- 按需使用部署、回滚、备份和运维记录命令。

正式支持的生产环境是 Ubuntu 24.04 x86-64 和 GCC 13。其他系统可以用来阅读或生成
项目，但生产构建建议使用受支持的环境。

## 五分钟开始使用

生成项目需要 Python 3.11 或更高版本以及
[`pipx`](https://pipx.pypa.io/stable/)。编译项目还需要 GCC 13、CMake、Ninja 和 Conan。
[入门指南](https://github.com/HoneyBury/cpp-project-foundation/blob/main/docs/getting-started.zh-CN.md)提供了完整的安装命令。

从 PyPI 安装工具：

```bash
pipx install "cpp-project-foundation==0.7.0"
cpp-foundation --help
```

创建项目。输出目录不能已经存在：

```bash
cpp-foundation init \
  --name order-service \
  --version 0.1.0 \
  --license MIT \
  --output ../order-service
cd ../order-service
```

检查生成结果：

```bash
cpp-foundation validate
cpp-foundation doctor --root .
```

`validate` 检查 `foundation.toml` 是否正确；`doctor` 会说明哪些文件和工具已经准备好，
哪些可选工具还未安装。此时看到“服务尚未编译”的警告是正常的。

接下来请按照[编译并运行第一个项目](https://github.com/HoneyBury/cpp-project-foundation/blob/main/docs/getting-started.zh-CN.md#6-编译并运行)操作。

## 生成了哪些内容？

| 路径 | 用途 |
| --- | --- |
| `src/`、`include/` | 示例应用代码，可以逐步替换为自己的代码 |
| `tests/` | 示例测试，以及后续测试代码的位置 |
| `CMakeLists.txt`、`CMakePresets.json` | 编译目标和简短、可重复的命令 |
| `conanfile.py`、`conan/` | 第三方依赖及其固定版本 |
| `foundation.toml` | 项目名、编译目标、发布文件和运维命令 |
| `.github/workflows/` | 自动编译、测试、安全检查和发布任务 |
| `deploy/` | 可选的 Docker Compose 和 systemd 示例 |
| `quality/` | 检查使用的时间、文件大小和覆盖率限制 |
| `LICENSE`、`SECURITY.md` | 选择的许可证和私下报告安全问题的方法 |

生成目录属于你的项目，可以正常修改。工具不会悄悄覆盖业务代码，也不会因为检查失败
而自动降低标准。

## 最常用的命令

以下命令应在生成的项目目录中运行：

| 命令 | 使用时机 |
| --- | --- |
| `cpp-foundation validate` | 修改 `foundation.toml` 后 |
| `cpp-foundation doctor --root .` | 配置新电脑或排查项目问题时 |
| `cpp-foundation quality --root . --mode fast` | 每次提交 pull request 前 |
| `cpp-foundation template-diff --root .` | 升级 foundation 版本前 |
| `cpp-foundation package --output-dir dist` | Release 编译成功后 |
| `cpp-foundation verify-release ...` | 安装或发布归档前 |

质量工具需要先安装一次；部署和备份命令也需要提前准备。请按照对应指南操作，不建议只
复制其中一条命令：

- [第一个项目：安装、编译、测试和运行](https://github.com/HoneyBury/cpp-project-foundation/blob/main/docs/getting-started.zh-CN.md)
- [维护生成的项目](https://github.com/HoneyBury/cpp-project-foundation/blob/main/docs/maintenance.zh-CN.md)
- [发布、部署、故障恢复和备份](https://github.com/HoneyBury/cpp-project-foundation/blob/main/docs/operations.zh-CN.md)

## 文档中的几个常用词

- **Manifest（项目清单）：** 指 `foundation.toml`，它告诉工具怎样处理当前项目。
- **Lockfile（依赖锁定文件）：** 记录第三方库的准确版本，让以后使用相同输入编译。
- **Workflow（自动任务）：** GitHub Actions 中自动运行的任务。
- **Evidence（执行记录）：** 保存检查实际结果的 JSON 文件或归档。
- **SBOM（软件清单）：** 发布包内文件和第三方软件的列表。

## 文档入口

[文档导航](https://github.com/HoneyBury/cpp-project-foundation/blob/main/docs/README.zh-CN.md)按照不同读者整理了内容：

- 初次使用者；
- 维护生成项目的开发者；
- 生产环境运维人员；
- 维护本 foundation 仓库的贡献者。

版本支持范围和升级方法请阅读[兼容性说明](https://github.com/HoneyBury/cpp-project-foundation/blob/main/docs/compatibility.zh-CN.md)与
[迁移指南](https://github.com/HoneyBury/cpp-project-foundation/blob/main/docs/migrations.zh-CN.md)。

## 使用前需要知道的限制

- 生成的监控和部署文件是参考示例。用于生产前，必须检查主机名、存储、凭据和权限。
- 应用数据、凭据和备份不能放在发布目录中。
- 通过已有检查不等于已经证明系统具备高可用、足够容量或灾难恢复能力。
- 八小时长时间检查需要稳定的 self-hosted GitHub Actions runner；短时间检查默认使用
  GitHub 提供的 runner。

报告安全问题请阅读 [SECURITY.md](https://github.com/HoneyBury/cpp-project-foundation/blob/main/SECURITY.md)。修改本仓库请阅读
[CONTRIBUTING.md](https://github.com/HoneyBury/cpp-project-foundation/blob/main/CONTRIBUTING.md)。
