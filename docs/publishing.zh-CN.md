# 发布 Python 工具

[English](publishing.md)

本指南只面向发布 `cpp-project-foundation` 自身的维护者。使用本工具生成的项目不需要
执行这些步骤。

发布分成两个独立阶段：

1. Release workflow 编译并在 GitHub 发布不可修改的 wheel；
2. PyPI workflow 下载完全相同的 wheel，验证后上传到 PyPI。

PyPI trusted publishing 让 GitHub 证明任务来自哪个仓库和 workflow，因此不需要在
GitHub 中保存长期 PyPI 密码或 API token。

## 一次性配置

在 PyPI 创建 pending trusted publisher，准确填写：

| PyPI 字段 | 值 |
| --- | --- |
| Project name | `cpp-project-foundation` |
| GitHub owner | `HoneyBury` |
| GitHub repository | `cpp-project-foundation` |
| Workflow filename | `publish-pypi.yml` |
| Environment name | `pypi` |

还要在 GitHub 创建名为 `pypi` 的 environment。单维护者仓库可以不设置 reviewer；团队
仓库通常应要求 reviewer。

不要为该 workflow 创建或保存 PyPI API token。

## 每次发布前

确认以下事项：

- 发布 pull request 已合并，所有必需检查通过；
- Python 包、示例 manifest 和 workflow 引用使用相同版本；
- `CHANGELOG.md` 已把 `Unreleased` 改为发布日期；
- 该版本还不存在于 Git tag、GitHub Release 或 PyPI。

从合并后的 `main` 提交创建并推送带说明的版本 tag。Release workflow 会编译 C++
示例、发布归档和 Python wheel，验证它们，创建证明记录并发布 GitHub Release。

只有该 workflow 成功，而且 GitHub Release 已包含 wheel 和 `.sha256` 文件后才能继续。

## 运行不上传的检查

下面的命令会执行所有检查，但有意跳过 PyPI 上传：

```bash
gh workflow run publish-pypi.yml \
  --repo HoneyBury/cpp-project-foundation \
  -f release-tag=v0.6.0 \
  -f publish=false
```

任务会验证 tag 和包版本、检查 wheel 校验值、在干净环境安装 wheel、创建示例项目，
并运行 `doctor` 和 `template-diff`。

## 发布到 PyPI

只有不上传的检查成功后才执行：

```bash
gh workflow run publish-pypi.yml \
  --repo HoneyBury/cpp-project-foundation \
  -f release-tag=v0.6.0 \
  -f publish=true
```

第一个 job 会重复全部验证；另一个独立 job 会接收已验证的 wheel，并使用短期 GitHub
身份上传。

## 验证公开软件包

Workflow 成功后，等待 PyPI 显示该版本，再从官方索引安装到干净环境：

```bash
python3 -m venv /tmp/cpp-foundation-pypi-check
/tmp/cpp-foundation-pypi-check/bin/pip install \
  --index-url https://pypi.org/simple \
  "cpp-project-foundation==0.6.0"
/tmp/cpp-foundation-pypi-check/bin/cpp-foundation --help
```

还要比较 PyPI wheel 的 SHA-256 和 GitHub Release 附带的 `.sha256` 文件。本地软件源
显示新版本的时间可能晚于 PyPI 官方索引。

## 发布失败时

- 不要替换 tag；
- 不要启用 `skip-existing`；
- 不要使用同一版本重新编译并上传不同文件；
- 保留 workflow 日志，确认失败发生在 PyPI 接受文件之前还是之后；
- 如果 PyPI 已接受该版本，应使用新版本修复并重新发布。

PyPI 文件和 release tag 都应当作为永久记录处理。
