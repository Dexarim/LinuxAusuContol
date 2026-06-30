# Translations for ASUS Control GUI

This folder contains translation source files (`.ts`) and compiled translation binaries (`.qm`) for the desktop GUI.

## Translation Workflow

### 1. Extract strings from source code into a `.ts` file:
To update or create a Russian translation file:
```bash
.venv/bin/pyside6-lupdate asus_control/gui/*.py -ts asus_control/gui/translations/asus-control_ru.ts
```

### 2. Translate strings:
Open the generated `asus-control_ru.ts` file in **Qt Linguist** to translate the strings, then save it.

### 3. Compile the `.ts` file into a `.qm` file:
```bash
.venv/bin/pyside6-lrelease asus_control/gui/translations/asus-control_ru.ts
```
The resulting `asus-control_ru.qm` file will be loaded automatically by the GUI if the system language is set to Russian.
