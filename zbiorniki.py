import sys
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QSlider, QLabel
from PyQt5.QtCore import Qt, QTimer, QPointF
from PyQt5.QtGui import QPainter, QColor, QPen, QPainterPath


class Zawor:
    def __init__(self):
        self.otwarty = True

    def przelacz(self):
        self.otwarty = not self.otwarty


class ZaworSpustowy:
    def __init__(self):
        self.otwarty = False


class Rura:
    def __init__(self, punkty, grubosc=10):
        self.punkty = [QPointF(p[0], p[1]) for p in punkty]
        self.grubosc = grubosc
        self.plynie = False

    def draw(self, p):
        if not self.punkty:
            return

        path = QPainterPath()
        path.moveTo(self.punkty[0])
        for pt in self.punkty[1:]:
            path.lineTo(pt)

        p.setPen(QPen(QColor(120, 120, 120), self.grubosc))
        p.drawPath(path)

        if self.plynie:
            p.setPen(QPen(QColor(0, 160, 255), self.grubosc - 4))
            p.drawPath(path)


class Zbiornik:
    def __init__(self, x, y, nazwa):
        self.x, self.y = x, y
        self.w, self.h = 120, 160
        self.nazwa = nazwa

        self.pojemnosc = 100.0
        self.ilosc = 0.0

        self.temperatura = 20.0
        self.max_temp = 180.0
        self.krytyczna_temp = 300.0
        self.awaria_temp = 350.0

    def poziom(self):
        return 0.0 if self.pojemnosc <= 0 else self.ilosc / self.pojemnosc

    def dodaj(self, v, temp_wejscia=None):
        if v <= 0:
            return 0.0

        dodano = min(self.pojemnosc - self.ilosc, v)
        if dodano <= 0:
            return 0.0

        if temp_wejscia is None:
            temp_wejscia = self.temperatura

        m_old = self.ilosc
        m_in = dodano
        if m_old + m_in > 0:
            self.temperatura = (m_old * self.temperatura + m_in * temp_wejscia) / (m_old + m_in)

        self.ilosc += dodano
        return dodano

    def usun(self, v):
        if v <= 0:
            return 0.0, self.temperatura
        usunieto = min(self.ilosc, v)
        self.ilosc -= usunieto
        return usunieto, self.temperatura

    def podgrzewaj(self, moc):
        self.temperatura += moc * 0.08

    def chlodz(self):
        self.temperatura = max(20.0, self.temperatura - 0.3)

    def alarm_przegrzanie(self):
        return self.ilosc > 1 and self.temperatura >= self.max_temp

    def alarm_krytyczny(self):
        return self.ilosc > 1 and self.temperatura >= self.krytyczna_temp

    def alarm_przepelnienie(self):
        return self.ilosc >= self.pojemnosc - 0.01

    def wejscie(self):
        return (self.x + self.w // 2, self.y - 8)

    def wyjscie(self):
        return (self.x + self.w // 2, self.y + self.h + 8)

    def punkt_wyciek(self):
        return (self.x + 6, self.y + self.h - 6)


    def draw(self, p, awaria=False):
        if awaria:
            obrys = QColor(255, 40, 40)
        elif self.alarm_przegrzanie():
            obrys = QColor(255, 80, 80)
        else:
            obrys = QColor(240, 240, 240)

        p.setPen(QPen(obrys, 3))
        p.setBrush(Qt.NoBrush)
        p.drawRect(self.x, self.y, self.w, self.h)

        if self.ilosc > 0:
            h = int(self.h * self.poziom())
            p.setBrush(QColor(0, 120, 255))
            p.drawRect(self.x + 4, self.y + self.h - h, self.w - 8, h)

        p.setPen(QColor(240, 240, 240))
        p.drawText(self.x, self.y - 25, self.nazwa)
        p.drawText(self.x, self.y - 8, f"{int(self.temperatura)} °C")


class SCADA(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SCADA – Symulacja Zbiorników")
        self.setFixedSize(1200, 760)
        self.setStyleSheet("background:#2b2b2b")

        self.z1 = Zbiornik(80, 60, "Zbiornik 1")
        self.z2 = Zbiornik(380, 220, "Zbiornik 2")
        self.z3 = Zbiornik(680, 380, "Zbiornik 3")
        self.z4 = Zbiornik(960, 460, "Zbiornik 4")
        self.z1.ilosc = 100

        self.zbiorniki = [self.z1, self.z2, self.z3, self.z4]

        self.zawory = {self.z1: Zawor(), self.z2: Zawor(), self.z3: Zawor()}
        self.spust = ZaworSpustowy()

        self.rury = []
        for a, b in [(self.z1, self.z2), (self.z2, self.z3), (self.z3, self.z4)]:
            mid_y = (a.wyjscie()[1] + b.wejscie()[1]) / 2
            self.rury.append(Rura([
                a.wyjscie(), (a.wyjscie()[0], mid_y),
                (b.wejscie()[0], mid_y), b.wejscie()
            ]))

        self.z2_rozszczelniony = False
        self.z2_wyciek_rate = 1.8

        self.z2_doplyw_w_tym_kroku = False
        self.z2_wyciek_w_tym_kroku = False  

        self.running = False
        self.doplyw_aktywny = False
        self.alarmy = []

        self.timer = QTimer()
        self.timer.timeout.connect(self.logika)

        self.btn_start = QPushButton(self)
        self.btn_start.setGeometry(20, 700, 120, 40)
        self.btn_start.clicked.connect(self.toggle_pompa)

        self.btn_doplyw = QPushButton(self)
        self.btn_doplyw.setGeometry(160, 700, 100, 40)
        self.btn_doplyw.clicked.connect(self.toggle_doplyw)

        self.btn_spust = QPushButton(self)
        self.btn_spust.setGeometry(280, 700, 100, 40)
        self.btn_spust.clicked.connect(self.toggle_spust)

        self.btn_zawory = []
        x = 420
        for i, z in enumerate([self.z1, self.z2, self.z3]):
            b = QPushButton(self)
            b.setGeometry(x, 695, 110, 50)
            b.clicked.connect(lambda _, zb=z: self.toggle_zawor(zb))
            self.btn_zawory.append(b)
            x += 130

        self.lbl_heat = QLabel("Moc grzałki", self)
        self.lbl_heat.setGeometry(800, 670, 200, 20)
        self.lbl_heat.setStyleSheet("color: #e0e0e0;")

        self.lbl_flow = QLabel("Prędkość przepływu", self)
        self.lbl_flow.setGeometry(800, 700, 200, 20)
        self.lbl_flow.setStyleSheet("color: #e0e0e0;")

        self.slider_heat = QSlider(Qt.Horizontal, self)
        self.slider_heat.setGeometry(800, 690, 200, 20)
        self.slider_heat.setValue(5)

        self.slider_flow = QSlider(Qt.Horizontal, self)
        self.slider_flow.setGeometry(800, 720, 200, 20)
        self.slider_flow.setValue(5)

        self.update_ui()

    def toggle_pompa(self):
        self.running = not self.running
        if self.running:
            self.timer.start(30)
        else:
            self.timer.stop()
        self.update_ui()

    def toggle_doplyw(self):
        self.doplyw_aktywny = not self.doplyw_aktywny
        self.update_ui()

    def toggle_spust(self):
        self.spust.otwarty = not self.spust.otwarty
        self.update_ui()

    def toggle_zawor(self, zb):
        self.zawory[zb].przelacz()
        self.update_ui()

    def update_ui(self):
        if self.running:
            self.btn_start.setText("POMPA\nON")
            self.btn_start.setStyleSheet("background:#2e7d32; color:white;")
        else:
            self.btn_start.setText("POMPA\nOFF")
            self.btn_start.setStyleSheet("background:#b71c1c; color:white;")

        if self.doplyw_aktywny:
            self.btn_doplyw.setText("DOPŁYW\nON")
            self.btn_doplyw.setStyleSheet("background:#1565c0; color:white;")
        else:
            self.btn_doplyw.setText("DOPŁYW\nOFF")
            self.btn_doplyw.setStyleSheet("background:#424242; color:white;")

        if self.spust.otwarty:
            self.btn_spust.setText("SPUST\nON")
            self.btn_spust.setStyleSheet("background:#6a1b9a; color:white;")
        else:
            self.btn_spust.setText("SPUST\nOFF")
            self.btn_spust.setStyleSheet("background:#424242; color:white;")

        for i, z in enumerate([self.z1, self.z2, self.z3]):
            b = self.btn_zawory[i]
            if self.zawory[z].otwarty:
                b.setText(f"Zawór Z{i+1}\nOTWARTY")
                b.setStyleSheet("background:#2e7d32; color:white;")
            else:
                b.setText(f"Zawór Z{i+1}\nZAMKNIĘTY")
                b.setStyleSheet("background:#b71c1c; color:white;")

    def logika(self):
        self.alarmy.clear()
        self.z2_doplyw_w_tym_kroku = False
        self.z2_wyciek_w_tym_kroku = False

        f = self.slider_flow.value() * 0.3
        moc = self.slider_heat.value()

        if self.doplyw_aktywny and not self.z1.alarm_przepelnienie():
            self.z1.dodaj(f, temp_wejscia=20.0)

        pary = [(self.z1, self.z2), (self.z2, self.z3), (self.z3, self.z4)]
        for i, (a, b) in enumerate(pary):
            if self.zawory[a].otwarty and a.ilosc > 0 and not b.alarm_przepelnienie():
                self.rury[i].plynie = True
                usunieto, temp_out = a.usun(f)
                dodano = b.dodaj(usunieto, temp_wejscia=temp_out)

                if b == self.z2 and dodano > 0:
                    self.z2_doplyw_w_tym_kroku = True
            else:
                self.rury[i].plynie = False


        if self.spust.otwarty and self.z4.ilosc > 0:
            self.z4.usun(f * 2)

        if self.z2.ilosc > 1:
            self.z2.podgrzewaj(moc)
        else:
            self.z2.chlodz()

        
        if (not self.z2_rozszczelniony) and self.z2.temperatura >= self.z2.awaria_temp and self.z2.ilosc > 1:
            self.z2_rozszczelniony = True

        if self.z2_rozszczelniony:
            
            if self.z2.ilosc > 0 or self.z2_doplyw_w_tym_kroku:
                self.z2_wyciek_w_tym_kroku = True

            if self.z2.ilosc > 0:
                self.z2.usun(f * 1.8)

        for z in self.zbiorniki:
            if z != self.z2:
                z.chlodz()

        for z in self.zbiorniki:
            if z.alarm_przegrzanie():
                self.alarmy.append(f"PRZEGRZANIE - {z.nazwa}")
            if z.alarm_przepelnienie():
                self.alarmy.append(f"PRZEPEŁNIENIE - {z.nazwa}")

        if self.z2.alarm_krytyczny():
            self.alarmy.append("KRYTYCZNA TEMP - Zbiornik 2 (300°C)")

        if self.z2_rozszczelniony:
            self.alarmy.append("AWARIA - Zbiornik 2 rozszczelniony (>=350°C)")

        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        for r in self.rury:
            r.draw(p)

        for z in self.zbiorniki:
            z.draw(p, awaria=(z == self.z2 and self.z2_rozszczelniony))

        if self.spust.otwarty and self.z4.ilosc > 0:
            x, y = self.z4.wyjscie()
            p.setPen(QPen(QColor(0, 160, 255), 4))
            p.drawLine(x, y, x, y + 55)

        if self.z2_rozszczelniony and self.z2_wyciek_w_tym_kroku:
            x, y = self.z2.punkt_wyciek()
            p.setPen(QPen(QColor(0, 200, 255), 5))
            p.drawLine(x, y, x, y + 65)

            p.setPen(QColor(255, 120, 120))
            p.drawText(self.z2.x + 10, self.z2.y + self.z2.h + 25, "WYCIEK (AWARIA)")

        if self.alarmy:
            p.setPen(QColor(255, 80, 80))
            x0 = self.width() - 420
            p.drawText(x0, 30, "ALARMY:")
            for i, a in enumerate(self.alarmy):
                p.drawText(x0, 50 + i * 18, a)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SCADA()
    window.show()
    sys.exit(app.exec_())
