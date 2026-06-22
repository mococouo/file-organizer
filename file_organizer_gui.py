#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
File Organizer GUI
Organize files from one or more source folders into one target folder.
"""

import os
import queue
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from i18n import Translator, available_languages, language_name
from organizer_config import is_hidden_path, is_relative_to, load_config


SKIP_FILE_NAMES = {
    "file_organizer.py",
    "file_organizer_gui.py",
    "organizer_report.txt",
    "start_cli.bat",
    "start_gui.bat",
    "一键整理.bat",
    "图形界面整理.bat",
}


def open_folder(path):
    folder = str(path)
    if sys.platform.startswith("win"):
        os.startfile(folder)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", folder])
    else:
        subprocess.Popen(["xdg-open", folder])


class FileOrganizerGUI:
    def __init__(self, root):
        self.root = root
        self.config = load_config()
        self.t = Translator(self.config["settings"].get("language", "en"))

        self.source_folders = []
        self.target_folder = None
        self.is_running = False
        self.thread = None
        self.log_queue = queue.Queue()
        self.log_history = []

        self.mode_var = tk.StringVar(value=self.config["settings"].get("default_mode", "copy"))
        self.language_var = tk.StringVar(value=self.format_language(self.t.language))
        self.status_var = tk.StringVar(value=self.t("status.ready"))
        self.progress_var = tk.DoubleVar()

        self.stats = {
            "total_files": 0,
            "processed_files": 0,
            "skipped_files": 0,
            "renamed_files": 0,
            "file_types": defaultdict(int),
        }
        self.processing_log = []

        self.root.geometry("860x640")
        self.root.resizable(True, True)
        self.init_ui()
        self.update_log()

    def format_language(self, code):
        return f"{language_name(code)} ({code})"

    def language_from_display(self, value):
        if "(" in value and value.endswith(")"):
            return value.rsplit("(", 1)[1][:-1]
        return value

    def init_ui(self):
        for child in self.root.winfo_children():
            child.destroy()

        self.root.title(self.t("app.title"))

        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(5, weight=1)

        title_label = ttk.Label(main_frame, text=self.t("app.title"), font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))

        language_frame = ttk.Frame(main_frame)
        language_frame.grid(row=0, column=2, sticky=tk.E, pady=(0, 10))
        ttk.Label(language_frame, text=self.t("ui.language")).pack(side=tk.LEFT, padx=(0, 5))

        language_values = [self.format_language(code) for code in available_languages()]
        self.language_var.set(self.format_language(self.t.language))
        language_combo = ttk.Combobox(
            language_frame,
            textvariable=self.language_var,
            values=language_values,
            width=22,
            state="readonly",
        )
        language_combo.pack(side=tk.LEFT)
        language_combo.bind("<<ComboboxSelected>>", self.change_language)

        ttk.Label(main_frame, text=self.t("ui.source_folders")).grid(row=1, column=0, sticky=tk.W, pady=5)

        source_frame = ttk.Frame(main_frame)
        source_frame.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5)
        source_frame.columnconfigure(0, weight=1)

        self.source_listbox = tk.Listbox(source_frame, height=4, selectmode=tk.EXTENDED)
        self.source_listbox_scroll = ttk.Scrollbar(source_frame, orient=tk.VERTICAL, command=self.source_listbox.yview)
        self.source_listbox.configure(yscrollcommand=self.source_listbox_scroll.set)
        self.source_listbox.grid(row=0, column=0, sticky=(tk.W, tk.E))
        self.source_listbox_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        for folder in self.source_folders:
            self.source_listbox.insert(tk.END, folder)

        source_button_frame = ttk.Frame(main_frame)
        source_button_frame.grid(row=1, column=2, padx=5)
        ttk.Button(source_button_frame, text=self.t("button.add_folder"), command=self.add_source_folder).pack(fill=tk.X, pady=2)
        ttk.Button(
            source_button_frame,
            text=self.t("button.remove_selected"),
            command=self.remove_source_folder,
        ).pack(fill=tk.X, pady=2)
        ttk.Button(source_button_frame, text=self.t("button.clear_list"), command=self.clear_source_folders).pack(fill=tk.X, pady=2)

        ttk.Label(main_frame, text=self.t("ui.target_folder")).grid(row=2, column=0, sticky=tk.W, pady=5)

        target_frame = ttk.Frame(main_frame)
        target_frame.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5)
        target_frame.columnconfigure(0, weight=1)

        self.target_var = tk.StringVar(value=str(self.target_folder) if self.target_folder else "")
        self.target_entry = ttk.Entry(target_frame, textvariable=self.target_var, state="readonly")
        self.target_entry.grid(row=0, column=0, sticky=(tk.W, tk.E))
        ttk.Button(main_frame, text=self.t("button.choose_folder"), command=self.select_target_folder).grid(
            row=2,
            column=2,
            padx=5,
        )

        mode_frame = ttk.LabelFrame(main_frame, text=self.t("ui.mode"), padding="10")
        mode_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        ttk.Radiobutton(
            mode_frame,
            text=self.t("mode.copy_gui"),
            variable=self.mode_var,
            value="copy",
        ).pack(side=tk.LEFT, padx=20)
        ttk.Radiobutton(
            mode_frame,
            text=self.t("mode.move_gui"),
            variable=self.mode_var,
            value="move",
        ).pack(side=tk.LEFT, padx=20)

        log_frame = ttk.LabelFrame(main_frame, text=self.t("ui.log"), padding="5")
        log_frame.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, wrap=tk.WORD, font=("Courier", 9))
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        if self.log_history:
            self.log_text.insert(tk.END, "".join(self.log_history))
            self.log_text.see(tk.END)

        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)

        self.status_label = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.grid(row=7, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)

        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=8, column=0, columnspan=3, pady=10)

        self.start_btn = ttk.Button(control_frame, text=self.t("button.start"), command=self.start_organize)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        self.stop_btn = ttk.Button(control_frame, text=self.t("button.stop"), command=self.stop_organize)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text=self.t("button.clear_log"), command=self.clear_log).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text=self.t("button.about"), command=self.show_about).pack(side=tk.LEFT, padx=5)

        self.start_btn.config(state=tk.DISABLED if self.is_running else tk.NORMAL)
        self.stop_btn.config(state=tk.NORMAL if self.is_running else tk.DISABLED)

    def change_language(self, _event=None):
        code = self.language_from_display(self.language_var.get())
        self.t.set_language(code)
        self.config["settings"]["language"] = code
        self.status_var.set(self.t("status.ready") if not self.is_running else self.status_var.get())
        self.init_ui()
        self.log(self.t("log.language_changed", language=language_name(self.t.language)))

    def add_source_folder(self):
        folder = filedialog.askdirectory(title=self.t("dialog.select_source"))
        if folder:
            folder_path = Path(folder).resolve()
            if str(folder_path) not in self.source_folders:
                self.source_folders.append(str(folder_path))
                self.source_listbox.insert(tk.END, str(folder_path))
                self.log(self.t("log.added_source", path=folder_path))
            else:
                messagebox.showwarning(self.t("dialog.warning"), self.t("warning.folder_already_added"))

    def remove_source_folder(self):
        selections = self.source_listbox.curselection()
        if not selections:
            messagebox.showwarning(self.t("dialog.warning"), self.t("warning.select_folder_to_remove"))
            return

        for index in reversed(selections):
            self.source_folders.pop(index)
            self.source_listbox.delete(index)

    def clear_source_folders(self):
        if messagebox.askyesno(self.t("dialog.confirm"), self.t("confirm.clear_sources")):
            self.source_folders.clear()
            self.source_listbox.delete(0, tk.END)
            self.log(self.t("log.cleared_sources"))

    def select_target_folder(self):
        folder = filedialog.askdirectory(title=self.t("dialog.select_target"))
        if folder:
            self.target_folder = Path(folder).resolve()
            self.target_var.set(str(self.target_folder))
            self.log(self.t("log.selected_target", path=self.target_folder))

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"
        self.log_history.append(log_message)
        self.log_queue.put(log_message)

    def update_log(self):
        try:
            while True:
                message = self.log_queue.get_nowait()
                self.log_text.insert(tk.END, message)
                self.log_text.see(tk.END)
        except queue.Empty:
            pass

        self.root.after(100, self.update_log)

    def clear_log(self):
        self.log_history.clear()
        self.log_text.delete(1.0, tk.END)

    def show_about(self):
        messagebox.showinfo(self.t("dialog.about"), self.t("about.message"))

    def has_invalid_target(self):
        if not self.target_folder:
            return False

        for folder in self.source_folders:
            if Path(folder).resolve() == self.target_folder:
                return True
        return False

    def start_organize(self):
        if not self.source_folders:
            messagebox.showwarning(self.t("dialog.warning"), self.t("warning.add_source_required"))
            return

        if not self.target_folder:
            messagebox.showwarning(self.t("dialog.warning"), self.t("warning.target_required"))
            return

        if self.has_invalid_target():
            messagebox.showwarning(self.t("dialog.warning"), self.t("warning.target_same_as_source"))
            return

        mode_text = self.t("mode.copy") if self.mode_var.get() == "copy" else self.t("mode.move")
        message = self.t(
            "confirm.start_message",
            count=len(self.source_folders),
            target=self.target_folder,
            mode=mode_text,
        )

        if not messagebox.askyesno(self.t("dialog.confirm"), message):
            return

        self.stats = {
            "total_files": 0,
            "processed_files": 0,
            "skipped_files": 0,
            "renamed_files": 0,
            "file_types": defaultdict(int),
        }
        self.processing_log.clear()
        self.progress_var.set(0)

        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.is_running = True

        self.clear_log()
        self.log("=" * 60)
        self.log(self.t("log.start"))
        self.log("=" * 60)

        self.thread = threading.Thread(target=self.run_organize, daemon=True)
        self.thread.start()

    def stop_organize(self):
        if messagebox.askyesno(self.t("dialog.confirm"), self.t("confirm.stop")):
            self.is_running = False
            self.log(self.t("log.stopping"))

    def run_organize(self):
        try:
            organizer = MultiFolderOrganizer(
                source_folders=self.source_folders,
                target_folder=str(self.target_folder),
                move_files=self.mode_var.get() == "move",
                categories=self.config["categories"],
                settings=self.config["settings"],
                translator=self.t,
                gui=self,
            )
            organizer.run()
            self.root.after(0, self.organize_complete)
        except Exception as exc:
            self.log(str(exc))
            self.root.after(0, self.organize_complete)

    def organize_complete(self):
        self.is_running = False
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.progress_var.set(100)

        self.log("=" * 60)
        self.log(self.t("log.complete"))
        self.log("=" * 60)

        messagebox.showinfo(self.t("dialog.complete"), self.t("complete.message"))

        if messagebox.askyesno(self.t("dialog.open_folder"), self.t("open_folder.message")):
            open_folder(self.target_folder)

    def update_progress(self, value, total):
        if total <= 0:
            return
        progress = (value / total) * 100
        self.root.after(0, lambda: self.progress_var.set(progress))

    def update_status(self, message):
        self.root.after(0, lambda: self.status_var.set(message))


class MultiFolderOrganizer:
    def __init__(
        self,
        source_folders,
        target_folder,
        move_files=False,
        categories=None,
        settings=None,
        translator=None,
        gui=None,
    ):
        self.source_folders = [Path(folder).resolve() for folder in source_folders]
        self.target_folder = Path(target_folder).resolve()
        self.move_files = move_files
        self.categories = categories or {}
        self.settings = settings or {}
        self.rename_separator = str(self.settings.get("rename_separator") or "_")
        self.include_hidden_files = bool(self.settings.get("include_hidden_files", False))
        self.t = translator or Translator(self.settings.get("language", "en"))
        self.gui = gui

        self.stats = {
            "total_files": 0,
            "processed_files": 0,
            "skipped_files": 0,
            "renamed_files": 0,
            "file_types": defaultdict(int),
        }
        self.processing_log = []

    def get_file_extension(self, file_path):
        return file_path.suffix.lower()

    def get_file_category(self, extension):
        for category, extensions in self.categories.items():
            if extension in extensions:
                return category
        return "others"

    def get_unique_filename(self, target_path):
        if not target_path.exists():
            return target_path

        original_stem = target_path.stem
        suffix = target_path.suffix
        counter = 1

        while True:
            new_name = f"{original_stem}{self.rename_separator}{counter}{suffix}"
            new_path = target_path.parent / new_name
            if not new_path.exists():
                self.stats["renamed_files"] += 1
                return new_path
            counter += 1

    def log(self, message):
        if self.gui:
            self.gui.log(message)
        else:
            print(message)

    def update_progress(self):
        if self.gui and self.stats["total_files"] > 0:
            self.gui.update_progress(self.stats["processed_files"], self.stats["total_files"])

    def update_status(self, message):
        if self.gui:
            self.gui.update_status(message)
        else:
            print(message)

    def check_stop(self):
        if self.gui and hasattr(self.gui, "is_running"):
            return not self.gui.is_running
        return False

    def should_skip_file(self, file_path, source_dir):
        if file_path.name in SKIP_FILE_NAMES:
            return True

        if self.target_folder != source_dir and is_relative_to(file_path, self.target_folder):
            return True

        if not self.include_hidden_files and is_hidden_path(file_path, source_dir):
            return True

        return False

    def scan_all_folders(self):
        all_files = []

        for source_dir in self.source_folders:
            if not source_dir.exists():
                self.log(self.t("cli.source_missing", path=source_dir))
                continue

            self.log(self.t("log.scan_folder", path=source_dir))

            for file_path in source_dir.rglob("*"):
                if self.check_stop():
                    return []

                if file_path.is_file() and not self.should_skip_file(file_path, source_dir):
                    all_files.append(file_path)
                    self.stats["total_files"] += 1

                    extension = self.get_file_extension(file_path)
                    self.stats["file_types"][extension] += 1

        self.log(self.t("log.found_files", count=self.stats["total_files"]))
        return all_files

    def organize_file(self, file_path):
        try:
            extension = self.get_file_extension(file_path)
            category = self.get_file_category(extension)
            type_dir = self.target_folder / category / (extension[1:] if extension else "no_extension")
            type_dir.mkdir(parents=True, exist_ok=True)

            target_path = self.get_unique_filename(type_dir / file_path.name)

            if self.move_files:
                shutil.move(str(file_path), str(target_path))
                action = self.t("action.move")
                log_key = "log.moved_renamed" if file_path.name != target_path.name else "log.moved"
            else:
                shutil.copy2(str(file_path), str(target_path))
                action = self.t("action.copy")
                log_key = "log.copied_renamed" if file_path.name != target_path.name else "log.copied"

            log_entry = {
                "source": str(file_path),
                "target": str(target_path.relative_to(self.target_folder)),
                "action": action,
                "renamed": file_path.name != target_path.name,
            }
            self.processing_log.append(log_entry)
            self.stats["processed_files"] += 1

            if log_entry["renamed"]:
                self.log(self.t(log_key, old=file_path.name, new=target_path.name))
            else:
                self.log(self.t(log_key, name=file_path.name))

        except Exception as exc:
            self.log(self.t("log.failed", name=file_path.name, error=str(exc)))
            self.stats["skipped_files"] += 1
            self.processing_log.append(
                {
                    "source": str(file_path),
                    "target": None,
                    "action": self.t("action.failed"),
                    "error": str(exc),
                }
            )

    def clean_empty_folders(self):
        if not self.move_files:
            return

        self.log(self.t("log.cleaning"))

        for source_dir in self.source_folders:
            if not source_dir.exists():
                continue

            for dir_path in sorted(source_dir.rglob("*"), key=lambda path: len(path.parts), reverse=True):
                if is_relative_to(dir_path, self.target_folder):
                    continue
                if dir_path.is_dir() and not any(dir_path.iterdir()):
                    try:
                        dir_path.rmdir()
                        self.log(self.t("log.removed_empty_folder", path=dir_path.relative_to(source_dir)))
                    except OSError:
                        pass

    def generate_report(self):
        report_path = self.target_folder / "organizer_report.txt"
        mode = self.t("mode.move") if self.move_files else self.t("mode.copy")

        with open(report_path, "w", encoding="utf-8") as report:
            report.write("=" * 80 + "\n")
            report.write(self.t("report.title") + "\n")
            report.write("=" * 80 + "\n")
            report.write(self.t("report.generated_at", time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")) + "\n")
            report.write(self.t("report.operation_mode", mode=mode) + "\n")
            report.write("=" * 80 + "\n\n")

            report.write(self.t("report.sources_heading") + "\n")
            for index, folder in enumerate(self.source_folders, 1):
                report.write(f"{index}. {folder}\n")
            report.write("\n" + self.t("report.target_folder", path=self.target_folder) + "\n\n")

            report.write(self.t("report.stats_heading") + "\n")
            report.write(self.t("report.total_files", count=self.stats["total_files"]) + "\n")
            report.write(self.t("report.processed_files", count=self.stats["processed_files"]) + "\n")
            report.write(self.t("report.skipped_files", count=self.stats["skipped_files"]) + "\n")
            report.write(self.t("report.renamed_files", count=self.stats["renamed_files"]) + "\n\n")

            report.write(self.t("report.distribution_heading") + "\n")
            for extension, count in sorted(self.stats["file_types"].items(), key=lambda item: item[1], reverse=True):
                extension_display = extension if extension else self.t("report.no_extension")
                report.write(self.t("report.extension_count", extension=extension_display, count=count) + "\n")
            report.write("\n")

            report.write(self.t("report.details_heading") + "\n")
            for index, item in enumerate(self.processing_log, 1):
                report.write(f"\n{index}. {self.t('report.source_file', path=item['source'])}\n")
                if item["target"]:
                    report.write(self.t("report.target_location", path=item["target"]) + "\n")
                    report.write(self.t("report.action", action=item["action"]))
                    if item.get("renamed", False):
                        report.write(self.t("report.renamed_note"))
                    report.write("\n")
                else:
                    report.write(self.t("report.status", status=item["action"]) + "\n")
                    report.write(
                        self.t("report.error", error=item.get("error", self.t("report.unknown_error"))) + "\n"
                    )

            report.write("\n" + "=" * 80 + "\n")
            report.write(self.t("report.generated") + "\n")
            report.write("=" * 80 + "\n")

        return report_path

    def run(self):
        self.log(self.t("cli.begin"))

        self.update_status(self.t("status.scanning"))
        files_to_process = self.scan_all_folders()

        if not files_to_process or self.check_stop():
            self.log(self.t("log.cancelled_or_empty"))
            return

        self.log(self.t("log.begin_count", count=len(files_to_process)))

        for index, file_path in enumerate(files_to_process, 1):
            if self.check_stop():
                self.log(self.t("log.stopped"))
                break

            self.update_status(self.t("status.processing", name=file_path.name, index=index, total=len(files_to_process)))
            self.organize_file(file_path)
            self.update_progress()

        if self.move_files and not self.check_stop():
            self.update_status(self.t("status.cleaning"))
            self.clean_empty_folders()

        self.update_status(self.t("status.report"))
        report_path = self.generate_report()

        self.log("\n" + "=" * 60)
        self.log(self.t("log.complete"))
        self.log("=" * 60)
        self.log(self.t("log.summary_total", count=self.stats["total_files"]))
        self.log(self.t("log.summary_processed", count=self.stats["processed_files"]))
        self.log(self.t("log.summary_skipped", count=self.stats["skipped_files"]))
        self.log(self.t("log.summary_renamed", count=self.stats["renamed_files"]))
        self.log("")
        self.log(self.t("log.target_folder", path=self.target_folder))
        self.log(self.t("log.report_path", path=report_path))
        self.log("=" * 60)

        self.update_status(self.t("status.complete"))


def main():
    root = tk.Tk()
    FileOrganizerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
