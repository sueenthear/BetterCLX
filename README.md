# Better CLX

一梦江湖多实例窗口监控与启动面板，使用 Python 3.12、`PySide6`、`qfluentwidgets` 和 `uv` 构建。

## 运行

```powershell
uv sync
uv run clx
```

应用每秒枚举可见的 `wyclx64.exe` / `wyclx.exe` 顶层“一梦江湖”窗口，并按 PID 关联同一进程的 `MPAY_LOGIN` 或标题含“登录”的窗口。窗口信息统一显示在“绑定”页：单击窗口会在短暂缓冲后聚焦，双击窗口会取消待执行的聚焦动作并绑定该 HWND。应用同时只保留一个绑定窗口；F11 全屏和后续连招输出只作用于该绑定 HWND。

“启动”页提供游戏独立启动、游戏路径手动填写或 BFS 查找，以及多个脚本的独立启动配置。每个脚本都可以单独设置启动路径和更新网址；不再提供同时启动游戏和脚本的“一键启动”按钮。

“连招”页分为左窄右宽两栏。左侧是连招组列表，每组内含启用开关、红色删除按钮（带二次确认）和分享导出按钮，底部可新建空白组或从文件导入。右侧编辑器顶部可编辑组名、切换激活状态，下方以列表形式呈现操作块，触发后从上到下循环执行，并可用拖拽手柄调整顺序。操作块分为键盘事件（按键名称 + 按下/抬起）、延时事件（等待毫秒）和鼠标事件（中键上滚/下滚），每个操作块可监听并保存多个触发按键，任意一个按下都会触发，触发方式支持按住（松手强制终止）和切换（再次触发终止）。连招组数据保存在 `combo_groups.json`，单组可导出为 `.combo.json` 持久化文件并导入。所有按键都通过 Win32 消息直接发送给当前绑定的唯一 HWND。

## 测试

```powershell
uv run python -m unittest discover -s tests
```

## 目录结构

```text
better_clx/
  main.py                 应用入口
  config.py               运行配置
  models.py               窗口数据模型与状态
  combo_models.py         连招组、操作与触发模型
  combo_store.py          连招组 JSON 持久化与单组导入导出
  platform/windows.py     Win32 窗口枚举与登录归属检测
  services/monitor.py     周期扫描与状态聚合
  services/settings.py    JSON 配置和旧 INI 迁移
  services/launcher.py    游戏/脚本启动与 BFS 搜索
  services/window_actions.py  HWND 聚焦、绑定和全屏
  services/win32_input.py     Win32 按键监听与 PostMessage 输出
  services/combo_runtime.py   连招触发状态机与顺序执行
  ui/main_window.py       主窗口、侧边栏和 F11 热键
  ui/start_page.py        游戏与多脚本启动页
  ui/launcher_cards.py    游戏卡和脚本卡
  ui/binding_page.py      窗口信息与单 HWND 绑定页
  ui/combo_page.py        连招组两栏编辑器
  ui/combo_group_list.py  左侧连招组列表项
  ui/combo_editor.py      操作块编辑器与拖拽手柄
tests/
  test_window_detection.py
  test_launcher_settings.py
  test_window_binding.py
  test_combo_data.py
  test_combo_runtime.py
  test_combo_editor_ui.py
pyproject.toml             uv 项目与依赖定义
uv.lock                    锁定依赖版本
```
