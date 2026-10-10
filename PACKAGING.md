# Better CLX 打包与发布流程

本文档记录 Better CLX 当前实际使用的 Windows 发布流程。

当前方案为：

- 主程序使用 `PyInstaller onedir`
- 安装器使用 `Tkinter + PyInstaller` 打成单文件自解包安装器
- 安装器运行时将 payload 释放到用户选择的目录
- 不使用 MSI
- 不使用 WiX
- 不上传旧 MSI 产物

## 1. 环境要求

Windows 环境需要安装：

- `uv`
- Python `>=3.12`
- Git
- GitHub CLI `gh`
- 已登录 GitHub CLI

项目依赖由 `uv` 管理。首次准备环境：

```powershell
uv sync
```

确认 PyInstaller 可用：

```powershell
uv run pyinstaller --version
```

确认 GitHub CLI 登录状态：

```powershell
gh auth status
gh repo view sueenthear/BetterCLX
```

## 2. 版本号和 Release Tag

项目版本位于 `pyproject.toml`：

```toml
version = "0.1.0"
```

构建脚本会自动读取该版本，并使用当天日期生成 tag：

```text
vX.X.X_buildYYMMDD
```

例如：

```text
v0.1.0_build261011
```

对应的输出目录为：

```text
release/v0.1.0_build261011/
```

## 3. 目录结构

构建前的关键文件：

```text
packaging/
├─ BetterCLX.spec       # 主程序 PyInstaller onedir spec
├─ setup.py              # Tk 自解包安装器源码
├─ setup.spec            # 安装器 PyInstaller spec
└─ build_release.ps1     # 完整构建脚本
```

默认连招示例位于：

```text
combo/
├─ __all__.json
└─ <group_id>.json
```

`combo/__all__.json` 维护连招组顺序、名称和启用状态；每个连招组使用单独的 JSON 文件。

## 4. 运行时持久化规则

程序运行时会通过 `better_clx/runtime_paths.py` 解析根目录：

- 源码运行：项目根目录
- PyInstaller 冻结运行：`BetterCLX.exe` 所在目录

因此冻结后的用户数据直接保存在安装目录内：

```text
<安装目录>/user_setting.json
<安装目录>/user_setting.ini
<安装目录>/combo/__all__.json
<安装目录>/combo/<group_id>.json
```

默认示例文件在安装器 payload 中位于：

```text
<安装目录>/examples/combo/
```

首次启动且安装目录中不存在 `combo/__all__.json` 时，程序会将 `examples/combo/*.json` 复制到 `combo/`。已有用户连招不会被覆盖。

注意：如果安装到受保护目录，例如 `C:\Program Files`，程序写入包内配置可能需要管理员权限。推荐在安装器中选择用户可写目录，例如：

```text
%LOCALAPPDATA%\BetterCLX
```

## 5. 构建 onedir 和安装器

在项目根目录执行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\packaging\build_release.ps1
```

构建脚本会依次执行：

1. 从 `better_clx/main.py` 构建主程序 onedir
2. 将 onedir 文件复制到 `packaging/payload`
3. 将 `combo/*.json` 复制到 `packaging/payload/examples/combo`
4. 使用 `packaging/setup.spec` 构建 Tk 单文件安装器
5. 验证 onedir 主程序和安装器存在

如果只修改了安装器界面，不需要重新构建主程序，可以复用已有 onedir：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\packaging\build_release.ps1 -SkipAppBuild
```

输出结构：

```text
release/<tag>/
├─ BetterCLX-Setup-<tag>.exe
└─ dist/
   └─ BetterCLX/
      ├─ BetterCLX.exe
      └─ _internal/
```

## 6. 安装器功能

安装器源码为 `packaging/setup.py`，当前提供：

- 安装目录输入框
- “浏览…”目录选择按钮
- “复制默认连招示例”复选框
- “创建桌面快捷方式”复选框
- 安装进度条
- 底部“开始安装”按钮
- 底部“取消”按钮

安装过程：

1. 创建用户选择的安装目录
2. 将 payload 中的 onedir 文件复制到安装目录
3. 如果勾选示例，将 `examples/combo` 复制为安装目录的 `combo`
4. 如果勾选快捷方式，创建桌面 `.lnk`
5. 安装完成后显示目标目录

安装器使用 `_MEIPASS` 定位自身 payload，适用于 PyInstaller 单文件运行环境。

## 7. 发布前验证

至少执行以下检查：

```powershell
uv run python -m unittest discover -s tests
uv run python -m compileall -q better_clx tests packaging
uv run python -m py_compile packaging/setup.py
git diff --check
```

确认产物：

```powershell
Test-Path .\release\v0.1.0_build261011\BetterCLX-Setup-v0.1.0_build261011.exe
Test-Path .\release\v0.1.0_build261011\dist\BetterCLX\BetterCLX.exe
Test-Path .\packaging\payload\examples\combo\__all__.json
```

确认 release 目录中不应包含旧 MSI：

```powershell
Get-ChildItem .\release\v0.1.0_build261011 -Filter *.msi
```

该命令应无输出。

建议手工验证安装器：

1. 启动 `BetterCLX-Setup-<tag>.exe`
2. 修改安装目录
3. 保持“复制默认连招示例”勾选
4. 保持“创建桌面快捷方式”勾选
5. 点击底部“开始安装”
6. 检查目标目录存在 `BetterCLX.exe`
7. 检查目标目录存在 `combo/__all__.json`
8. 启动目标目录下的 `BetterCLX.exe`
9. 修改窗口位置或连招后确认配置写入安装目录

## 8. 创建 GitHub Release

构建完成后读取当前版本对应的安装器路径：

```powershell
Get-Item .\release\v0.1.0_build261011\BetterCLX-Setup-v0.1.0_build261011.exe
```

检查 Release 是否已经存在：

```powershell
gh release view v0.1.0_build261011 --repo sueenthear/BetterCLX
```

如果不存在，创建 Release 并上传安装器：

```powershell
gh release create v0.1.0_build261011 `
  .\release\v0.1.0_build261011\BetterCLX-Setup-v0.1.0_build261011.exe `
  --repo sueenthear/BetterCLX `
  --title "Better CLX v0.1.0_build261011" `
  --notes "Better CLX v0.1.0 build 261011\n\n- PyInstaller onedir application\n- Tk self-extracting installer\n- Selectable installation directory\n- Optional default combo examples\n- Optional desktop shortcut\n- Package-local settings and combo persistence"
```

创建后检查：

```powershell
gh release view v0.1.0_build261011 --repo sueenthear/BetterCLX
```

## 9. 源码提交注意事项

不要提交以下文件：

```text
user_setting.json
user_setting.ini
.venv/
.reasonix/
build/
release/
packaging/payload/
__pycache__/
```

这些路径已在 `.gitignore` 中排除。

发布时应提交：

```text
better_clx/
tests/
packaging/BetterCLX.spec
packaging/setup.py
packaging/setup.spec
packaging/build_release.ps1
pyproject.toml
uv.lock
README.md
PACKAGING.md
```

安装器和 onedir 是 Release 资产，不直接提交到 Git 仓库。

## 10. 常见问题

### 找不到安装按钮

安装器窗口必须使用当前版本的 `BetterCLX-Setup-<tag>.exe`。当前安装器固定窗口大小为 `560x390`，安装按钮位于窗口底部操作栏。

如果看到旧界面，请删除旧安装器后重新运行最新 Release 资产。

### 安装后配置无法保存

确认安装目录有写权限。不要优先安装到 `C:\Program Files`；推荐选择用户目录或 `%LOCALAPPDATA%` 下的目录。

### 默认连招没有出现

确认安装器勾选了“复制默认连招示例”。也可以检查：

```text
<安装目录>/examples/combo/__all__.json
<安装目录>/combo/__all__.json
```

如果 `combo/` 已经存在，安装器不会覆盖已有连招数据。

### GitHub Release 创建失败

依次检查：

```powershell
gh auth status
gh repo view sueenthear/BetterCLX
gh release view <tag> --repo sueenthear/BetterCLX
```

如果 tag 已存在，不要重复创建，改用上传资产命令：

```powershell
gh release upload <tag> .\release\<tag>\BetterCLX-Setup-<tag>.exe --repo sueenthear/BetterCLX
```

### 为什么不再构建 MSI

当前项目使用 Tk 自解包安装器，原因是它能直接控制：

- 安装目录选择
- 默认连招是否复制
- 桌面快捷方式是否创建
- onedir 文件释放逻辑
- 包内配置和连招存储

因此不再使用旧的 WiX/MSI 流程。
