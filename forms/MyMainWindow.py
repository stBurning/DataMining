from typing import Union

import cv2
import numpy as np
from PyQt6 import QtWidgets
from PyQt6.QtCore import QThread, pyqtSignal, pyqtSlot, QMutex, QWaitCondition, QMutexLocker
from PyQt6.QtGui import QImage, QPixmap, QPalette
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QLabel, QSizePolicy, QWidgetAction

from MainWindow import Ui_MainWindow
from MyFullScreenWindow import MyFullScreenWindow


class VideoThread(QThread):
    """Видеопоток, наследуется от класса QThread"""
    change_pixmap_signal = pyqtSignal(np.ndarray)

    def __init__(self, source: Union[int, str] = 0, fps=30):
        super().__init__()
        self.is_run = True  # Флаг активации
        self.is_paused = bool()  # Флаг для паузы
        self.mutex = QMutex()  # Блокировщик потока
        self.cond = QWaitCondition()  # Условие блокировки
        self.source = source  # Источник потока (путь до видео-файла, номер веб-камеры)
        self.fps = fps  # Кол-во кадров в секунду

    def run(self):
        """Запуск видеопотока"""
        self.is_run = True
        capture = cv2.VideoCapture(self.source)
        while self.is_run:
            with QMutexLocker(self.mutex):
                while self.is_paused:
                    self.cond.wait(self.mutex)
                ret, cv_img = capture.read()
                if ret:
                    self.change_pixmap_signal.emit(cv_img)
                    self.msleep(int(1000. / self.fps))
        capture.release()
        self.close()
        print("Thread closed")

    def close(self):
        self.is_run = False
        self.wait()

    def pause(self):
        """Выставление паузы у потока"""
        with QMutexLocker(self.mutex):
            self.is_paused = True

    def resume(self):
        """Возобновление после паузы"""
        if not self.is_paused:
            return
        with QMutexLocker(self.mutex):
            self.is_paused = False
            self.cond.wakeOne()  # Пробуждаем другие потоки


# noinspection PyArgumentList
class MyMainWindow(QtWidgets.QMainWindow, Ui_MainWindow):
    """
    Основное окно приложения
    """

    def __init__(self):
        super().__init__()  # Инициализация базовых классов
        self.thread = None  # Видео поток
        self.full_screen_window = None
        self.setupUi(self)  # Инициализация базовых UI элементов, определенных в базовом классе Ui_MainWindow
        self.scaleFactor = 0.0  # Множитель при масштабировании изображения
        self.imageLabel = QLabel()  # Основное поле для вывода изображений
        self.imageLabel.setBackgroundRole(QPalette.ColorRole.Base)
        self.imageLabel.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.imageLabel.setScaledContents(True)
        self.scrollArea.setWidget(self.imageLabel)
        self.scrollArea.setVisible(False)
        self.pushButton.setVisible(False)
        self.createActions()
        self.createMenus()
        self.threadOn = False  # Флаг состояния потока вывода

    def __clean_frame(self):
        if self.thread is not None:
            self.thread.resume()  # Выводим из паузы
            self.threadOn = False  # Предупреждаем о выключении
            self.thread.close()  # Закрываем

    def openImage(self):
        """
        Метод, вызываемый при активации события открытия изображения.
        Вызывает диалоговое окно для выбора изображения из файловой системы и
        выводит его в поле imageLabel.
        :return:
        """

        fileName, _ = QFileDialog.getOpenFileName(self, 'Открытие файла', '',
                                                  'Images (*.png *.jpeg *.jpg *.bmp *.gif)')
        if fileName:
            image = QImage(fileName)
            if image.isNull():
                QMessageBox.information(self, "Image Viewer", "Cannot load %s." % fileName)
                return
            self.__clean_frame()
            # Активация пункта меню с масштабированием изображения
            self.fitToWindowAct.setEnabled(True)
            # Загрузка изображения в форму
            self.imageLabel.setPixmap(QPixmap.fromImage(image))
            self.scaleFactor = 1.0  # Множитель масштабирования
            self.scrollArea.setVisible(True)  # Делаем видимым слайдеры
            self.pushButton.setVisible(False)  # Скрываем кнопку StartStop
            self.updateActions()  # Включаем возможности масштабирования
            self.label.setText("Из файла")
            self.lineEdit.setText(fileName)
            if not self.fitToWindowAct.isChecked():
                self.imageLabel.adjustSize()

    def open_full_screen(self):
        threadState = self.threadOn
        if self.thread is not None:
            self.thread.pause()  # Если поток активен - останавливаем на паузу
            self.threadOn = False

        self.imageLabel.setVisible(False)
        self.full_screen_window = MyFullScreenWindow()
        self.full_screen_window.closeSignal.connect(self.__close_full_screen)
        self.full_screen_window.pushButton.clicked.connect(self.__toggle_video)
        self.full_screen_window.pushButton.setText('Start')

        if self.thread is not None:  # сигнал видео-потока
            self.thread.change_pixmap_signal.connect(self.full_screen_window.update_frame)
            self.full_screen_window.pushButton.setVisible(True)
        else:  # изображение
            self.full_screen_window.set_source(self.imageLabel.pixmap())
            self.full_screen_window.pushButton.setVisible(False)

        self.full_screen_window.show()

        if self.thread is not None and threadState:  # Если поток жил, и был активен, то пробуждаем его
            self.thread.resume()
            self.full_screen_window.pushButton.setText("Stop")
            self.threadOn = True

    @pyqtSlot()
    def __close_full_screen(self):
        self.full_screen_window.closeSignal.disconnect(self.__close_full_screen)
        self.scrollArea.setWidget(self.imageLabel)
        self.scrollArea.setVisible(True)
        self.imageLabel.setVisible(True)
        self.full_screen_window = None
        if self.thread is not None and self.threadOn:
            self.thread.resume()
            self.threadOn = True

    def openCamera(self):
        """
        Функция включения веб-камеры.
        :return:
        """
        self.__clean_frame()  # Очищаем текущий кадр, закрываем поток кадров

        self.thread = VideoThread()  # Создаем объект потока кадров с веб-камеры
        # добавляем к потоку метод обновления кадра
        self.thread.change_pixmap_signal.connect(self.__update_frame)
        self.thread.start()  # Запускаем входящий поток
        self.threadOn = True  # Устанавливаем флаг, что видео-поток запущен
        self.pushButton.setVisible(True)  # Делаем кнопку видимой
        self.pushButton.setText("Stop")  # Меняем надпись на "Стоп"
        self.label.setText("Из камеры")
        self.lineEdit.setText("")

    def openVideo(self):
        """
        Функция открытия видео-потока из файла.
        Вызывает диалоговое окно для выбора видео-файла из файловой системы и
        выводит его в поле imageLabel.
        :return:
        """
        fileName, _ = QFileDialog.getOpenFileName(self, 'QFileDialog.getOpenFileName()', '', '')
        try:
            if self.thread is not None:
                self.__clean_frame()

            self.thread = VideoThread(source=fileName, fps=60)  # Создаем объект потока кадров из файла

            # добавляем к потоку метод обновления кадра
            self.thread.change_pixmap_signal.connect(self.__update_frame)
            self.threadOn = True  # Устанавливаем флаг, что видео-поток запущен
            self.thread.start()  # Запускаем входящий поток
            self.scrollArea.setVisible(True)
            self.pushButton.setVisible(True)  # Делаем кнопку видимой
            self.pushButton.setText("Stop")  # Меняем надпись на "Стоп"
            self.label.setText("Из файла")
            self.lineEdit.setText(fileName)
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
        # self.scaleFactor = 1.0
        # self.scrollArea.setVisible(True)
        # self.updateActions()
        #
        # if not self.fitToWindowAct.isChecked():
        #     self.imageLabel.adjustSize()

    @pyqtSlot()
    def __toggle_video(self):
        """
        Метод изменения состояния веб-камеры (выкл/вкл)
        :return:
        """
        if self.thread is None:
            return
        if self.threadOn:
            self.thread.pause()
            self.pushButton.setText("Start")
            if self.full_screen_window is not None:
                self.full_screen_window.pushButton.setText("Start")
            self.threadOn = False
        else:
            self.thread.resume()
            self.pushButton.setText("Stop")
            if self.full_screen_window is not None:
                self.full_screen_window.pushButton.setText("Stop")
            self.threadOn = True

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

        self.pushButton.clicked.connect(self.__toggle_video)
        self.fullScreenButton.clicked.connect(self.open_full_screen)

    def createMenus(self):
        self.menuView.addAction(self.zoomInAct)
        self.menuView.addAction(self.zoomOutAct)
        self.menuView.addAction(self.normalSizeAct)
        self.menuView.addSeparator()
        self.menuView.addAction(self.fitToWindowAct)


if __name__ == "__main__":
    import sys

    app = QtWidgets.QApplication(sys.argv)
    MyWindow = MyMainWindow()
    MyWindow.show()
    sys.exit(app.exec())
