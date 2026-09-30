# Getting Started

[简体中文](getting-started.zh-CN.md)

This guide starts with a new Ubuntu 24.04 machine and ends with a running example service.
Commands marked as optional can be skipped during the first trial.

## 1. Install the basic tools

Install Python, `pipx`, the supported compiler, CMake and Ninja:

```bash
sudo apt-get update
sudo apt-get install -y \
  python3 python3-venv pipx \
  gcc-13 g++-13 cmake ninja-build git
pipx ensurepath
```

Open a new shell if `pipx ensurepath` asks you to. Confirm the important versions:

```bash
python3 --version
gcc-13 --version
cmake --version
ninja --version
```

Python must be 3.11 or newer. The supported compiler is GCC 13.

## 2. Install the project generator

```bash
pipx install "cpp-project-foundation==0.6.0"
cpp-foundation --help
```

`pipx` keeps this Python tool separate from your C++ project dependencies. To replace an
older installed version, use:

```bash
pipx install --force "cpp-project-foundation==0.6.0"
```

## 3. Create a project

Project names use lowercase letters, numbers and hyphens. The output directory must not
already exist.

```bash
cpp-foundation init \
  --name order-service \
  --version 0.1.0 \
  --output ../order-service
cd ../order-service
```

Run the two safe checks first:

```bash
cpp-foundation validate
cpp-foundation doctor --root .
```

At this stage, `doctor` may warn that the release program has not been built or that an
optional tool is missing. That is expected. Fix a `fail` result before continuing.

## 4. Look at the important files

You only need to understand a few files to begin:

- `src/main.cpp` starts the example program;
- `tests/request_parser_test.cpp` shows how a test is added;
- `CMakeLists.txt` defines the program and test targets;
- `conanfile.py` lists third-party C++ libraries;
- `foundation.toml` tells `cpp-foundation` which targets and files to use.

The remaining files provide automated checks, packaging and optional deployment examples.
You can leave them unchanged during the first trial.

## 5. Install Conan

Conan downloads the C++ libraries used by the project. Keep its Python environment inside
the project so it is easy to remove or recreate:

```bash
python3 -m venv .venv/conan
.venv/conan/bin/pip install "conan==2.8.1"
.venv/conan/bin/conan remote add \
  conancenter https://center2.conan.io --force
export PATH="$PWD/.venv/conan/bin:$PATH"
```

The `export` command applies only to the current shell. Run it again after opening a new
shell, or call `.venv/conan/bin/conan` directly.

## 6. Build and run

Tell Conan to install the fixed dependency versions already recorded by the project:

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

Configure and build the example program and its test:

```bash
cmake -S . -B build/release -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DENABLE_TESTING=ON \
  -DFOUNDATION_WARNINGS_AS_ERRORS=ON \
  -DCMAKE_TOOLCHAIN_FILE=build/conan/build/Release/generators/conan_toolchain.cmake
cmake --build build/release --parallel \
  --target order_service order_service_tests
ctest --test-dir build/release --output-on-failure
```

Run the service's built-in check:

```bash
build/release/bin/order-service --check
```

The exact target and file names come from the project name. For example,
`payment-api` becomes the CMake target `payment_api` and the program `payment-api`.

## 7. Install and run the code checks

This step is recommended before your first pull request:

```bash
python3 scripts/install_quality_tools.py \
  --venv .venv/quality \
  --tools-dir .tools
export PATH="$PWD/.venv/quality/bin:$PWD/.tools/bin:$PWD/.tools/npm/node_modules/.bin:$PATH"
cpp-foundation quality --root . --mode fast
```

The fast check covers source formatting and common configuration mistakes. The slower
deep check is useful before changes to CMake, Docker or documentation:

```bash
cpp-foundation quality --root . --mode deep
```

## 8. Put the project in Git

Review the generated files before committing them:

```bash
git init
git add .
git status
git commit -m "chore: create order service"
```

After pushing the project to GitHub, its files under `.github/workflows/` run the same main
build and checks automatically. Repository rules, secrets and production environments are
not created by the template; configure them separately for your organization.

## Common first-time problems

### `cpp-foundation: command not found`

Run `pipx ensurepath`, open a new shell and try again. `pipx list` shows whether the tool is
installed.

### The output directory already exists

`init` does not overwrite a directory. Choose a new path or move the existing directory
after checking its contents.

### Conan reports a compiler mismatch

Confirm `CC=gcc-13` and `CXX=g++-13`, then use the supplied GCC profile. Do not delete the
lockfile to hide the error.

### `doctor` reports missing release binaries

Build the project first. Before the first build, this is a warning rather than a broken
project.

### `template-diff` reports changes

This command only reports differences; it does not overwrite anything. Review each item
and keep intentional project changes.

## What next?

- Replace the example code and add tests.
- Read [Maintaining a project](maintenance.md) before changing dependencies or upgrading.
- Read [Operations](operations.md) before creating a production package or deployment.
