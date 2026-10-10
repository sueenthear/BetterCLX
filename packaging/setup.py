from __future__ import annotations

import os
import shutil
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

APP_NAME = "Better CLX"
BUNDLE_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
PAYLOAD_DIR = BUNDLE_ROOT / "payload"
DEFAULT_INSTALL_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "BetterCLX"


class Installer(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_NAME} 安装程序")
        self.geometry("560x390")
        self.minsize(560, 390)
        self.maxsize(560, 390)
        self.resizable(False, False)
        self.install_dir = tk.StringVar(value=str(DEFAULT_INSTALL_DIR))
        self.copy_examples = tk.BooleanVar(value=True)
        self.create_shortcut = tk.BooleanVar(value=True)
        self.progress = tk.DoubleVar(value=0)
        self.status = tk.StringVar(value="请选择安装目录")
        self._build_ui()

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=24)
        root.pack(fill="both", expand=True)
        ttk.Label(root, text=APP_NAME, font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(root, text="将 onedir 程序释放到你选择的目录。", padding=(0, 6, 0, 18)).pack(anchor="w")

        ttk.Label(root, text="安装目录").pack(anchor="w")
        path_row = ttk.Frame(root)
        path_row.pack(fill="x", pady=(5, 18))
        ttk.Entry(path_row, textvariable=self.install_dir).pack(side="left", fill="x", expand=True)
        ttk.Button(path_row, text="浏览…", command=self.choose_directory).pack(side="left", padx=(8, 0))

        ttk.Checkbutton(root, text="复制默认连招示例", variable=self.copy_examples).pack(anchor="w", pady=3)
        ttk.Checkbutton(root, text="创建桌面快捷方式", variable=self.create_shortcut).pack(anchor="w", pady=3)

        ttk.Label(root, textvariable=self.status).pack(anchor="w", pady=(18, 4))
        ttk.Progressbar(root, variable=self.progress, maximum=100).pack(fill="x")

        action_bar = ttk.Frame(root)
        action_bar.pack(fill="x", side="bottom", pady=(22, 0))
        ttk.Button(action_bar, text="取消", command=self.destroy).pack(side="right")
        self.install_button = ttk.Button(action_bar, text="开始安装", command=self.start_install)
        self.install_button.pack(side="right", padx=(0, 10))
        self.install_button.focus_set()

    def choose_directory(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.install_dir.get(), title="选择安装目录")
        if selected:
            self.install_dir.set(selected)

    def start_install(self) -> None:
        target = Path(self.install_dir.get().strip()).expanduser()
        if not target:
            messagebox.showerror(APP_NAME, "请选择安装目录")
            return
        if not PAYLOAD_DIR.is_dir() or not (PAYLOAD_DIR / "BetterCLX.exe").is_file():
            messagebox.showerror(APP_NAME, f"安装包缺少 payload：{PAYLOAD_DIR}")
            return
        self.install_button.configure(state="disabled")
        threading.Thread(target=self._install, args=(target,), daemon=True).start()

    def _install(self, target: Path) -> None:
        try:
            target.mkdir(parents=True, exist_ok=True)
            files = [p for p in PAYLOAD_DIR.rglob("*") if p.is_file()]
            for index, source in enumerate(files, 1):
                relative = source.relative_to(PAYLOAD_DIR)
                destination = target / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
                self.after(0, self._set_progress, index * 100 / len(files), f"正在复制文件 {index}/{len(files)}")

            if self.copy_examples.get():
                examples = PAYLOAD_DIR / "examples" / "combo"
                combo = target / "combo"
                if examples.is_dir() and not (combo / "__all__.json").exists():
                    shutil.copytree(examples, combo, dirs_exist_ok=True)

            if self.create_shortcut.get():
                self._create_shortcut(target / "BetterCLX.exe")

            self.after(0, self._finish, target)
        except Exception as exc:
            self.after(0, self._failed, str(exc))

    def _create_shortcut(self, executable: Path) -> None:
        desktop = Path(os.environ.get("USERPROFILE", Path.home())) / "Desktop"
        desktop.mkdir(parents=True, exist_ok=True)
        shortcut = desktop / f"{APP_NAME}.lnk"
        escaped_target = str(executable).replace("'", "''")
        script = (
            "$w=New-Object -ComObject WScript.Shell;"
            f"$s=$w.CreateShortcut('{shortcut}');$s.TargetPath='{escaped_target}';"
            f"$s.WorkingDirectory='{executable.parent}';$s.IconLocation='{escaped_target},0';$s.Save()"
        )
        os.system(f'powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "{script}"')

    def _set_progress(self, value: float, text: str) -> None:
        self.progress.set(value)
        self.status.set(text)

    def _finish(self, target: Path) -> None:
        self.progress.set(100)
        self.status.set("安装完成")
        messagebox.showinfo(APP_NAME, f"已安装到：{target}")
        self.destroy()

    def _failed(self, error: str) -> None:
        self.install_button.configure(state="normal")
        self.status.set("安装失败")
        messagebox.showerror(APP_NAME, error)


if __name__ == "__main__":
    Installer().mainloop()
