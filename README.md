# Instroke: billiard club table timer

An Arduino plus a Windows desktop app that times and bills every table in a billiard club: 14 pool tables, 6 dart boards and 2 snooker tables. Each table has a switch; when staff switch a table on, its timer starts, and when they switch it off, the app shows the bill. Built in 2024 for a real club.

## How it works

```
24 table switches ──> Arduino Mega ──USB serial, 9600 baud──> PyQt5 app (Windows)
                      "<table> <0|1>"                          timers, bills, shift reports
```

**Arduino** (`sketch_jul22a/sketch_jul22a.ino`)

- Reads 24 switches on digital pins 2–25 with the internal pull-ups enabled (pins 22–25 exist only on the Mega 2560).
- Polls every 100 ms, which also debounces the switches, and sends `<table index> <state>` whenever a switch changes.

**Desktop app** (`instroke/program.py`)

- A background thread reads the serial port and passes events to the Qt UI through a signal, so the UI never blocks on I/O.
- A table shows each table's running time and cost, updated every second, using a price per hour set for each table.
- When a table is switched off, the app shows its bill (start, end, duration, cost) and adds it to the shift total.
- At the end of a shift it writes a PDF report (ReportLab) and a JSON record into `reports/<date>/`.
- Table names, prices and the COM port live in `settings_biliard.json` and can be changed from a password-protected admin menu.
- Packaged as a single Windows `.exe` with PyInstaller.

## Run from source

```sh
pip install pyqt5 pyserial reportlab
python instroke/program.py
```

Set the Arduino's COM port in `instroke/settings_biliard.json` or in the admin menu. To build the executable: `pyinstaller instroke/Instroke.spec`.

## Known limitations

This was one of my first real-world projects. Looking back, I would change these things:

- **Message framing:** the Arduino sends no line ending, so Python's `readline()` only returns after its 1-second timeout. If two tables change within the same second, the two messages arrive as one line and are ignored. The fix is `Serial.println` on the Arduino side.
- **Duplicated code:** the app has 24 copies of the billing and price-setting functions, one per table. They should be a single function that takes the table index.
- **Security:** the admin password is hard-coded in the source.
- **Debouncing:** a fixed 100 ms delay works, but per-switch debouncing with timestamps would react faster.
