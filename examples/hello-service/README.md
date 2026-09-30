# Hello Service

This C++20 service was generated with C++ Project Foundation. It includes a small program,
a test, repeatable build settings, GitHub Actions and optional deployment examples.

If this is your first time using the toolkit, follow the full
[getting-started guide](https://github.com/HoneyBury/cpp-project-foundation/blob/main/docs/getting-started.md).
The commands below are a short reference for this project.

## Build and test

Use Ubuntu 24.04, GCC 13, Conan 2.8.1, CMake and Ninja:

```bash
export CC=gcc-13
export CXX=g++-13
conan install . \
  --profile:host conan/profiles/linux-gcc-x64 \
  --profile:build conan/profiles/linux-gcc-x64 \
  --lockfile conan/locks/linux-gcc-x64-release.lock \
  --output-folder=build/conan \
  --build=missing
cmake -S . -B build/release -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DENABLE_TESTING=ON \
  -DFOUNDATION_WARNINGS_AS_ERRORS=ON \
  -DCMAKE_TOOLCHAIN_FILE=build/conan/build/Release/generators/conan_toolchain.cmake
cmake --build build/release --parallel \
  --target hello_service hello_service_tests
ctest --test-dir build/release --output-on-failure
```

## Run the example

```bash
build/release/bin/hello-service --check
build/release/bin/hello-service --benchmark 200000
```

`--check` performs the small health check used by the template. `--benchmark` prints a JSON
performance result used by the optional operations workflow.

## Important files

| Path | Purpose |
| --- | --- |
| `src/`, `include/` | Example C++ implementation |
| `tests/` | Unit test |
| `foundation.toml` | Build, release and operation settings |
| `conanfile.py`, `conan/` | Dependency request, profiles and fixed lockfile |
| `deploy/` | Optional container, systemd and monitoring examples |
| `.github/workflows/` | Automated checks and release jobs |

This example currently uses
[`cpp-project-foundation@v0.6.0`](https://github.com/HoneyBury/cpp-project-foundation/releases/tag/v0.6.0).
Generated projects own their copied files and may change application code normally.
