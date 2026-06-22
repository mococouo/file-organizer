# File Organizer

A small Python utility that organizes files by type. It can copy or move files from one or more folders into a structured target folder, handles duplicate names automatically, and writes a detailed report.

## Features

- GUI and command-line modes
- Multiple source folders in the GUI
- Copy mode by default, so original files are preserved
- Move mode for users who want to clear the source folders
- Duplicate filename handling, such as `photo.jpg`, `photo_1.jpg`, `photo_2.jpg`
- UTF-8 paths and localized UI text
- JSON language packs in `locales/`
- Configurable file categories in `config.json`

## Languages

The default language is English. Included language packs:

- `en` English
- `zh-CN` Simplified Chinese
- `fr` French
- `de` German
- `ja` Japanese

To add another language, copy `locales/en.json` to a new file such as `locales/es.json`, translate the values, and run:

```bash
python file_organizer.py --lang es
```

The app falls back to English for missing translation keys.

## Quick Start

### GUI

```bash
python file_organizer_gui.py
```

On Windows, you can also double-click `start_gui.bat`.

### CLI

```bash
python file_organizer.py
```

Non-interactive example:

```bash
python file_organizer.py --source "C:\Users\You\Downloads" --output "D:\Organized" --copy --yes
```

Use another language:

```bash
python file_organizer.py --lang ja
```

List available languages:

```bash
python file_organizer.py --list-languages
```

## Output Layout

```text
organized/
├── images/
│   ├── jpg/
│   └── png/
├── videos/
│   └── mp4/
├── documents/
│   └── pdf/
└── organizer_report.txt
```

## Configuration

Edit `config.json` to change categories, extensions, default mode, rename separator, hidden-file handling, or default language.

```json
{
  "language": "en",
  "settings": {
    "default_mode": "copy",
    "rename_separator": "_",
    "include_hidden_files": false
  }
}
```

Older configs that use the previous Chinese key names are still accepted.

## Safety Notes

Use copy mode the first time you run the tool. Review the output folder and `organizer_report.txt` before deleting original files. Move mode removes files from the source location after moving them into the target folder.

## Requirements

- Python 3.8 or newer recommended
- Tkinter for the GUI. It is included with most Python installers.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
