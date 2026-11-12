# Instroke: billiard club table timer

An Arduino plus a Windows desktop app that times and bills every table in a billiard club: 14 pool tables, 6 dart boards and 2 snooker tables. Each table has a switch; when staff switch a table on, its timer starts, and when they switch it off, the app shows the bill. Built in 2024 for a real club and reworked in 2026.

## How it works

```
24 table switches ──> Arduino Mega ──USB serial, 9600 baud──> PyQt5 app (Windows)
                      "<table> <0|1>\n"                        timers, bills, shift reports
```

**Arduino** (`sketch_jul22a/sketch_jul22a.ino`)

- Reads 24 switches on digital pins 2–25 with the internal pull-ups enabled (pins 22–25 exist only on the Mega 2560).
- Debounces each switch on its own without blocking: a change is reported only after the pin has been stable for 50 ms.
- Sends one newline-terminated message per change: `<table index> <state>`.

**Desktop app** (`instroke/`)

- A background thread only reads and parses serial lines. Each event goes to the GUI thread through a Qt signal, so table data is only ever changed by one thread.
- A table shows each table's running time and cost, updated every second, using a price per hour set for each table and rounded down to 5 cents.
- When a table is switched off, the app shows its bill (start, end, duration, net, VAT, total) and adds it to the shift total.
- At the end of a shift it writes a PDF report (ReportLab) and a JSON record into `reports/<date>/`.
- Table names, prices, the COM port, the VAT rate and the admin password hash live in `settings_biliard.json`. An admin menu changes them.
- Packaged as a single Windows `.exe` with PyInstaller.

`program.py` holds the Qt window. `instroke_core.py` holds everything that can be tested without Qt or a serial port: message parsing, pricing, VAT, password hashing and settings updates.

## Run from source

```sh
pip install pyqt5 pyserial reportlab
python instroke/program.py
```

Set the Arduino's COM port in `instroke/settings_biliard.json` or in the admin menu. On the first admin login after installing, the app asks you to set a password. To build the executable: `cd instroke && pyinstaller Instroke.spec`.

## Tests

```sh
python -m unittest discover -s tests
```

12 tests cover message parsing (including noise and malformed lines), pricing and rounding, the VAT split, duration formatting, password hashing and settings updates.

## What changed in 2026

I revisited this project two years after writing it and fixed the problems I could now see:

| Problem in the 2024 version | Fix |
| --- | --- |
| The Arduino sent no line ending, so the app's `readline()` waited for its 1-second timeout, and two table changes within one second were merged and lost. | The sketch sends `println`; the app parses one line per event. |
| A bad byte, a malformed line, or switching off a table that was already on when the app started raised an exception in the serial thread. The thread died silently and no table was tracked any more. | Parsing is defensive, idle tables ignore "off" events, and a lost connection shows a warning. |
| The serial thread changed table data while the GUI read it. | The thread only emits Qt signals; all state changes happen in the GUI thread. |
| VAT was calculated as 19 % *of* the gross price (8.00 € showed 1.52 € VAT). | VAT is the share *contained in* the gross price, gross × 19/119 (8.00 € → 1.28 € VAT). The rate is configurable. |
| 24 copies each of the bill, price and name functions, plus 200 lines of menu setup. | One function each, taking the table index. `program.py` went from 1,762 to 588 lines. |
| The admin password was hard-coded in the source. | Only a salted PBKDF2-SHA256 hash is stored in the settings file, and the password can be changed from the menu. |
| Debouncing with `delay(100)` on all switches at once. | Per-switch, non-blocking debouncing with `millis()`. |
| Settings were rewritten in place, so a crash mid-write could corrupt them. | Written to a temporary file, then swapped in atomically. |
| A fresh install crashed when the `reports` folder did not exist yet. | The folder is created on start. |
