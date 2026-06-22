#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Configuration loading shared by the CLI and GUI."""

import json
from pathlib import Path


DEFAULT_CATEGORIES = {
    "images": [
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp", ".svg",
        ".ico", ".raw", ".heic",
    ],
    "videos": [
        ".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v",
        ".mpg", ".mpeg", ".3gp",
    ],
    "audios": [".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg", ".wma", ".ape", ".alac"],
    "documents": [
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt",
        ".md", ".rtf", ".csv",
    ],
    "archives": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".tgz", ".rar5"],
    "executables": [".exe", ".msi", ".bat", ".sh", ".cmd", ".ps1"],
    "code": [
        ".py", ".java", ".cpp", ".c", ".js", ".html", ".css", ".php",
        ".sql", ".go", ".rs", ".swift",
    ],
    "others": [],
}

DEFAULT_SETTINGS = {
    "default_mode": "copy",
    "rename_separator": "_",
    "include_hidden_files": False,
    "log_level": "verbose",
    "language": "en",
}

SETTING_ALIASES = {
    "默认操作模式": "default_mode",
    "重命名分隔符": "rename_separator",
    "是否包含隐藏文件": "include_hidden_files",
    "日志级别": "log_level",
    "语言": "language",
}


def _normalize_extension(extension):
    value = str(extension).strip().lower()
    if not value:
        return None
    if not value.startswith("."):
        value = f".{value}"
    return value


def _normalize_extensions(value):
    if not isinstance(value, list):
        return []

    extensions = []
    for item in value:
        normalized = _normalize_extension(item)
        if normalized and normalized not in extensions:
            extensions.append(normalized)
    return extensions


def _normalize_mode(value):
    mode = str(value).strip().lower()
    if mode in {"move", "moving", "moved", "2", "移动"}:
        return "move"
    return "copy"


def _normalize_bool(value):
    if isinstance(value, bool):
        return value

    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y", "on", "是", "是的"}:
        return True
    if normalized in {"0", "false", "no", "n", "off", "否", "不是"}:
        return False
    return bool(value)


def _load_json(path):
    if not path.exists():
        return {}

    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


def load_config(config_path=None):
    """Load config.json while accepting the previous Chinese key names."""
    path = Path(config_path) if config_path else Path(__file__).with_name("config.json")

    try:
        data = _load_json(path)
    except (OSError, json.JSONDecodeError):
        data = {}

    categories = {name: list(extensions) for name, extensions in DEFAULT_CATEGORIES.items()}
    raw_categories = data.get("file_categories") or data.get("文件分类规则") or {}
    if isinstance(raw_categories, dict):
        for name, value in raw_categories.items():
            if isinstance(value, dict):
                raw_extensions = value.get("extensions", value.get("扩展名", []))
            else:
                raw_extensions = value

            extensions = _normalize_extensions(raw_extensions)
            if extensions or name not in categories:
                categories[str(name)] = extensions

    categories.setdefault("others", [])

    settings = dict(DEFAULT_SETTINGS)
    raw_settings = data.get("settings") or data.get("设置") or {}
    if isinstance(raw_settings, dict):
        for key, value in raw_settings.items():
            canonical_key = SETTING_ALIASES.get(key, key)
            settings[canonical_key] = value

    if "language" in data:
        settings["language"] = data["language"]
    settings["default_mode"] = _normalize_mode(settings.get("default_mode", "copy"))
    settings["rename_separator"] = str(settings.get("rename_separator") or "_")
    settings["include_hidden_files"] = _normalize_bool(settings.get("include_hidden_files", False))
    settings["language"] = str(settings.get("language") or "en")

    return {
        "path": path,
        "categories": categories,
        "settings": settings,
    }


def is_relative_to(path, parent):
    try:
        Path(path).resolve().relative_to(Path(parent).resolve())
        return True
    except ValueError:
        return False


def is_hidden_path(path, root=None):
    file_path = Path(path)
    if root is not None:
        try:
            parts = file_path.relative_to(root).parts
        except ValueError:
            parts = file_path.parts
    else:
        parts = file_path.parts

    return any(part.startswith(".") for part in parts if part not in {".", ".."})
