import sys
import os
import PyQt5.QtCore
import PyQt5.QtWidgets
import serial
import time
import datetime
import threading
import PyQt5
from PyQt5.QtWidgets import QApplication, QLabel, QMainWindow, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, QHeaderView, QMenuBar, QAction, QInputDialog, QMessageBox
from PyQt5.QtCore import QTimer, QTime, Qt
import json
import shutil
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from PyQt5.QtGui import QIcon
from instroke_core import (TABLE_COUNT, DEFAULT_VAT_RATE, parse_switch_message, cost_for,
                           vat_breakdown, format_duration, hash_password, verify_password,
                           load_settings, update_settings)

table_names = []
table_prices = []
comport = []
brojac = []


if getattr(sys, 'frozen', False):
    #Ako je pretvoreno u .exe
    current_directory = os.path.dirname(sys.executable)
else:
    #Ako se skripta pokreće direktno iz Python interpretera
    current_directory = os.path.dirname(os.path.abspath(__file__))
path_settings_json = os.path.join(current_directory, 'settings_biliard.json')
reports_directory = os.path.join(current_directory, 'reports')
ikonica = os.path.join(current_directory, 'pool.ico')

datumi = []
trenutno_vrijeme = datetime.datetime.now()
danas_vrijeme = trenutno_vrijeme - datetime.timedelta(hours=5)
datumi.append(danas_vrijeme.strftime("%d-%m-%Y"))
juce_vrijeme = danas_vrijeme - datetime.timedelta(days=1)
datumi.append(juce_vrijeme.strftime("%d-%m-%Y"))
prekjuce_vrijeme = danas_vrijeme - datetime.timedelta(days=2)
datumi.append(prekjuce_vrijeme.strftime("%d-%m-%Y"))
pocetni_tms = trenutno_vrijeme.strftime('%H-%M-%S')

class SwitchMonitor(QMainWindow):
    # Events from the serial thread are handed to the GUI thread through these signals,
    # so all table data is only ever touched by one thread.
    switch_event = PyQt5.QtCore.pyqtSignal(int, int)
    serial_error = PyQt5.QtCore.pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.logged_in = False
        self.smjena = 0
        self.can_close = True
        self.vat_rate = load_settings(path_settings_json).get("vat_rate", DEFAULT_VAT_RATE)
        self.switch_data = {i: {"name": table_names[i], "start_time": None, "duration": 0, "cost_per_hour": table_prices[i], "total_cost": 0, "total_cost_today": 0, 'active': False} for i in range(TABLE_COUNT)}
        self.last_bill = {i: {"name": table_names[i], "start_time": 0, "duration": 0, "end_time": 0, "cost": 0} for i in range(TABLE_COUNT)}
        self.initUI()
        self.switch_event.connect(self.on_switch_event)
        self.serial_error.connect(self.on_serial_error)
        self.comport = comport[0]
        try:
            self.initSerial()
        except Exception:
            QMessageBox.information(self, "Wrong comport", f"Current comport is: {comport[0]}")
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_table)
        self.timer.start(1000)


    def initUI(self):
        self.setWindowTitle('Instroke')
        self.setWindowIcon(QIcon(ikonica))
        self.setGeometry(100, 100, 800, 600)
        self.setStyleSheet("""
                            QWidget{
                                background-color: #000000;
                                color: #ffffff;
                                font: bold 24px;
                            }
                            QMenuBar::item:selected{
                                background-color: #ffffff;
                                color: #000000
                            }
                            QMenu::item:selected{
                                background-color: #ffffff;
                                color: #000000
                            }
                            """)

        self.tableWidget = QTableWidget()
        self.tableWidget.setRowCount(24)
        self.tableWidget.setColumnCount(5)
        self.tableWidget.verticalHeader().setVisible(False)
        self.tableWidget.setHorizontalHeaderLabels(["Tisch", "Start", "Dauer (h:m:s)", "€/Std", "Gesamtsumme"])
        self.tableWidget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tableWidget.setEditTriggers(PyQt5.QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tableWidget.setSelectionMode(PyQt5.QtWidgets.QAbstractItemView.SingleSelection)
        self.tableWidget.setSelectionBehavior(PyQt5.QtWidgets.QAbstractItemView.SelectRows)
        self.tableWidget.setStyleSheet("""
                                       QTableWidget{
                                       background-color: #000000;
                                       color: #ffffff;
                                       font-size: 24pt;
                                       border: 2px solid #ffffff}

                                       QHeaderView::section{
                                       background-color: #000000;
                                       color: #ffffff}

                                       QTableWidget::item{
                                       background-color: #000000;
                                       color: #ffffff
                                       }
                                       QTableWidget::item:selected{
                                       background-color: #ffffff;
                                       color: #000000;
                                       }
                                       """)
        
        
        self.tableWidget.itemSelectionChanged.connect(self.highlight_selected_row)
        
        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.tableWidget)
        
        container = QWidget()
        container.setLayout(mainLayout)
        self.setCentralWidget(container)

        self.menuBar = self.menuBar()
        self.createMenu()

        self.clock_label = QLabel()
        self.clock_label.setStyleSheet("font-size: 20px; color: white;")
        self.menuBar.setCornerWidget(self.clock_label, corner=1)
        
        #tajmer da apdejtuje sat svaki sekund
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start(1000)  # Update every second

        #inicijalizacija
        self.update_clock()
        
    def highlight_selected_row(self):
        selected_indexes = self.tableWidget.selectedIndexes()
        if not selected_indexes:
            return
        
        selected_row = selected_indexes[0].row()
        
        #primijeni drugi stil
        for column in range(self.tableWidget.columnCount()):
            item = self.tableWidget.item(selected_row, column)
            item.setBackground(Qt.white)
            item.setForeground(Qt.white)

    def closeEvent(self, event):
        if not self.can_close:
            QMessageBox.warning(self, 'Warnung', 'Das Programm kann nicht geschlossen werden, solange die Tische aktiv sind.')
            event.ignore()
            return

        reply = QMessageBox.question(self, 'Schliessen',
                                     'Sind Sie sicher, dass Sie beenden moechten?',
                                     QMessageBox.Yes | QMessageBox.No,
                                     QMessageBox.No)

        if reply == QMessageBox.Yes:
            self.custom_cleanup_function()
            self.display_report()
            event.accept()
        else:
            event.ignore()

    def display_report(self):
        trenutacno_vrijeme = datetime.datetime.now()
        krajnji_tms = trenutacno_vrijeme.strftime('%H-%M-%S')
        vrijednost = self.smjena
        QMessageBox.information(self, "Schicht Bericht", f"Start: {pocetni_tms}\nStop: {krajnji_tms}\nGesamtsumme: {vrijednost:.2f}€")
    
    def custom_cleanup_function(self):
        trenutacno_vrijeme = datetime.datetime.now()
        krajnji_tms = trenutacno_vrijeme.strftime('%H-%M-%S')
        vrijednost = self.smjena
        folder_path = os.path.join(reports_directory, datumi[0])
        name_str = '#' + str(brojac[0]) + ' ' + pocetni_tms + '.pdf'
        name_json = '#' + str(brojac[0]) + ' ' + pocetni_tms + '.json'
        jsonfilename= os.path.join(folder_path, name_json)
        filename = os.path.join(folder_path, name_str)
        c = canvas.Canvas(filename, pagesize=letter)

        c.setTitle(f"Bericht {brojac[0]}")

        text = c.beginText(100, 750)
        text.setFont("Helvetica", 12)

        text.textLine(f"Bericht #{brojac[0]}")
        text.textLine(f"Start: {pocetni_tms}")
        text.textLine(f"Gesamtsumme: {vrijednost:.2f}€")
        text.textLine(f"Ende: {krajnji_tms}")

        c.drawText(text)
        c.save()

        data = {
            "id": brojac[0],
            "start": pocetni_tms,
            "finish": krajnji_tms,
            "price": vrijednost
        }
        with open(jsonfilename, 'w') as json_file:
            json.dump(data, json_file, indent=4)




    def update_clock(self):
        current_time = QTime.currentTime().toString('hh:mm:ss')
        self.clock_label.setText(current_time)

    # ---------- Admin login and password ----------

    def show_login_dialog(self):
        record = load_settings(path_settings_json).get("admin_password")
        if record is None:
            # First start after the update: no password stored yet, so the admin sets one now.
            QMessageBox.information(self, "Anmelden", "Es ist noch kein Passwort gesetzt. Bitte legen Sie jetzt ein Passwort fest.")
            if not self.set_new_password():
                return
        else:
            text, ok = QInputDialog.getText(self, "Anmelden", "Geben Sie Ihr Passwort ein:", PyQt5.QtWidgets.QLineEdit.Password)
            if not ok:
                return
            if not verify_password(text, record):
                QMessageBox.warning(self, "Anmelden", "Falsches Passwort!")
                return
        self.logged_in = True
        QMessageBox.information(self, "Anmelden", "Anmeldung erfolgreich!")
        self.update_menu_bar()

    def set_new_password(self):
        """Ask for a new password twice and store only its salted hash. Returns True if saved."""
        first, ok = QInputDialog.getText(self, "Passwort", "Neues Passwort (mindestens 6 Zeichen):", PyQt5.QtWidgets.QLineEdit.Password)
        if not ok:
            return False
        if len(first) < 6:
            QMessageBox.warning(self, "Passwort", "Das Passwort muss mindestens 6 Zeichen haben.")
            return False
        second, ok = QInputDialog.getText(self, "Passwort", "Neues Passwort wiederholen:", PyQt5.QtWidgets.QLineEdit.Password)
        if not ok:
            return False
        if first != second:
            QMessageBox.warning(self, "Passwort", "Die Passwörter stimmen nicht überein.")
            return False
        record = hash_password(first)

        def store(settings):
            settings["admin_password"] = record

        update_settings(path_settings_json, store)
        QMessageBox.information(self, "Passwort", "Das Passwort wurde gespeichert.")
        return True

    # ---------- Menus ----------

    def update_menu_bar(self):
        if not self.logged_in:
            return
        self.menuBar.removeAction(self.login_action)
        self.nameSettingsMenu = self.menuBar.addMenu('Tischnamen einstellen')
        self.costSettingsMenu = self.menuBar.addMenu('Tarif einstellen')
        self.comportMenu = self.menuBar.addMenu('COM port')

        # One menu entry per table; the lambda's default argument fixes i for each entry.
        self.name_actions = []
        self.cost_actions = []
        for i in range(TABLE_COUNT):
            name_action = QAction(table_names[i], self)
            name_action.triggered.connect(lambda checked=False, i=i: self.change_table_name(i))
            self.nameSettingsMenu.addAction(name_action)
            self.name_actions.append(name_action)

            cost_action = QAction(table_names[i], self)
            cost_action.triggered.connect(lambda checked=False, i=i: self.change_table_price(i))
            self.costSettingsMenu.addAction(cost_action)
            self.cost_actions.append(cost_action)

        changeComport = QAction('Change COM port', self)
        changeComport.triggered.connect(lambda checked=False: self.changeComportFunc())
        self.comportMenu.addAction(changeComport)

        self.change_password_action = QAction("Passwort ändern", self)
        self.change_password_action.triggered.connect(lambda checked=False: self.set_new_password())
        self.menuBar.addAction(self.change_password_action)

        self.logout_action = QAction("Abmelden", self)
        self.logout_action.triggered.connect(lambda checked=False: self.logout())
        self.menuBar.addAction(self.logout_action)

    def logout(self):
        self.logged_in = False
        QMessageBox.information(self, "Abmelden", "Sie haben sich erfolgreich abgemeldet!")
        #ukloni menije
        self.menuBar.removeAction(self.nameSettingsMenu.menuAction())
        self.menuBar.removeAction(self.costSettingsMenu.menuAction())
        self.menuBar.removeAction(self.comportMenu.menuAction())
        self.menuBar.removeAction(self.change_password_action)
        self.menuBar.removeAction(self.logout_action)
        #vrati login
        self.menuBar.addAction(self.login_action)

    def createMenu(self):
        lastBill = self.menuBar.addMenu('Letzte Rechnung')
        self.last_bill_actions = []
        for i, name in enumerate(table_names):
            action = QAction(name, self)
            action.triggered.connect(lambda checked=False, i=i: self.show_bill(i))
            lastBill.addAction(action)
            self.last_bill_actions.append(action)

        reportMenu = self.menuBar.addMenu('Berichte')

        self.login_action = QAction("Anmelden", self)
        self.login_action.triggered.connect(lambda checked=False: self.show_login_dialog())
        self.menuBar.addAction(self.login_action)

        todayAction = QAction('Schicht Bericht', self)
        todayAction.triggered.connect(self.showTodayShiftTotal)
        reportMenu.addAction(todayAction)

        danasTotal = QAction('Heutiges Bericht', self)
        danasTotal.triggered.connect(self.showDanasTotal)
        reportMenu.addAction(danasTotal)

        JuceTotal = QAction('Gestriges Bericht', self)
        JuceTotal.triggered.connect(self.showJuceTotal)
        reportMenu.addAction(JuceTotal)

        pJuceTotal = QAction('Bericht vor 2 Tagen', self)
        pJuceTotal.triggered.connect(self.showPJuceTotal)
        reportMenu.addAction(pJuceTotal)

        individualAction = QAction('Einzeltisch Bericht', self)
        individualAction.triggered.connect(self.showIndividualTotals)
        reportMenu.addAction(individualAction)

    # ---------- Bills ----------

    def show_bill(self, i):
        """Show the last bill of table i: one function for all 24 tables."""
        bill = self.last_bill[i]
        if bill["end_time"] == 0:
            QMessageBox.information(self, "Letzte Rechnung", f"{bill['name']}: noch keine Rechnung.")
            return
        price = bill["cost"]
        net, vat = vat_breakdown(price, self.vat_rate)

        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("Ende")
        message = (f"{bill['name']}<br>"
                f"Start: {bill['start_time']} - Ende: {bill['end_time']}<br>"
                f"Dauer: {bill['duration']}<br>"
                f"Ohne MwSt: {net:.2f}€<br>"
                f"MwSt {self.vat_rate * 100:g}%: {vat:.2f}€<br>"
                "--------------------<br>"
                f"<span style='font-size: 40px;'>Gesamtsumme: {price:.2f}€</span>")
        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.exec_()

    # ---------- Serial input ----------

    def initSerial(self):
        self.ser = serial.Serial(comport[0], 9600, timeout=1)
        self.serial_thread = threading.Thread(target=self.read_serial, daemon=True)
        self.serial_thread.start()

    def read_serial(self):
        """Runs in a background thread. Only reads and parses; the GUI thread does the rest."""
        while True:
            try:
                line = self.ser.readline()
            except serial.SerialException as e:
                self.serial_error.emit(str(e))
                return
            event = parse_switch_message(line)
            if event is not None:
                self.switch_event.emit(*event)

    def on_serial_error(self, message):
        QMessageBox.warning(self, "Verbindung verloren",
                            f"Die Verbindung zum Arduino wurde unterbrochen ({message}).\n"
                            "Bitte das Kabel prüfen und das Programm neu starten.")

    def on_switch_event(self, i, state):
        table = self.switch_data[i]
        if state == 1:
            if table['start_time'] is None:
                table['start_time'] = time.time()
                table['active'] = True
                self.can_close = False
            return

        if table['start_time'] is None:
            # Switched off while not running, e.g. it was already on when the program started.
            return

        start_time = table['start_time']
        end_time = time.time()
        cost = cost_for(table['cost_per_hour'], end_time - start_time)

        self.last_bill[i] = {
            "name": table['name'],
            "start_time": time.strftime('%H:%M:%S', time.localtime(start_time)),
            "end_time": time.strftime('%H:%M:%S', time.localtime(end_time)),
            "duration": format_duration(end_time - start_time),
            "cost": cost,
        }
        table['total_cost'] = cost
        table['total_cost_today'] += cost
        table['active'] = False
        table['start_time'] = None
        table['duration'] = "-"
        self.smjena += cost
        self.can_close = all(not t["active"] for t in self.switch_data.values())
        self.show_bill(i)

    def update_table(self):
        now = time.time()
        for i in range(TABLE_COUNT):
            table = self.switch_data[i]
            start_time = table['start_time']
            cost_per_hour = table['cost_per_hour']

            if start_time:
                activation_time = time.strftime('%H:%M:%S', time.localtime(start_time))
                duration_str = format_duration(now - start_time)
                table['duration'] = duration_str
                total_cost = cost_for(cost_per_hour, now - start_time)
                table['total_cost'] = total_cost
                total_text = f"{total_cost:.2f}"
            else:
                activation_time = "-"
                duration_str = "-"
                total_text = "-"

            self.tableWidget.setItem(i, 0, QTableWidgetItem(table['name']))
            self.tableWidget.setItem(i, 1, QTableWidgetItem(activation_time))
            self.tableWidget.setItem(i, 2, QTableWidgetItem(duration_str))
            self.tableWidget.setItem(i, 3, QTableWidgetItem(f"{cost_per_hour:.2f}"))
            self.tableWidget.setItem(i, 4, QTableWidgetItem(total_text))

    # ---------- Settings (admin only) ----------

    def change_table_price(self, i):
        number, ok = QInputDialog.getDouble(self, table_names[i], 'Tarif wechseln:', value=table_prices[i], min=1, decimals=2)
        if ok and number:
            table_prices[i] = number
            self.switch_data[i]["cost_per_hour"] = number

            def store(settings):
                settings["prices"][i] = number

            update_settings(path_settings_json, store)

    def change_table_name(self, i):
        text, ok = QInputDialog.getText(self, table_names[i], 'Name ändern:', text=table_names[i])
        if ok and text:
            table_names[i] = text
            self.switch_data[i]["name"] = text
            for actions in (self.last_bill_actions, self.name_actions, self.cost_actions):
                actions[i].setText(text)

            def store(settings):
                settings["names"][i] = text

            update_settings(path_settings_json, store)

    def changeComportFunc(self):
        text, ok = QInputDialog.getText(self, 'Change COM port', 'Change COM port:', text=self.comport)
        if ok and text:
            self.comport = text
            comport[0] = text

            def store(settings):
                settings["comport"] = text

            update_settings(path_settings_json, store)
            QMessageBox.information(self, "COM port change occured", "COM port has been changed, please restart program")


    def showTodayShiftTotal(self):
        total_cost = self.smjena
        QMessageBox.information(self, "Schicht Bericht", f"Schicht Bericht: {total_cost:.2f}€")

    def showDanasTotal(self):
        suma = self.smjena
        directory = os.path.join(reports_directory, datumi[0])
        for filename in os.listdir(directory):
            if filename.endswith('.json'):
                filepath = os.path.join(directory, filename)
                with open(filepath, 'r', encoding='utf-8') as file:
                    data = json.load(file)
                    suma += data["price"]
        suma = round(suma, 2)
        QMessageBox.information(self, "Heutiges Bericht", f"Heutiges Bericht: {suma:.2f}€")

    def showJuceTotal(self):
        sumaj = 0
        directory = os.path.join(reports_directory, datumi[1])
        if os.path.exists(directory):
            for filename in os.listdir(directory):
                if filename.endswith('.json'):
                    filepath = os.path.join(directory, filename)
                    with open(filepath, 'r', encoding='utf-8') as file:
                        data = json.load(file)
                        sumaj += data["price"]
        sumaj = round(sumaj, 2)
        QMessageBox.information(self, "Gestriges Bericht", f"Gestriges Bericht: {sumaj:.2f}€")

    def showPJuceTotal(self):
        sumapj = 0
        directory = os.path.join(reports_directory, datumi[2])
        if os.path.exists(directory):
            for filename in os.listdir(directory):
                if filename.endswith('.json'):
                    filepath = os.path.join(directory, filename)
                    with open(filepath, 'r', encoding='utf-8') as file:
                        data = json.load(file)
                        sumapj += data["price"]
        sumapj = round(sumapj, 2)
        QMessageBox.information(self, "Bericht vor 2 Tagen", f"Bericht vor 2 Tagen: {sumapj:.2f}€")

    def showIndividualTotals(self):
        totals = "\n".join([f"{self.switch_data[i]['name']}: {self.switch_data[i]['total_cost_today']:.2f}€" for i in range(24)])
        QMessageBox.information(self, "Einzeltisch Bericht", totals)

def delete_unmatched_folders():
    items = os.listdir(reports_directory)
    
    for item in items:
        #konstruisi cijeli path
        item_path = os.path.join(reports_directory, item)
        
        #provjeri je li item u dir
        if os.path.isdir(item_path):
            #ukloni folder
            if item not in datumi:
                shutil.rmtree(item_path)

def check_and_create_folder():
    folder_path = os.path.join(reports_directory, datumi[0])
    
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

def main():
    with open(path_settings_json, 'r') as f:
        fajl = json.load(f)
    comport.append(fajl["comport"])
    brojac.append(fajl["brojac"])
    brojac[0] += 1
    if brojac[0] > 99999:
        brojac[0] = 0
    for i in range(24):
        table_names.append(fajl["names"][i])
        table_prices.append(fajl["prices"][i])
    fajl["brojac"] = brojac[0]
    with open(path_settings_json, 'w') as f:
        json.dump(fajl, f)
    os.makedirs(reports_directory, exist_ok=True)  # first start on a new PC: no reports folder yet
    delete_unmatched_folders()
    check_and_create_folder()

    app = QApplication(sys.argv)
    window = SwitchMonitor()
    window.showMaximized()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
