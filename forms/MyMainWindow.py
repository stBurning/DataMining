from typing import Optional, Union

import cv2
import numpy as np
from PyQt6 import QtWidgets
from PyQt6.QtGui import QImage, QPixmap, QPalette
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QLabel, QSizePolicy, QMenu, QWidgetAction, QMainWindow
from PyQt6.QtCore import QTimer, QThread, pyqtSignal, pyqtSlot, QEvent, Qt
from MainWindow import Ui_MainWindow


class VideoThread(QThread):
    """
    Видеопоток с веб-камеры
    """
    change_pixmap_signal = pyqtSignal(np.ndarray)

    def __init__(self, source: Union[int, str] = 0, fps=30):
        super().__init__()
        self.is_run = True
        self.source = source
        self.fps = fps

    def run(self):
        self.is_run = True
        # capture from camera
        capture = cv2.VideoCapture(self.source)
        while self.is_run:
            ret, cv_img = capture.read()
            if ret:
                self.change_pixmap_signal.emit(cv_img)
                self.msleep(int(1000. / self.fps))
        # shut down capture system

        capture.release()

    def kill(self):
        """Sets run flag to False and waits for thread to finish"""
        self.is_run = False
        self.wait()

    def pause(self):
        """Выставление паузы у потока"""
        self.is_run = False

    def resume(self):
        """Возобновление после паузы"""
        self.run()


# noinspection PyArgumentList
class MyMainWindow(QtWidgets.QMainWindow, Ui_MainWindow):
    """
    Основное окно приложения
    """

    def __init__(self):
        super().__init__()  # Инициализация базовых классов
        self.thread = None
        self.setupUi(self)  # Инициализация базовых UI элементов, определенных в базовом классе Ui_MainWindow
        self.scaleFactor = 0.0  # Множитель при масштабировании изображения
        self.threadOn = False
        self.imageLabel = QLabel()
        self.imageLabel.setBackgroundRole(QPalette.ColorRole.Base)
        self.imageLabel.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.imageLabel.setScaledContents(True)

        self.scrollArea.setWidget(self.imageLabel)
        self.scrollArea.setVisible(False)

        self.createActions()
        self.createMenus()

    def openImage(self):
        """
        Метод, вызываемый при активации события открытия изображения.
        Вызывает диалоговое окно для выбора изображения из файловой системы и
        выводит его в поле imageLabel.
        :return:
        """
        fileName, _ = QFileDialog.getOpenFileName(self, 'QFileDialog.getOpenFileName()', '',
                                                  'Images (*.png *.jpeg *.jpg *.bmp *.gif)')
        if fileName:
            image = QImage(fileName)
            if image.isNull():
                QMessageBox.information(self, "Image Viewer", "Cannot load %s." % fileName)
                return

            self.fitToWindowAct.setEnabled(True)
            self.imageLabel.setPixmap(QPixmap.fromImage(image))
            self.scaleFactor = 1.0
            self.scrollArea.setVisible(True)
            self.updateActions()

            if not self.fitToWindowAct.isChecked():
                self.imageLabel.adjustSize()

    def openCamera(self):
        """
        Функция включения веб-камеры
        :return:
        """
        self.thread = VideoThread()  # Создаем объект потока кадров с веб-камеры
        # добавляем к потоку метод обновления кадра
        self.thread.change_pixmap_signal.connect(self.__update_frame)
        self.thread.start()  # Запускаем входящий поток
        self.threadOn = True

    def openVideo(self):
        """
        Функция открытия видеофайла
        :return:
        """
        fileName, _ = QFileDialog.getOpenFileName(self, 'QFileDialog.getOpenFileName()', '', '')
        try:
            self.thread = VideoThread(source=fileName, fps=30)  # Создаем объект потока кадров из файла

            # добавляем к потоку метод обновления кадра
            self.thread.change_pixmap_signal.connect(self.__update_frame)
            self.thread.start()  # Запускаем входящий поток
            self.threadOn = True
        except Exception as e:
            print(e)

    @pyqtSlot(np.ndarray)
    def __update_frame(self, frame):
        """
        Метод обновления кадра
        :param frame: новый кадр, который необходимо отобразить
        :return:
        """
        image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = image.shape
        bytes_per_line = ch * w
        q_image = QImage(image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        self.imageLabel.setPixmap(QPixmap(q_image))
        self.fitToWindowAct.setEnabled(True)
        self.scaleFactor = 1.0
        self.scrollArea.setVisible(True)
        self.updateActions()

        if not self.fitToWindowAct.isChecked():
            self.imageLabel.adjustSize()

    def __toggle_camera(self):
        """
        Метод изменения состояния веб-камеры (выкл/вкл)
        :return:
        """
        if self.threadOn:
            self.thread.pause()
            self.threadOn = False
            self.pushButton.setText("Start")
        else:
            self.thread.resume()
            self.threadOn = True
            self.pushButton.setText("Stop")

    def zoomIn(self):
        self.scaleImage(1.25)

    def zoomOut(self):
        self.scaleImage(0.8)

    def updateActions(self):
        self.zoomInAct.setEnabled(not self.fitToWindowAct.isChecked())
        self.zoomOutAct.setEnabled(not self.fitToWindowAct.isChecked())
        self.normalSizeAct.setEnabled(not self.fitToWindowAct.isChecked())

    def adjustScrollBar(self, scrollBar, factor):
        scrollBar.setValue(int(factor * scrollBar.value()
                               + ((factor - 1) * scrollBar.pageStep() / 2)))

    def scaleImage(self, factor):
        self.scaleFactor *= factor
        self.imageLabel.resize(self.scaleFactor * self.imageLabel.pixmap().size())

        self.adjustScrollBar(self.scrollArea.horizontalScrollBar(), factor)
        self.adjustScrollBar(self.scrollArea.verticalScrollBar(), factor)

        self.zoomInAct.setEnabled(self.scaleFactor < 3.0)
        self.zoomOutAct.setEnabled(self.scaleFactor > 0.333)

    def normalSize(self):
        self.imageLabel.adjustSize()
        self.scaleFactor = 1.0

    def fitToWindow(self):
        fitToWindow = self.fitToWindowAct.isChecked()
        self.scrollArea.setWidgetResizable(fitToWindow)
        if not fitToWindow:
            self.normalSize()

        self.updateActions()

    def createActions(self):
        self.actionImage.triggered.connect(self.openImage)
        self.actionImage.setShortcut("Ctrl+O")
        self.actionVideo.triggered.connect(self.openVideo)
        self.actionCamera.triggered.connect(self.openCamera)

        self.normalSizeAct = QWidgetAction(self)
        self.normalSizeAct.setText("&Normal Size")
        self.normalSizeAct.setShortcut("Ctrl+S")
        self.normalSizeAct.setEnabled(False)
        self.normalSizeAct.triggered.connect(self.normalSize)

        self.fitToWindowAct = QWidgetAction(self)
        self.fitToWindowAct.setText("&Fit to Window")
        self.fitToWindowAct.setShortcut("Ctrl+F")
        self.fitToWindowAct.setEnabled(False)
        self.fitToWindowAct.setCheckable(True)
        self.fitToWindowAct.triggered.connect(self.fitToWindow)

        self.zoomInAct = QWidgetAction(self)
        self.zoomInAct.setText("Zoom &In (25%)")
        self.zoomInAct.setShortcut("Ctrl++")
        self.zoomInAct.setEnabled(False)
        self.zoomInAct.triggered.connect(self.zoomIn)

        self.zoomOutAct = QWidgetAction(self)
        self.zoomOutAct.setText("Zoom &Out (25%)")
        self.zoomOutAct.setShortcut("Ctrl+-")
        self.zoomOutAct.setEnabled(False)
        self.zoomOutAct.triggered.connect(self.zoomOut)

        self.pushButton.clicked.connect(self.__toggle_camera)

    def createMenus(self):
        self.viewMenu = QMenu("&View", self)
        self.viewMenu.addAction(self.zoomInAct)
        self.viewMenu.addAction(self.zoomOutAct)
        self.viewMenu.addAction(self.normalSizeAct)
        self.viewMenu.addSeparator()
        self.viewMenu.addAction(self.fitToWindowAct)
        self.menuBar().addMenu(self.viewMenu)


if __name__ == "__main__":
    import sys  # сыс

    app = QtWidgets.QApplication(sys.argv)
    MyWindow = MyMainWindow()
    MyWindow.show()
    sys.exit(app.exec())
