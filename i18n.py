#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""JSON-backed translations for the file organizer."""

import json
import locale
from pathlib import Path


DEFAULT_LANGUAGE = "en"
LOCALE_DIR = Path(__file__).with_name("locales")

LANGUAGE_NAMES = {
    "en": "English",
    "zh-CN": "简体中文",
    "fr": "Français",
    "de": "Deutsch",
    "ja": "日本語",
}

LANGUAGE_ALIASES = {
    "en_US": "en",
    "en-US": "en",
    "zh": "zh-CN",
    "zh_CN": "zh-CN",
    "zh-CN": "zh-CN",
    "zh_Hans": "zh-CN",
    "zh-Hans": "zh-CN",
    "fr_FR": "fr",
    "fr-FR": "fr",
    "de_DE": "de",
    "de-DE": "de",
    "ja_JP": "ja",
    "ja-JP": "ja",
}


def available_languages():
    """Return language codes with English first."""
    codes = set(LANGUAGE_NAMES)
    if LOCALE_DIR.exists():
        codes.update(path.stem for path in LOCALE_DIR.glob("*.json"))

    return sorted(
        codes,
        key=lambda code: (code != DEFAULT_LANGUAGE, LANGUAGE_NAMES.get(code, code).lower()),
    )


def language_name(code):
    return LANGUAGE_NAMES.get(code, code)


def normalize_language(language):
    """Normalize a user/config locale into a supported language code."""
    if not language:
        return DEFAULT_LANGUAGE

    raw = str(language).strip()
    if not raw:
        return DEFAULT_LANGUAGE

    alias = LANGUAGE_ALIASES.get(raw) or LANGUAGE_ALIASES.get(raw.replace("_", "-"))
    if alias:
        return alias

    lower_to_code = {code.lower(): code for code in available_languages()}
    normalized = raw.replace("_", "-").lower()
    if normalized in lower_to_code:
        return lower_to_code[normalized]

    base = normalized.split("-", 1)[0]
    for code in available_languages():
        if code.lower().split("-", 1)[0] == base:
            return code

    return DEFAULT_LANGUAGE


def detect_system_language():
    try:
        language, _encoding = locale.getdefaultlocale()
    except Exception:
        language = None
    return normalize_language(language)


def _load_messages(language):
    path = LOCALE_DIR / f"{language}.json"
    if not path.exists():
        return {}

    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, dict):
        return {}
    return {str(key): str(value) for key, value in data.items()}


class Translator:
    """Translate message keys with English fallback."""

    def __init__(self, language=None):
        self._cache = {}
        self.language = DEFAULT_LANGUAGE
        self.messages = {}
        self.set_language(language or DEFAULT_LANGUAGE)

    def set_language(self, language):
        self.language = normalize_language(language)

        if DEFAULT_LANGUAGE not in self._cache:
            self._cache[DEFAULT_LANGUAGE] = _load_messages(DEFAULT_LANGUAGE)
        messages = dict(self._cache[DEFAULT_LANGUAGE])

        if self.language != DEFAULT_LANGUAGE:
            if self.language not in self._cache:
                self._cache[self.language] = _load_messages(self.language)
            messages.update(self._cache[self.language])

        self.messages = messages

    def t(self, key, **kwargs):
        text = self.messages.get(key, key)
        if not kwargs:
            return text
        try:
            return text.format(**kwargs)
        except (KeyError, ValueError):
            return text

    __call__ = t
