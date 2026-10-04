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
    message_signal = PyQt5.QtCore.pyqtSignal(int, float)

    def __init__(self):
        self.password = "admin123"  #password
        self.logged_in = False
        self.smjena = 0
        self.can_close = True
        super().__init__()
        self.initUI()
        self.message_signal.connect(self.show_finish_message)
        try:
            self.initSerial()
        except:
            QMessageBox.information(self, "Wrong comport", f"Current comport is: {comport[0]}")
        self.comport = comport[0]
        self.switch_data = {i: {"name": table_names[i], "start_time": None, "duration": 0, "cost_per_hour": table_prices[i], "total_cost": 0, "total_cost_today": 0, 'active': False} for i in range(24)}
        self.last_bill = {i: {"name": table_names[i], "start_time": 0, "duration": 0, "end_time": 0, "cost": 0} for i in range(24)}
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

    def show_login_dialog(self):
        text, ok = QInputDialog.getText(self, "Anmelden", "Geben Sie Ihr Passwort ein:", PyQt5.QtWidgets.QLineEdit.Password)

        if ok and text == self.password:
            self.logged_in = True
            QMessageBox.information(self, "Anmelden", "Anmeldung erfolgreich!")
            self.update_menu_bar()
        elif ok:
            QMessageBox.warning(self, "Anmelden", "Falsches Passwort!")

    def update_menu_bar(self):
        if self.logged_in:
            self.menuBar.removeAction(self.login_action)
            self.nameSettingsMenu = self.menuBar.addMenu('Tischnamen einstellen')
            self.costSettingsMenu = self.menuBar.addMenu('Tarif einstellen')
            self.comportMenu = self.menuBar.addMenu('COM port')

            '''pocetak'''

            buttonOneCost = QAction(table_names[0], self)
            buttonOneCost.triggered.connect(self.tableOneCostSettings)
            self.costSettingsMenu.addAction(buttonOneCost)

            buttonTwoCost = QAction(table_names[1], self)
            buttonTwoCost.triggered.connect(self.tableTwoCostSettings)
            self.costSettingsMenu.addAction(buttonTwoCost)

            buttonThreeCost = QAction(table_names[2], self)
            buttonThreeCost.triggered.connect(self.tableThreeCostSettings)
            self.costSettingsMenu.addAction(buttonThreeCost)

            buttonFourCost = QAction(table_names[3], self)
            buttonFourCost.triggered.connect(self.tableFourCostSettings)
            self.costSettingsMenu.addAction(buttonFourCost)

            buttonFiveCost = QAction(table_names[4], self)
            buttonFiveCost.triggered.connect(self.tableFiveCostSettings)
            self.costSettingsMenu.addAction(buttonFiveCost)

            buttonSixCost = QAction(table_names[5], self)
            buttonSixCost.triggered.connect(self.tableSixCostSettings)
            self.costSettingsMenu.addAction(buttonSixCost)

            buttonSevenCost = QAction(table_names[6], self)
            buttonSevenCost.triggered.connect(self.tableSevenCostSettings)
            self.costSettingsMenu.addAction(buttonSevenCost)

            buttonEightCost = QAction(table_names[7], self)
            buttonEightCost.triggered.connect(self.tableEightCostSettings)
            self.costSettingsMenu.addAction(buttonEightCost)

            buttonNineCost = QAction(table_names[8], self)
            buttonNineCost.triggered.connect(self.tableNineCostSettings)
            self.costSettingsMenu.addAction(buttonNineCost)

            buttonTenCost = QAction(table_names[9], self)
            buttonTenCost.triggered.connect(self.tableTenCostSettings)
            self.costSettingsMenu.addAction(buttonTenCost)

            buttonElevenCost = QAction(table_names[10], self)
            buttonElevenCost.triggered.connect(self.tableElevenCostSettings)
            self.costSettingsMenu.addAction(buttonElevenCost)

            buttonTwelveCost = QAction(table_names[11], self)
            buttonTwelveCost.triggered.connect(self.tableTwelveCostSettings)
            self.costSettingsMenu.addAction(buttonTwelveCost)

            buttonOneThreeCost = QAction(table_names[12], self)
            buttonOneThreeCost.triggered.connect(self.tableOneThreeCostSettings)
            self.costSettingsMenu.addAction(buttonOneThreeCost)

            buttonOneFourCost = QAction(table_names[13], self)
            buttonOneFourCost.triggered.connect(self.tableOneFourCostSettings)
            self.costSettingsMenu.addAction(buttonOneFourCost)

            buttonOneFiveCost = QAction(table_names[14], self)
            buttonOneFiveCost.triggered.connect(self.tableOneFiveCostSettings)
            self.costSettingsMenu.addAction(buttonOneFiveCost)

            buttonOneSixCost = QAction(table_names[15], self)
            buttonOneSixCost.triggered.connect(self.tableOneSixCostSettings)
            self.costSettingsMenu.addAction(buttonOneSixCost)

            buttonOneSevenCost = QAction(table_names[16], self)
            buttonOneSevenCost.triggered.connect(self.tableOneSevenCostSettings)
            self.costSettingsMenu.addAction(buttonOneSevenCost)

            buttonOneEightCost = QAction(table_names[17], self)
            buttonOneEightCost.triggered.connect(self.tableOneEightCostSettings)
            self.costSettingsMenu.addAction(buttonOneEightCost)

            buttonOneNineCost = QAction(table_names[18], self)
            buttonOneNineCost.triggered.connect(self.tableOneNineCostSettings)
            self.costSettingsMenu.addAction(buttonOneNineCost)

            buttonTwoZeroCost = QAction(table_names[19], self)
            buttonTwoZeroCost.triggered.connect(self.tableTwoZeroCostSettings)
            self.costSettingsMenu.addAction(buttonTwoZeroCost)

            buttonTwoOneCost = QAction(table_names[20], self)
            buttonTwoOneCost.triggered.connect(self.tableTwoOneCostSettings)
            self.costSettingsMenu.addAction(buttonTwoOneCost)

            buttonTwoTwoCost = QAction(table_names[21], self)
            buttonTwoTwoCost.triggered.connect(self.tableTwoTwoCostSettings)
            self.costSettingsMenu.addAction(buttonTwoTwoCost)

            buttonTwoThreeCost = QAction(table_names[22], self)
            buttonTwoThreeCost.triggered.connect(self.tableTwoThreeCostSettings)
            self.costSettingsMenu.addAction(buttonTwoThreeCost)

            buttonTwoFourCost = QAction(table_names[23], self)
            buttonTwoFourCost.triggered.connect(self.tableTwoFourCostSettings)
            self.costSettingsMenu.addAction(buttonTwoFourCost)

            '''kraj'''

            changeComport = QAction('Change COM port', self)
            changeComport.triggered.connect(self.changeComportFunc)
            self.comportMenu.addAction(changeComport)

            buttonOne = QAction(table_names[0], self)
            buttonOne.triggered.connect(self.tableOneSettings)
            self.nameSettingsMenu.addAction(buttonOne)

            buttonTwo = QAction(table_names[1], self)
            buttonTwo.triggered.connect(self.tableTwoSettings)
            self.nameSettingsMenu.addAction(buttonTwo)

            buttonThree = QAction(table_names[2], self)
            buttonThree.triggered.connect(self.tableThreeSettings)
            self.nameSettingsMenu.addAction(buttonThree)

            buttonFour = QAction(table_names[3], self)
            buttonFour.triggered.connect(self.tableFourSettings)
            self.nameSettingsMenu.addAction(buttonFour)

            buttonFive = QAction(table_names[4], self)
            buttonFive.triggered.connect(self.tableFiveSettings)
            self.nameSettingsMenu.addAction(buttonFive)

            buttonSix = QAction(table_names[5], self)
            buttonSix.triggered.connect(self.tableSixSettings)
            self.nameSettingsMenu.addAction(buttonSix)

            buttonSeven = QAction(table_names[6], self)
            buttonSeven.triggered.connect(self.tableSevenSettings)
            self.nameSettingsMenu.addAction(buttonSeven)

            buttonEight = QAction(table_names[7], self)
            buttonEight.triggered.connect(self.tableEightSettings)
            self.nameSettingsMenu.addAction(buttonEight)

            buttonNine = QAction(table_names[8], self)
            buttonNine.triggered.connect(self.tableNineSettings)
            self.nameSettingsMenu.addAction(buttonNine)

            buttonTen = QAction(table_names[9], self)
            buttonTen.triggered.connect(self.tableTenSettings)
            self.nameSettingsMenu.addAction(buttonTen)

            buttonEleven = QAction(table_names[10], self)
            buttonEleven.triggered.connect(self.tableElevenSettings)
            self.nameSettingsMenu.addAction(buttonEleven)

            buttonTwelve = QAction(table_names[11], self)
            buttonTwelve.triggered.connect(self.tableTwelveSettings)
            self.nameSettingsMenu.addAction(buttonTwelve)

            buttonOneThree = QAction(table_names[12], self)
            buttonOneThree.triggered.connect(self.tableOneThreeSettings)
            self.nameSettingsMenu.addAction(buttonOneThree)

            buttonOneFour = QAction(table_names[13], self)
            buttonOneFour.triggered.connect(self.tableOneFourSettings)
            self.nameSettingsMenu.addAction(buttonOneFour)

            buttonOneFive = QAction(table_names[14], self)
            buttonOneFive.triggered.connect(self.tableOneFiveSettings)
            self.nameSettingsMenu.addAction(buttonOneFive)

            buttonOneSix = QAction(table_names[15], self)
            buttonOneSix.triggered.connect(self.tableOneSixSettings)
            self.nameSettingsMenu.addAction(buttonOneSix)

            buttonOneSeven = QAction(table_names[16], self)
            buttonOneSeven.triggered.connect(self.tableOneSevenSettings)
            self.nameSettingsMenu.addAction(buttonOneSeven)

            buttonOneEight = QAction(table_names[17], self)
            buttonOneEight.triggered.connect(self.tableOneEightSettings)
            self.nameSettingsMenu.addAction(buttonOneEight)

            buttonOneNine = QAction(table_names[18], self)
            buttonOneNine.triggered.connect(self.tableOneNineSettings)
            self.nameSettingsMenu.addAction(buttonOneNine)

            buttonTwoZero = QAction(table_names[19], self)
            buttonTwoZero.triggered.connect(self.tableTwoZeroSettings)
            self.nameSettingsMenu.addAction(buttonTwoZero)

            buttonTwoOne = QAction(table_names[20], self)
            buttonTwoOne.triggered.connect(self.tableTwoOneSettings)
            self.nameSettingsMenu.addAction(buttonTwoOne)

            buttonTwoTwo = QAction(table_names[21], self)
            buttonTwoTwo.triggered.connect(self.tableTwoTwoSettings)
            self.nameSettingsMenu.addAction(buttonTwoTwo)

            buttonTwoThree = QAction(table_names[22], self)
            buttonTwoThree.triggered.connect(self.tableTwoThreeSettings)
            self.nameSettingsMenu.addAction(buttonTwoThree)

            buttonTwoFour = QAction(table_names[23], self)
            buttonTwoFour.triggered.connect(self.tableTwoFourSettings)
            self.nameSettingsMenu.addAction(buttonTwoFour)

            self.logout_action = QAction("Abmelden", self)
            self.logout_action.triggered.connect(self.logout)
            self.menuBar.addAction(self.logout_action)

    def logout(self):
        self.logged_in = False
        QMessageBox.information(self, "Abmelden", "Sie haben sich erfolgreich Abgemelded!")

        #ukloni menije
        self.menuBar.removeAction(self.nameSettingsMenu.menuAction())
        self.menuBar.removeAction(self.costSettingsMenu.menuAction())
        self.menuBar.removeAction(self.comportMenu.menuAction())
        self.menuBar.removeAction(self.logout_action)

        #vrati login
        self.menuBar.addAction(self.login_action)

    def createMenu(self):
        lastBill = self.menuBar.addMenu('Letzte Rechnung')

        for i, name in enumerate(table_names):
            action = QAction(name, self)
            action.triggered.connect(getattr(self, f'table_{i + 1}_bill'))
            lastBill.addAction(action)

        reportMenu = self.menuBar.addMenu('Berichte')

        self.login_action = QAction("Anmelden", self)
        self.login_action.triggered.connect(self.show_login_dialog)

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

    def table_1_bill(self):
        price = self.last_bill[0]["cost"]
        pdv = round(price * 0.19, 2)
        bez_pdv = round(price-pdv, 2)
        
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("Ende")
        
        #definisi poruku
        message = (f"{self.last_bill[0]['name']}<br>"
                f"Start: {self.last_bill[0]['start_time']} - Ende: {self.last_bill[0]['end_time']}<br>"
                f"Dauer: {self.last_bill[0]['duration']}<br>"
                f"Ohne MwSt: {bez_pdv:.2f}€<br>"
                f"MwSt 19%: {pdv:.2f}€<br>"
                "--------------------<br>"
                f"<span style='font-size: 40px;'>Gesamtsumme: {price:.2f}€</span>")

        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Ok)

        #stylesheet za novi message box

        #prikazi message box
        msg_box.exec_()

    def table_2_bill(self):
        price = self.last_bill[1]["cost"]
        pdv = round(price * 0.19, 2)
        bez_pdv = round(price-pdv, 2)
        
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("Ende")

        message = (f"{self.last_bill[1]['name']}<br>"
                f"Start: {self.last_bill[1]['start_time']} - Ende: {self.last_bill[1]['end_time']}<br>"
                f"Dauer: {self.last_bill[1]['duration']}<br>"
                f"Ohne MwSt: {bez_pdv:.2f}€<br>"
                f"MwSt 19%: {pdv:.2f}€<br>"
                "--------------------<br>"
                f"<span style='font-size: 40px;'>Gesamtsumme: {price:.2f}€</span>")

        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Ok)

        #stylesheet za novi message box

        #prikazi message box
        msg_box.exec_()

    def table_3_bill(self):
        price = self.last_bill[2]["cost"]
        pdv = round(price * 0.19, 2)
        bez_pdv = round(price-pdv, 2)
        
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("Ende")

        message = (f"{self.last_bill[2]['name']}<br>"
                f"Start: {self.last_bill[2]['start_time']} - Ende: {self.last_bill[2]['end_time']}<br>"
                f"Dauer: {self.last_bill[2]['duration']}<br>"
                f"Ohne MwSt: {bez_pdv:.2f}€<br>"
                f"MwSt 19%: {pdv:.2f}€<br>"
                "--------------------<br>"
                f"<span style='font-size: 40px;'>Gesamtsumme: {price:.2f}€</span>")

        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Ok)

        #stylesheet za novi message box

        #prikazi message box
        msg_box.exec_()

    def table_4_bill(self):
        price = self.last_bill[3]["cost"]
        pdv = round(price * 0.19, 2)
        bez_pdv = round(price-pdv, 2)
        
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("Ende")

        message = (f"{self.last_bill[3]['name']}<br>"
                f"Start: {self.last_bill[3]['start_time']} - Ende: {self.last_bill[3]['end_time']}<br>"
                f"Dauer: {self.last_bill[3]['duration']}<br>"
                f"Ohne MwSt: {bez_pdv:.2f}€<br>"
                f"MwSt 19%: {pdv:.2f}€<br>"
                "--------------------<br>"
                f"<span style='font-size: 40px;'>Gesamtsumme: {price:.2f}€</span>")

        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Ok)

        msg_box.exec_()

    def table_5_bill(self):
        price = self.last_bill[4]["cost"]
        pdv = round(price * 0.19, 2)
        bez_pdv = round(price-pdv, 2)
        
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("Ende")

        message = (f"{self.last_bill[4]['name']}<br>"
                f"Start: {self.last_bill[4]['start_time']} - Ende: {self.last_bill[4]['end_time']}<br>"
                f"Dauer: {self.last_bill[4]['duration']}<br>"
                f"Ohne MwSt: {bez_pdv:.2f}€<br>"
                f"MwSt 19%: {pdv:.2f}€<br>"
                "--------------------<br>"
                f"<span style='font-size: 40px;'>Gesamtsumme: {price:.2f}€</span>")

        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Ok)

        msg_box.exec_()

    def table_6_bill(self):
        price = self.last_bill[5]["cost"]
        pdv = round(price * 0.19, 2)
        bez_pdv = round(price-pdv, 2)
        
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("Ende")

        message = (f"{self.last_bill[5]['name']}<br>"
                f"Start: {self.last_bill[5]['start_time']} - Ende: {self.last_bill[5]['end_time']}<br>"
                f"Dauer: {self.last_bill[5]['duration']}<br>"
                f"Ohne MwSt: {bez_pdv:.2f}€<br>"
                f"MwSt 19%: {pdv:.2f}€<br>"
                "--------------------<br>"
                f"<span style='font-size: 40px;'>Gesamtsumme: {price:.2f}€</span>")

        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Ok)

        msg_box.exec_()

    def table_7_bill(self):
        price = self.last_bill[6]["cost"]
        pdv = round(price * 0.19, 2)
        bez_pdv = round(price-pdv, 2)
        
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("Ende")

        message = (f"{self.last_bill[6]['name']}<br>"
                f"Start: {self.last_bill[6]['start_time']} - Ende: {self.last_bill[6]['end_time']}<br>"
                f"Dauer: {self.last_bill[6]['duration']}<br>"
                f"Ohne MwSt: {bez_pdv:.2f}€<br>"
                f"MwSt 19%: {pdv:.2f}€<br>"
                "--------------------<br>"
                f"<span style='font-size: 40px;'>Gesamtsumme: {price:.2f}€</span>")

        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Ok)

        msg_box.exec_()

    def table_8_bill(self):
        price = self.last_bill[7]["cost"]
        pdv = round(price * 0.19, 2)
        bez_pdv = round(price-pdv, 2)
        
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("Ende")

        message = (f"{self.last_bill[7]['name']}<br>"
                f"Start: {self.last_bill[7]['start_time']} - Ende: {self.last_bill[7]['end_time']}<br>"
                f"Dauer: {self.last_bill[7]['duration']}<br>"
                f"Ohne MwSt: {bez_pdv:.2f}€<br>"
                f"MwSt 19%: {pdv:.2f}€<br>"
                "--------------------<br>"
                f"<span style='font-size: 40px;'>Gesamtsumme: {price:.2f}€</span>")

        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Ok)

        msg_box.exec_()

    def table_9_bill(self):
        price = self.last_bill[8]["cost"]
        pdv = round(price * 0.19, 2)
        bez_pdv = round(price-pdv, 2)
        
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("Ende")

        message = (f"{self.last_bill[8]['name']}<br>"
                f"Start: {self.last_bill[8]['start_time']} - Ende: {self.last_bill[8]['end_time']}<br>"
                f"Dauer: {self.last_bill[8]['duration']}<br>"
                f"Ohne MwSt: {bez_pdv:.2f}€<br>"
                f"MwSt 19%: {pdv:.2f}€<br>"
                "--------------------<br>"
                f"<span style='font-size: 40px;'>Gesamtsumme: {price:.2f}€</span>")

        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Ok)

        msg_box.exec_()

    def table_10_bill(self):
        price = self.last_bill[9]["cost"]
        pdv = round(price * 0.19, 2)
        bez_pdv = round(price-pdv, 2)
        
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("Ende")

        message = (f"{self.last_bill[9]['name']}<br>"
                f"Start: {self.last_bill[9]['start_time']} - Ende: {self.last_bill[9]['end_time']}<br>"
                f"Dauer: {self.last_bill[9]['duration']}<br>"
                f"Ohne MwSt: {bez_pdv:.2f}€<br>"
                f"MwSt 19%: {pdv:.2f}€<br>"
                "--------------------<br>"
                f"<span style='font-size: 40px;'>Gesamtsumme: {price:.2f}€</span>")

        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Ok)

        msg_box.exec_()

    def table_11_bill(self):
        price = self.last_bill[10]["cost"]
        pdv = round(price * 0.19, 2)
        bez_pdv = round(price-pdv, 2)
        
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("Ende")

        message = (f"{self.last_bill[10]['name']}<br>"
                f"Start: {self.last_bill[10]['start_time']} - Ende: {self.last_bill[10]['end_time']}<br>"
                f"Dauer: {self.last_bill[10]['duration']}<br>"
                f"Ohne MwSt: {bez_pdv:.2f}€<br>"
                f"MwSt 19%: {pdv:.2f}€<br>"
                "--------------------<br>"
                f"<span style='font-size: 40px;'>Gesamtsumme: {price:.2f}€</span>")

        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Ok)

        msg_box.exec_()

    def table_12_bill(self):
        price = self.last_bill[11]["cost"]
        pdv = round(price * 0.19, 2)
        bez_pdv = round(price-pdv, 2)
        
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("Ende")

        message = (f"{self.last_bill[11]['name']}<br>"
                f"Start: {self.last_bill[11]['start_time']} - Ende: {self.last_bill[11]['end_time']}<br>"
                f"Dauer: {self.last_bill[11]['duration']}<br>"
                f"Ohne MwSt: {bez_pdv:.2f}€<br>"
                f"MwSt 19%: {pdv:.2f}€<br>"
                "--------------------<br>"
                f"<span style='font-size: 40px;'>Gesamtsumme: {price:.2f}€</span>")

        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Ok)

        msg_box.exec_()

    def table_13_bill(self):
        price = self.last_bill[12]["cost"]
        pdv = round(price * 0.19, 2)
        bez_pdv = round(price-pdv, 2)
        
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("Ende")

        message = (f"{self.last_bill[12]['name']}<br>"
                f"Start: {self.last_bill[12]['start_time']} - Ende: {self.last_bill[12]['end_time']}<br>"
                f"Dauer: {self.last_bill[12]['duration']}<br>"
                f"Ohne MwSt: {bez_pdv:.2f}€<br>"
                f"MwSt 19%: {pdv:.2f}€<br>"
                "--------------------<br>"
                f"<span style='font-size: 40px;'>Gesamtsumme: {price:.2f}€</span>")

        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Ok)

        msg_box.exec_()

    def table_14_bill(self):
        price = self.last_bill[13]["cost"]
        pdv = round(price * 0.19, 2)
        bez_pdv = round(price-pdv, 2)
        
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("Ende")

        message = (f"{self.last_bill[13]['name']}<br>"
                f"Start: {self.last_bill[13]['start_time']} - Ende: {self.last_bill[13]['end_time']}<br>"
                f"Dauer: {self.last_bill[13]['duration']}<br>"
                f"Ohne MwSt: {bez_pdv:.2f}€<br>"
                f"MwSt 19%: {pdv:.2f}€<br>"
                "--------------------<br>"
                f"<span style='font-size: 40px;'>Gesamtsumme: {price:.2f}€</span>")

        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Ok)

        msg_box.exec_()

    def table_15_bill(self):
        price = self.last_bill[14]["cost"]
        pdv = round(price * 0.19, 2)
        bez_pdv = round(price-pdv, 2)
        
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("Ende")

        message = (f"{self.last_bill[14]['name']}<br>"
                f"Start: {self.last_bill[14]['start_time']} - Ende: {self.last_bill[14]['end_time']}<br>"
                f"Dauer: {self.last_bill[14]['duration']}<br>"
                f"Ohne MwSt: {bez_pdv:.2f}€<br>"
                f"MwSt 19%: {pdv:.2f}€<br>"
                "--------------------<br>"
                f"<span style='font-size: 40px;'>Gesamtsumme: {price:.2f}€</span>")

        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Ok)

        msg_box.exec_()

    def table_16_bill(self):
        price = self.last_bill[15]["cost"]
        pdv = round(price * 0.19, 2)
        bez_pdv = round(price-pdv, 2)
        
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("Ende")

        message = (f"{self.last_bill[15]['name']}<br>"
                f"Start: {self.last_bill[15]['start_time']} - Ende: {self.last_bill[15]['end_time']}<br>"
                f"Dauer: {self.last_bill[15]['duration']}<br>"
                f"Ohne MwSt: {bez_pdv:.2f}€<br>"
                f"MwSt 19%: {pdv:.2f}€<br>"
                "--------------------<br>"
                f"<span style='font-size: 40px;'>Gesamtsumme: {price:.2f}€</span>")

        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Ok)

        msg_box.exec_()

    def table_17_bill(self):
        price = self.last_bill[16]["cost"]
        pdv = round(price * 0.19, 2)
        bez_pdv = round(price-pdv, 2)
        
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("Ende")

        message = (f"{self.last_bill[16]['name']}<br>"
                f"Start: {self.last_bill[16]['start_time']} - Ende: {self.last_bill[16]['end_time']}<br>"
                f"Dauer: {self.last_bill[16]['duration']}<br>"
                f"Ohne MwSt: {bez_pdv:.2f}€<br>"
                f"MwSt 19%: {pdv:.2f}€<br>"
                "--------------------<br>"
                f"<span style='font-size: 40px;'>Gesamtsumme: {price:.2f}€</span>")

        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Ok)

        msg_box.exec_()

    def table_18_bill(self):
        price = self.last_bill[17]["cost"]
        pdv = round(price * 0.19, 2)
        bez_pdv = round(price-pdv, 2)
        
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("Ende")

        message = (f"{self.last_bill[17]['name']}<br>"
                f"Start: {self.last_bill[17]['start_time']} - Ende: {self.last_bill[17]['end_time']}<br>"
                f"Dauer: {self.last_bill[17]['duration']}<br>"
                f"Ohne MwSt: {bez_pdv:.2f}€<br>"
                f"MwSt 19%: {pdv:.2f}€<br>"
                "--------------------<br>"
                f"<span style='font-size: 40px;'>Gesamtsumme: {price:.2f}€</span>")

        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Ok)

        msg_box.exec_()

    def table_19_bill(self):
        price = self.last_bill[18]["cost"]
        pdv = round(price * 0.19, 2)
        bez_pdv = round(price-pdv, 2)
        
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("Ende")

        message = (f"{self.last_bill[18]['name']}<br>"
                f"Start: {self.last_bill[18]['start_time']} - Ende: {self.last_bill[18]['end_time']}<br>"
                f"Dauer: {self.last_bill[18]['duration']}<br>"
                f"Ohne MwSt: {bez_pdv:.2f}€<br>"
                f"MwSt 19%: {pdv:.2f}€<br>"
                "--------------------<br>"
                f"<span style='font-size: 40px;'>Gesamtsumme: {price:.2f}€</span>")

        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Ok)

        msg_box.exec_()

    def table_20_bill(self):
        price = self.last_bill[19]["cost"]
        pdv = round(price * 0.19, 2)
        bez_pdv = round(price-pdv, 2)
        
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("Ende")

        message = (f"{self.last_bill[19]['name']}<br>"
                f"Start: {self.last_bill[19]['start_time']} - Ende: {self.last_bill[19]['end_time']}<br>"
                f"Dauer: {self.last_bill[19]['duration']}<br>"
                f"Ohne MwSt: {bez_pdv:.2f}€<br>"
                f"MwSt 19%: {pdv:.2f}€<br>"
                "--------------------<br>"
                f"<span style='font-size: 40px;'>Gesamtsumme: {price:.2f}€</span>")

        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Ok)

        msg_box.exec_()

    def table_21_bill(self):
        price = self.last_bill[20]["cost"]
        pdv = round(price * 0.19, 2)
        bez_pdv = round(price-pdv, 2)
        
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("Ende")

        message = (f"{self.last_bill[20]['name']}<br>"
                f"Start: {self.last_bill[20]['start_time']} - Ende: {self.last_bill[20]['end_time']}<br>"
                f"Dauer: {self.last_bill[20]['duration']}<br>"
                f"Ohne MwSt: {bez_pdv:.2f}€<br>"
                f"MwSt 19%: {pdv:.2f}€<br>"
                "--------------------<br>"
                f"<span style='font-size: 40px;'>Gesamtsumme: {price:.2f}€</span>")

        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Ok)

        msg_box.exec_()

    def table_22_bill(self):
        price = self.last_bill[21]["cost"]
        pdv = round(price * 0.19, 2)
        bez_pdv = round(price-pdv, 2)
        
        
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("Ende")

        message = (f"{self.last_bill[21]['name']}<br>"
                f"Start: {self.last_bill[21]['start_time']} - Ende: {self.last_bill[21]['end_time']}<br>"
                f"Dauer: {self.last_bill[21]['duration']}<br>"
                f"Ohne MwSt: {bez_pdv:.2f}€<br>"
                f"MwSt 19%: {pdv:.2f}€<br>"
                "--------------------<br>"
                f"<span style='font-size: 40px;'>Gesamtsumme: {price:.2f}€</span>")

        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Ok)

        msg_box.exec_()

    def table_23_bill(self):
        price = self.last_bill[22]["cost"]
        pdv = round(price * 0.19, 2)
        bez_pdv = round(price-pdv, 2)
        
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("Ende")

        message = (f"{self.last_bill[22]['name']}<br>"
                f"Start: {self.last_bill[22]['start_time']} - Ende: {self.last_bill[22]['end_time']}<br>"
                f"Dauer: {self.last_bill[22]['duration']}<br>"
                f"Ohne MwSt: {bez_pdv:.2f}€<br>"
                f"MwSt 19%: {pdv:.2f}€<br>"
                "--------------------<br>"
                f"<span style='font-size: 40px;'>Gesamtsumme: {price:.2f}€</span>")

        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Ok)

        msg_box.exec_()

    def table_24_bill(self):
        price = self.last_bill[23]["cost"]
        pdv = round(price * 0.19, 2)
        bez_pdv = round(price-pdv, 2)
        
        '''novo'''

        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("Ende")

        message = (f"{self.last_bill[23]['name']}<br>"
                f"Start: {self.last_bill[23]['start_time']} - Ende: {self.last_bill[23]['end_time']}<br>"
                f"Dauer: {self.last_bill[23]['duration']}<br>"
                f"Ohne MwSt: {bez_pdv:.2f}€<br>"
                f"MwSt 19%: {pdv:.2f}€<br>"
                "--------------------<br>"
                f"<span style='font-size: 40px;'>Gesamtsumme: {price:.2f}€</span>")

        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Ok)

        msg_box.exec_()
        
        '''staro'''
        '''
        QMessageBox.information(self, "Ende", f"{self.last_bill[23]['name']}\nStart: {self.last_bill[23]["start_time"]} - Ende: {self.last_bill[23]["end_time"]}\nDauer: {self.last_bill[23]["duration"]}\nOhne MwSt: {bez_pdv:.2f}€\nMwSt 19%: {pdv:.2f}€\n--------------------\nGesamtsumme: {price:.2f}€")
        '''

    
    def initSerial(self):
        self.ser = serial.Serial(comport[0], 9600, timeout=1)
        self.serial_thread = threading.Thread(target=self.read_serial)
        self.serial_thread.daemon = True
        self.serial_thread.start()
#{}
    def show_finish_message(self, switch_num, str_time):
        fn_cijena = round(self.switch_data[switch_num]["total_cost"], 2)
        fn_pdv = round(fn_cijena * 0.19, 2)
        fn_no_pdv = round(fn_cijena - fn_pdv, 2)
        fn_from = str_time
        fn_to = time.time()
        activation_time = time.strftime('%H:%M:%S', time.localtime(fn_from))
        deactivation_time = time.strftime('%H:%M:%S', time.localtime(fn_to))
        duration_str = time.strftime('%H:%M:%S', time.gmtime(time.time()-str_time))
        
        '''odje pocinje novo'''

        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("Ende")

        message = (f"{self.switch_data[switch_num]['name']}<br>"
                f"Start: {activation_time} - Ende: {deactivation_time}<br>"
                f"Dauer: {duration_str}<br>"
                f"Ohne MwSt: {fn_no_pdv:.2f}€<br>"
                f"MwSt 19%: {fn_pdv:.2f}€<br>"
                "--------------------<br>"
                f"<span style='font-size:20px;'>Gesamtsumme:</span> {fn_cijena:.2f}€")

        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Ok)

        msg_box.exec_()
        
        '''ovo je staro'''
        '''
        QMessageBox.information(self, "Ende", f"{self.switch_data[switch_num]['name']}\nStart: {activation_time} - Ende: {deactivation_time}\nDauer: {duration_str}\nOhne MwSt: {fn_no_pdv:.2f}€\nMwSt 19%: {fn_pdv:.2f}€\n--------------------\nGesamtsumme: {fn_cijena:.2f}€")
        '''

    def read_serial(self):
        while True:
            line = self.ser.readline().decode('utf-8')
            parts = line.split()
            if len(parts) == 2:
                switch_num = int(parts[0])
                state = int(parts[1])

                if state == 1:
                    if self.switch_data[switch_num]['start_time'] is None:
                        self.switch_data[switch_num]['start_time'] = time.time()
                        self.can_close = False
                        self.switch_data[switch_num]['active'] = True
                else:
                    self.last_bill[switch_num]["cost"] = self.switch_data[switch_num]['total_cost']
                    start_time = time.strftime('%H:%M:%S', time.localtime(self.switch_data[switch_num]['start_time']))
                    self.last_bill[switch_num]["start_time"] = start_time
                    end_time = time.time()
                    self.last_bill[switch_num]["end_time"] = time.strftime('%H:%M:%S', time.localtime(end_time))
                    self.last_bill[switch_num]["duration"] = time.strftime('%H:%M:%S', time.gmtime(time.time()-self.switch_data[switch_num]['start_time']))
                    self.switch_data[switch_num]['active'] = False
                    self.can_close = all(not switch["active"] for switch in self.switch_data.values())
                    self.smjena += self.switch_data[switch_num]['total_cost']
                    self.message_signal.emit(switch_num, self.switch_data[switch_num]['start_time'])
                    self.switch_data[switch_num]['start_time'] = None
                    self.switch_data[switch_num]['duration'] = "-"
                    self.switch_data[switch_num]['total_cost_today'] += self.switch_data[switch_num]['total_cost']
                    

    def update_table(self):
        for i in range(24):
            start_time = self.switch_data[i]['start_time']
            #duration = self.switch_data[i]['duration']
            cost_per_hour = self.switch_data[i]['cost_per_hour']
            total_cost = self.switch_data[i]['total_cost']

            if start_time:
                activation_time = time.strftime('%H:%M:%S', time.localtime(start_time))
                duration_str = time.strftime('%H:%M:%S', time.gmtime(time.time()-start_time))
                self.switch_data[i]['duration'] = duration_str
                total_cost = ((((cost_per_hour/60 * ( time.time()/60 - start_time/60)) * 100 ) // 5 ) * 5 ) / 100
                self.switch_data[i]['total_cost'] = total_cost
            else:
                activation_time = "-"
                duration_str = "-"
                total_cost = "-"

            self.tableWidget.setItem(i, 0, QTableWidgetItem(self.switch_data[i]['name']))
            self.tableWidget.setItem(i, 1, QTableWidgetItem(activation_time))
            self.tableWidget.setItem(i, 2, QTableWidgetItem(duration_str))
            self.tableWidget.setItem(i, 3, QTableWidgetItem(f"{cost_per_hour:.2f}"))
            if total_cost != "-":
                self.tableWidget.setItem(i, 4, QTableWidgetItem(f"{total_cost:.2f}"))
            else:
                self.tableWidget.setItem(i, 4, QTableWidgetItem(total_cost))

    '''pocetak'''
    def tableOneCostSettings(self):
        number, ok = QInputDialog.getDouble(self, table_names[0], 'Tarif wechslen:', value = table_prices[0], min=1, decimals=2)
        if ok and number:
            table_prices[0] = number
            self.switch_data[0]["cost_per_hour"] = number
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["prices"][0] = number
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def tableTwoCostSettings(self):
        number, ok = QInputDialog.getDouble(self, table_names[1], 'Tarif wechslen:', value = table_prices[1], min=1, decimals=2)
        if ok and number:
            table_prices[1] = number
            self.switch_data[1]["cost_per_hour"] = number
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["prices"][1] = number
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def tableThreeCostSettings(self):
        number, ok = QInputDialog.getDouble(self, table_names[2], 'Tarif wechslen:', value = table_prices[2], min=1, decimals=2)
        if ok and number:
            table_prices[2] = number
            self.switch_data[2]["cost_per_hour"] = number
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["prices"][2] = number
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def tableFourCostSettings(self):
        number, ok = QInputDialog.getDouble(self, table_names[3], 'Tarif wechslen:', value = table_prices[3], min=1, decimals=2)
        if ok and number:
            table_prices[3] = number
            self.switch_data[3]["cost_per_hour"] = number
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["prices"][3] = number
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def tableFiveCostSettings(self):
        number, ok = QInputDialog.getDouble(self, table_names[4], 'Tarif wechslen:', value = table_prices[4], min=1, decimals=2)
        if ok and number:
            table_prices[4] = number
            self.switch_data[4]["cost_per_hour"] = number
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["prices"][4] = number
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def tableSixCostSettings(self):
        number, ok = QInputDialog.getDouble(self, table_names[5], 'Tarif wechslen:', value = table_prices[5], min=1, decimals=2)
        if ok and number:
            table_prices[5] = number
            self.switch_data[5]["cost_per_hour"] = number
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["prices"][5] = number
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def tableSevenCostSettings(self):
        number, ok = QInputDialog.getDouble(self, table_names[6], 'Tarif wechslen:', value = table_prices[6], min=1, decimals=2)
        if ok and number:
            table_prices[6] = number
            self.switch_data[6]["cost_per_hour"] = number
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["prices"][6] = number
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def tableEightCostSettings(self):
        number, ok = QInputDialog.getDouble(self, table_names[7], 'Tarif wechslen:', value = table_prices[7], min=1, decimals=2)
        if ok and number:
            table_prices[7] = number
            self.switch_data[7]["cost_per_hour"] = number
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["prices"][7] = number
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def tableNineCostSettings(self):
        number, ok = QInputDialog.getDouble(self, table_names[8], 'Tarif wechslen:', value = table_prices[8], min=1, decimals=2)
        if ok and number:
            table_prices[8] = number
            self.switch_data[8]["cost_per_hour"] = number
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["prices"][8] = number
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def tableTenCostSettings(self):
        number, ok = QInputDialog.getDouble(self, table_names[9], 'Tarif wechslen:', value = table_prices[9], min=1, decimals=2)
        if ok and number:
            table_prices[9] = number
            self.switch_data[9]["cost_per_hour"] = number
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["prices"][9] = number
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def tableElevenCostSettings(self):
        number, ok = QInputDialog.getDouble(self, table_names[10], 'Tarif wechslen:', value = table_prices[10], min=1, decimals=2)
        if ok and number:
            table_prices[10] = number
            self.switch_data[10]["cost_per_hour"] = number
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["prices"][10] = number
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def tableTwelveCostSettings(self):
        number, ok = QInputDialog.getDouble(self, table_names[11], 'Tarif wechslen:', value = table_prices[11], min=1, decimals=2)
        if ok and number:
            table_prices[11] = number
            self.switch_data[11]["cost_per_hour"] = number
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["prices"][11] = number
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def tableOneThreeCostSettings(self):
        number, ok = QInputDialog.getDouble(self, table_names[12], 'Tarif wechslen:', value = table_prices[12], min=1, decimals=2)
        if ok and number:
            table_prices[12] = number
            self.switch_data[12]["cost_per_hour"] = number
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["prices"][12] = number
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def tableOneFourCostSettings(self):
        number, ok = QInputDialog.getDouble(self, table_names[13], 'Tarif wechslen:', value = table_prices[13], min=1, decimals=2)
        if ok and number:
            table_prices[13] = number
            self.switch_data[13]["cost_per_hour"] = number
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["prices"][13] = number
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def tableOneFiveCostSettings(self):
        number, ok = QInputDialog.getDouble(self, table_names[14], 'Tarif wechslen:', value = table_prices[14], min=1, decimals=2)
        if ok and number:
            table_prices[14] = number
            self.switch_data[14]["cost_per_hour"] = number
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["prices"][14] = number
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def tableOneSixCostSettings(self):
        number, ok = QInputDialog.getDouble(self, table_names[15], 'Tarif wechslen:', value = table_prices[15], min=1, decimals=2)
        if ok and number:
            table_prices[15] = number
            self.switch_data[15]["cost_per_hour"] = number
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["prices"][15] = number
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def tableOneSevenCostSettings(self):
        number, ok = QInputDialog.getDouble(self, table_names[16], 'Tarif wechslen:', value = table_prices[16], min=1, decimals=2)
        if ok and number:
            table_prices[16] = number
            self.switch_data[16]["cost_per_hour"] = number
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["prices"][16] = number
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def tableOneEightCostSettings(self):
        number, ok = QInputDialog.getDouble(self, table_names[17], 'Tarif wechslen:', value = table_prices[17], min=1, decimals=2)
        if ok and number:
            table_prices[17] = number
            self.switch_data[17]["cost_per_hour"] = number
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["prices"][17] = number
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def tableOneNineCostSettings(self):
        number, ok = QInputDialog.getDouble(self, table_names[18], 'Tarif wechslen:', value = table_prices[18], min=1, decimals=2)
        if ok and number:
            table_prices[18] = number
            self.switch_data[18]["cost_per_hour"] = number
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["prices"][18] = number
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def tableTwoZeroCostSettings(self):
        number, ok = QInputDialog.getDouble(self, table_names[19], 'Tarif wechslen:', value = table_prices[19], min=1, decimals=2)
        if ok and number:
            table_prices[19] = number
            self.switch_data[19]["cost_per_hour"] = number
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["prices"][19] = number
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def tableTwoOneCostSettings(self):
        number, ok = QInputDialog.getDouble(self, table_names[20], 'Tarif wechslen:', value = table_prices[20], min=1, decimals=2)
        if ok and number:
            table_prices[20] = number
            self.switch_data[20]["cost_per_hour"] = number
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["prices"][20] = number
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def tableTwoTwoCostSettings(self):
        number, ok = QInputDialog.getDouble(self, table_names[21], 'Tarif wechslen:', value = table_prices[21], min=1, decimals=2)
        if ok and number:
            table_prices[21] = number
            self.switch_data[21]["cost_per_hour"] = number
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["prices"][21] = number
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def tableTwoThreeCostSettings(self):
        number, ok = QInputDialog.getDouble(self, table_names[22], 'Tarif wechslen:', value = table_prices[22], min=1, decimals=2)
        if ok and number:
            table_prices[22] = number
            self.switch_data[22]["cost_per_hour"] = number
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["prices"][22] = number
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def tableTwoFourCostSettings(self):
        number, ok = QInputDialog.getDouble(self, table_names[23], 'Tarif wechslen:', value = table_prices[23], min=1, decimals=2)
        if ok and number:
            table_prices[23] = number
            self.switch_data[23]["cost_per_hour"] = number
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["prices"][23] = number
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)
    '''kraj'''

    def tableOneSettings(self):
        text, ok = QInputDialog.getText(self, table_names[0], 'Name aendren:', text = table_names[0])
        if ok and text and isinstance(text, str):
            table_names[0] = text
            self.switch_data[0]["name"] = text
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["names"][0] = text
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def tableTwoSettings(self):
        text, ok = QInputDialog.getText(self, table_names[1], 'Name aendren:', text = table_names[1])
        if ok and text and isinstance(text, str):
            table_names[1] = text
            self.switch_data[1]["name"] = text
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["names"][1] = text
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def tableThreeSettings(self):
        text, ok = QInputDialog.getText(self, table_names[2], 'Name aendren:', text = table_names[2])
        if ok and text and isinstance(text, str):
            table_names[2] = text
            self.switch_data[2]["name"] = text
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["names"][2] = text
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def tableFourSettings(self):
        text, ok = QInputDialog.getText(self, table_names[3], 'Name aendren:', text = table_names[3])
        if ok and text and isinstance(text, str):
            table_names[3] = text
            self.switch_data[3]["name"] = text
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["names"][3] = text
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def tableFiveSettings(self):
        text, ok = QInputDialog.getText(self, table_names[4], 'Name aendren:', text = table_names[4])
        if ok and text and isinstance(text, str):
            table_names[4] = text
            self.switch_data[4]["name"] = text
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["names"][4] = text
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def tableSixSettings(self):
        text, ok = QInputDialog.getText(self, table_names[5], 'Name aendren:', text = table_names[5])
        if ok and text and isinstance(text, str):
            table_names[5] = text
            self.switch_data[5]["name"] = text
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["names"][5] = text
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def tableSevenSettings(self):
        text, ok = QInputDialog.getText(self, table_names[6], 'Name aendren:', text = table_names[6])
        if ok and text and isinstance(text, str):
            table_names[6] = text
            self.switch_data[6]["name"] = text
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["names"][6] = text
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def tableEightSettings(self):
        text, ok = QInputDialog.getText(self, table_names[7], 'Name aendren:', text = table_names[7])
        if ok and text and isinstance(text, str):
            table_names[7] = text
            self.switch_data[7]["name"] = text
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["names"][7] = text
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def tableNineSettings(self):
        text, ok = QInputDialog.getText(self, table_names[8], 'Name aendren:', text = table_names[8])
        if ok and text and isinstance(text, str):
            table_names[8] = text
            self.switch_data[8]["name"] = text
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["names"][8] = text
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def tableTenSettings(self):
        text, ok = QInputDialog.getText(self, table_names[9], 'Name aendren:', text = table_names[9])
        if ok and text and isinstance(text, str):
            table_names[9] = text
            self.switch_data[9]["name"] = text
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["names"][9] = text
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def tableElevenSettings(self):
        text, ok = QInputDialog.getText(self, table_names[10], 'Name aendren:', text = table_names[10])
        if ok and text and isinstance(text, str):
            table_names[10] = text
            self.switch_data[10]["name"] = text
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["names"][10] = text
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def tableTwelveSettings(self):
        text, ok = QInputDialog.getText(self, table_names[11], 'Name aendren:', text = table_names[11])
        if ok and text and isinstance(text, str):
            table_names[11] = text
            self.switch_data[11]["name"] = text
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["names"][11] = text
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def tableOneThreeSettings(self):
        text, ok = QInputDialog.getText(self, table_names[12], 'Name aendren:', text = table_names[12])
        if ok and text and isinstance(text, str):
            table_names[12] = text
            self.switch_data[12]["name"] = text
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["names"][12] = text
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def tableOneFourSettings(self):
        text, ok = QInputDialog.getText(self, table_names[13], 'Name aendren:', text = table_names[13])
        if ok and text and isinstance(text, str):
            table_names[13] = text
            self.switch_data[13]["name"] = text
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["names"][13] = text
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def tableOneFiveSettings(self):
        text, ok = QInputDialog.getText(self, table_names[14], 'Name aendren:', text = table_names[14])
        if ok and text and isinstance(text, str):
            table_names[14] = text
            self.switch_data[14]["name"] = text
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["names"][14] = text
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def tableOneSixSettings(self):
        text, ok = QInputDialog.getText(self, table_names[15], 'Name aendren:', text = table_names[15])
        if ok and text and isinstance(text, str):
            table_names[15] = text
            self.switch_data[15]["name"] = text
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["names"][15] = text
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def tableOneSevenSettings(self):
        text, ok = QInputDialog.getText(self, table_names[16], 'Name aendren:', text = table_names[16])
        if ok and text and isinstance(text, str):
            table_names[16] = text
            self.switch_data[16]["name"] = text
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["names"][16] = text
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def tableOneEightSettings(self):
        text, ok = QInputDialog.getText(self, table_names[17], 'Name aendren:', text = table_names[17])
        if ok and text and isinstance(text, str):
            table_names[17] = text
            self.switch_data[17]["name"] = text
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["names"][17] = text
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def tableOneNineSettings(self):
        text, ok = QInputDialog.getText(self, table_names[18], 'Name aendren:', text = table_names[18])
        if ok and text and isinstance(text, str):
            table_names[18] = text
            self.switch_data[18]["name"] = text
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["names"][18] = text
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def tableTwoZeroSettings(self):
        text, ok = QInputDialog.getText(self, table_names[19], 'Name aendren:', text = table_names[19])
        if ok and text and isinstance(text, str):
            table_names[19] = text
            self.switch_data[19]["name"] = text
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["names"][19] = text
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def tableTwoOneSettings(self):
        text, ok = QInputDialog.getText(self, table_names[20], 'Name aendren:', text = table_names[20])
        if ok and text and isinstance(text, str):
            table_names[20] = text
            self.switch_data[20]["name"] = text
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["names"][20] = text
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def tableTwoTwoSettings(self):
        text, ok = QInputDialog.getText(self, table_names[21], 'Name aendren:', text = table_names[21])
        if ok and text and isinstance(text, str):
            table_names[21] = text
            self.switch_data[21]["name"] = text
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["names"][21] = text
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def tableTwoThreeSettings(self):
        text, ok = QInputDialog.getText(self, table_names[22], 'Name aendren:', text = table_names[22])
        if ok and text and isinstance(text, str):
            table_names[22] = text
            self.switch_data[22]["name"] = text
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["names"][22] = text
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def tableTwoFourSettings(self):
        text, ok = QInputDialog.getText(self, table_names[23], 'Name aendren:', text = table_names[23])
        if ok and text and isinstance(text, str):
            table_names[23] = text
            self.switch_data[23]["name"] = text
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["names"][23] = text
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)

    def changeComportFunc(self):
        text, ok = QInputDialog.getText(self, 'Change COM port', 'Change COM port:', text = self.comport)
        if ok and text and isinstance(text, str):
            self.comport = text
            comport[0] = text
            with open(path_settings_json, 'r') as f:
                fajl = json.load(f)
            fajl["comport"] = text
            with open(path_settings_json, 'w') as f:
                json.dump(fajl, f)
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
    delete_unmatched_folders()
    check_and_create_folder()

    app = QApplication(sys.argv)
    window = SwitchMonitor()
    window.showMaximized()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
