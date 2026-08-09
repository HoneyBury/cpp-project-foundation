# Python 分发发布

[English](publishing.md)

GitHub Release 仍是 Python wheel 的不可变来源。PyPI 发布会下载完全相同的 wheel，
校验其可移植 SHA-256 文件，在干净环境安装，再把已验证资产传递给独立的 OIDC job。
拥有发布权限的 job 不会 checkout 或执行仓库代码。

## 一次性 PyPI 配置

在 PyPI 为新项目创建 pending trusted publisher，字段必须与下表完全一致：

| 字段 | 值 |
| --- | --- |
| PyPI 项目名 | `cpp-project-foundation` |
| GitHub owner | `HoneyBury` |
| GitHub repository | `cpp-project-foundation` |
| Workflow 文件名 | `publish-pypi.yml` |
| Environment 名称 | `pypi` |

GitHub 仓库还必须存在名为 `pypi` 的 environment。不要添加 PyPI API token：发布 job
只获取短期 GitHub OIDC 身份。单维护者可以不配置 environment reviewer，团队仓库建议
配置 reviewer。

## 发布前验证

不可变 GitHub Release 创建后，先运行默认安全路径：

```bash
gh workflow run publish-pypi.yml \
  --repo HoneyBury/cpp-project-foundation \
  -f release-tag=v0.4.0 \
  -f publish=false
```

workflow 必须验证 tag、包版本、wheel checksum、安装后的 CLI、生成脚手架、`doctor`
和 `template-diff`。它只保留 wheel 一天，并跳过 OIDC job。

## 正式发布

只有 trusted publisher 字段完全匹配并且 dry-run 成功后，才运行：

```bash
gh workflow run publish-pypi.yml \
  --repo HoneyBury/cpp-project-foundation \
  -f release-tag=v0.4.0 \
  -f publish=true
```

PyPI 分发资产不可变。不能启用 `skip-existing`、替换 Git tag 或重新构建已经发布的
版本；任何修正都必须使用新的语义版本和新的 GitHub Release。

PyPI 显示该发布后，用户无需源码 checkout 即可安装：

```bash
pipx install "cpp-project-foundation==0.4.0"
```
