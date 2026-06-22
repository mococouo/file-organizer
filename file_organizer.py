#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
File Organizer
Scan a folder, sort files by extension, and handle duplicate file names.
"""

import argparse
import os
import shutil
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

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

YES_VALUES = {"y", "yes", "o", "oui", "j", "ja", "s", "si", "sí", "是", "是的", "はい"}


def configure_console_encoding():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass


class FileOrganizer:
    def __init__(
        self,
        source_dir,
        output_dir=None,
        move_files=False,
        categories=None,
        settings=None,
        translator=None,
    ):
        self.source_dir = Path(source_dir).resolve()
        self.output_dir = Path(output_dir).resolve() if output_dir else self.source_dir / "organized"
        self.move_files = move_files
        self.categories = categories or {}
        self.settings = settings or {}
        self.rename_separator = str(self.settings.get("rename_separator") or "_")
        self.include_hidden_files = bool(self.settings.get("include_hidden_files", False))
        self.t = translator or Translator(self.settings.get("language", "en"))

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

    def should_skip_file(self, file_path):
        if file_path.name in SKIP_FILE_NAMES:
            return True

        if self.output_dir != self.source_dir and is_relative_to(file_path, self.output_dir):
            return True

        if not self.include_hidden_files and is_hidden_path(file_path, self.source_dir):
            return True

        return False

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

    def scan_files(self):
        print(self.t("log.scan_folder", path=self.source_dir))
        all_files = []

        for file_path in self.source_dir.rglob("*"):
            if file_path.is_file() and not self.should_skip_file(file_path):
                all_files.append(file_path)
                self.stats["total_files"] += 1

                extension = self.get_file_extension(file_path)
                self.stats["file_types"][extension] += 1

        print(self.t("log.found_files", count=self.stats["total_files"]))
        return all_files

    def organize_file(self, file_path):
        try:
            extension = self.get_file_extension(file_path)
            category = self.get_file_category(extension)
            type_dir = self.output_dir / category / (extension[1:] if extension else "no_extension")
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
                "source": str(file_path.relative_to(self.source_dir)),
                "target": str(target_path.relative_to(self.output_dir)),
                "action": action,
                "renamed": file_path.name != target_path.name,
            }
            self.processing_log.append(log_entry)
            self.stats["processed_files"] += 1

            if log_entry["renamed"]:
                print("  " + self.t(log_key, old=file_path.name, new=target_path.name))
            else:
                print("  " + self.t(log_key, name=file_path.name))

        except Exception as exc:
            print("  " + self.t("log.failed", name=file_path.name, error=str(exc)))
            self.stats["skipped_files"] += 1
            self.processing_log.append(
                {
                    "source": str(file_path.relative_to(self.source_dir)),
                    "target": None,
                    "action": self.t("action.failed"),
                    "error": str(exc),
                }
            )

    def generate_report(self):
        report_path = self.output_dir / "organizer_report.txt"
        mode = self.t("mode.move") if self.move_files else self.t("mode.copy")

        with open(report_path, "w", encoding="utf-8") as report:
            report.write("=" * 80 + "\n")
            report.write(self.t("report.title") + "\n")
            report.write("=" * 80 + "\n")
            report.write(self.t("report.generated_at", time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")) + "\n")
            report.write(self.t("report.source_folder", path=self.source_dir) + "\n")
            report.write(self.t("report.output_folder", path=self.output_dir) + "\n")
            report.write(self.t("report.operation_mode", mode=mode) + "\n")
            report.write("=" * 80 + "\n\n")

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
        print("\n" + "=" * 80)
        print(self.t("cli.start_title"))
        print("=" * 80 + "\n")

        if not self.source_dir.exists():
            print(self.t("cli.source_missing", path=self.source_dir))
            return False

        self.output_dir.mkdir(parents=True, exist_ok=True)
        files_to_process = self.scan_files()

        if not files_to_process:
            print(self.t("cli.no_files"))
            return False

        print("\n" + self.t("cli.begin") + "\n")
        for file_path in files_to_process:
            self.organize_file(file_path)

        print("\n" + self.t("cli.generating_report"))
        report_path = self.generate_report()

        print("\n" + "=" * 80)
        print(self.t("cli.done"))
        print("=" * 80)
        print(self.t("log.summary_total", count=self.stats["total_files"]))
        print(self.t("log.summary_processed", count=self.stats["processed_files"]))
        print(self.t("log.summary_skipped", count=self.stats["skipped_files"]))
        print(self.t("log.summary_renamed", count=self.stats["renamed_files"]))
        print()
        print(self.t("cli.output_location", path=self.output_dir))
        print(self.t("cli.report_location", path=report_path))
        print("=" * 80 + "\n")

        return True


def build_parser(translator):
    parser = argparse.ArgumentParser(description=translator("cli.description"))
    parser.add_argument("--lang", help=translator("cli.lang_help"))
    parser.add_argument("--list-languages", action="store_true", help=translator("cli.list_languages_help"))
    parser.add_argument("--source", help=translator("cli.source_help"))
    parser.add_argument("--output", help=translator("cli.output_help"))
    parser.add_argument("--move", action="store_true", help=translator("cli.move_help"))
    parser.add_argument("--copy", action="store_true", help=translator("cli.copy_help"))
    parser.add_argument("--yes", action="store_true", help=translator("cli.yes_help"))
    return parser


def choose_mode(args, settings, translator):
    if args.move and args.copy:
        return False
    if args.move:
        return True
    if args.copy:
        return False

    default_move = settings.get("default_mode") == "move"
    if args.source:
        return default_move

    while True:
        mode = input(translator("cli.mode_prompt")).strip()
        if mode in {"1", "2"}:
            return mode == "2"
        print(translator("cli.invalid_mode"))


def list_languages(translator):
    print(translator("cli.available_languages"))
    for code in available_languages():
        print(f"  {code}: {language_name(code)}")


def main(argv=None):
    configure_console_encoding()

    config = load_config()
    bootstrap_translator = Translator(config["settings"].get("language", "en"))
    parser = build_parser(bootstrap_translator)
    args = parser.parse_args(argv)

    if args.lang:
        config["settings"]["language"] = args.lang
    translator = Translator(config["settings"].get("language", "en"))

    if args.list_languages:
        list_languages(translator)
        return

    print(translator("cli.header"))
    print("=" * 80)

    source_dir = args.source
    if not source_dir:
        source_dir = input(translator("cli.source_prompt")).strip() or "."

    move_files = choose_mode(args, config["settings"], translator)
    mode_text = translator("mode.move") if move_files else translator("mode.copy")

    print()
    print(translator("cli.ready_source", path=os.path.abspath(source_dir)))
    print(translator("cli.mode_label", mode=mode_text))
    print("=" * 80)

    if not args.yes:
        confirm = input(translator("cli.confirm_prompt")).strip().lower()
        if confirm not in YES_VALUES:
            print(translator("cli.cancelled"))
            return

    organizer = FileOrganizer(
        source_dir,
        output_dir=args.output,
        move_files=move_files,
        categories=config["categories"],
        settings=config["settings"],
        translator=translator,
    )
    success = organizer.run()

    if success:
        print(translator("cli.tips_title"))
        print(translator("cli.tip_check_output"))
        print(translator("cli.tip_read_report"))
        print(translator("cli.tip_delete_originals"))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n")
        sys.exit(0)
    except Exception as error:
        print(f"\n{error}")
        sys.exit(1)
