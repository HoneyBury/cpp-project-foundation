# 入门指南

[English](getting-started.md)

本指南从一台新的 Ubuntu 24.04 电脑开始，最后运行生成的示例服务。第一次体验时，
标记为可选的步骤可以暂时跳过。

## 1. 安装基础工具

安装 Python、`pipx`、受支持的编译器、CMake 和 Ninja：

```bash
sudo apt-get update
sudo apt-get install -y \
  python3 python3-venv pipx \
  gcc-13 g++-13 cmake ninja-build git
pipx ensurepath
```

如果 `pipx ensurepath` 提示需要重新打开终端，请按提示操作。检查主要工具版本：

```bash
python3 --version
gcc-13 --version
cmake --version
ninja --version
```

Python 必须是 3.11 或更高版本；正式支持的编译器是 GCC 13。
可选的源码质量工具还需要 Node.js 22 或更高版本以及 npm。

## 2. 安装项目生成工具

```bash
pipx install "cpp-project-foundation==0.7.0"
cpp-foundation --help
```

`pipx` 会把这个 Python 工具与 C++ 项目的依赖分开。如果本机已经安装旧版本，可以执行：

```bash
pipx install --force "cpp-project-foundation==0.7.0"
```

## 3. 创建项目

项目名只能使用小写字母、数字和连字符。输出目录不能已经存在。`--license` 可以选择
`MIT`、`Apache-2.0`、`proprietary` 或 `none`；发布项目前应和团队一起确认生成的
`LICENSE`。

版本可以使用 `1.2.0-rc.1+build.5` 这样的预发布格式。CMake 的 `project(VERSION)` 只
接受数字，因此会使用其中的 `1.2.0`；`foundation.toml`、Conan 信息和发布文件名仍保留
完整版本。

```bash
cpp-foundation init \
  --name order-service \
  --version 0.1.0 \
  --license MIT \
  --output ../order-service
cd ../order-service
```

先运行两个不会修改文件的检查：

```bash
cpp-foundation validate
cpp-foundation doctor --root .
```

此时 `doctor` 可能提示发布程序尚未编译，或者某个可选工具没有安装，这是正常情况。
如果结果中出现 `fail`，应先按提示修复再继续。

## 4. 先认识几个重要文件

开始时只需要了解下面几个文件：

- `src/main.cpp`：示例程序入口；
- `tests/request_parser_test.cpp`：怎样添加测试的示例；
- `CMakeLists.txt`：程序和测试的编译目标；
- `conanfile.py`：项目使用的第三方 C++ 库；
- `foundation.toml`：告诉 `cpp-foundation` 应该使用哪些目标和文件。

其他文件负责自动检查、打包和可选部署。第一次体验时可以暂时不修改。

## 5. 安装 Conan

Conan 用来下载项目需要的 C++ 库。把它的 Python 环境放在项目目录中，后续删除或重建
都比较方便：

```bash
python3 -m venv .venv/conan
.venv/conan/bin/pip install "conan==2.8.1"
.venv/conan/bin/conan remote add \
  conancenter https://center2.conan.io --force
export PATH="$PWD/.venv/conan/bin:$PATH"
```

`export` 只对当前终端有效。重新打开终端后需要再次执行，或者直接使用
`.venv/conan/bin/conan`。

## 6. 编译并运行

让 Conan 按照项目中已经记录的固定版本安装依赖：

```bash
export CC=gcc-13
export CXX=g++-13
conan install . \
  --profile:host conan/profiles/linux-gcc-x64 \
  --profile:build conan/profiles/linux-gcc-x64 \
  --lockfile conan/locks/linux-gcc-x64-release.lock \
  --output-folder=build/conan \
  --build=missing
```

使用项目自带的 CMake preset 配置并编译示例程序和测试：

```bash
cmake --preset release
cmake --build --preset release --target order_service order_service_tests
ctest --preset release
```

运行程序自带的检查：

```bash
build/release/bin/order-service --check
```

实际目标名和文件名来自项目名。例如，`payment-api` 对应 CMake 目标 `payment_api` 和
程序文件 `payment-api`。

## 7. 安装并运行代码检查

建议在第一次提交 pull request 前完成本步骤：

```bash
python3 scripts/install_quality_tools.py \
  --venv .venv/quality \
  --tools-dir .tools
export PATH="$PWD/.venv/quality/bin:$PWD/.tools/bin:$PWD/.tools/npm/node_modules/.bin:$PATH"
cpp-foundation quality --root . --mode fast
```

快速检查会检查源码格式和常见配置错误。修改 CMake、Docker 或文档前后，还可以运行较慢
但更完整的检查：

```bash
cpp-foundation quality --root . --mode deep
```

## 8. 保存到 Git

提交前先检查生成的文件：

```bash
git init
git add .
git status
git commit -m "chore: create order service"
```

把项目推送到 GitHub 后，`.github/workflows/` 中的任务会自动执行主要编译和检查。
模板不会自动创建仓库规则、密钥或生产环境。生成的辅助脚本默认只打印分支保护策略，
不会修改仓库。第一次 pull request 跑出准确的检查名称后，使用仓库名和检查名称审阅策略：

```bash
python3 scripts/bootstrap_github.py \
  --repository your-org/order-service \
  --required-check "GitHub 显示的检查名称"
# 确认输出后，再增加 --apply。
```

## 初次使用常见问题

### 找不到 `cpp-foundation` 命令

执行 `pipx ensurepath`，重新打开终端后再试。`pipx list` 可以查看工具是否已经安装。

### 输出目录已经存在

`init` 不会覆盖已有目录。请选择新路径，或者确认原目录内容后先将它移动到其他位置。

### Conan 提示编译器不匹配

确认已经设置 `CC=gcc-13` 和 `CXX=g++-13`，并使用项目自带的 GCC profile。不要通过
删除 lockfile 来隐藏错误。

### `doctor` 提示缺少发布程序

请先完成编译。第一次编译前，这是正常警告，不代表项目损坏。

### `template-diff` 报告文件变化

该命令只报告差异，不会覆盖任何文件。应逐项检查，并保留项目有意做出的修改。

## 下一步

- 逐步替换示例代码并添加测试；
- 修改依赖或升级版本前阅读[项目维护指南](maintenance.zh-CN.md)；
- 创建生产发布包或部署前阅读[运维指南](operations.zh-CN.md)。
