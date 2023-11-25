import math

import cv2
import numpy as np
from PyQt6 import QtWidgets, QtGui, QtCore
from PyQt6.QtCore import pyqtSlot, Qt
from PyQt6.QtGui import QImage, QPixmap, QPalette, QPainter, QColor, QFont, QFontMetrics
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QLabel, QSizePolicy, QWidgetAction

from PyQt6.QtWidgets import (QWidgetAction,
                             QInputDialog)
from typing import List, Dict
from collections import defaultdict
import pickle

from MainWindow import Ui_MainWindow
from MyFullScreenWindow import MyFullScreenWindow
from utils.VideoThread import VideoThread

from resources import resources


class BoundingBox:
    def __init__(self, x0, y0, x1, y1, label="Новая метка"):
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1
        self.label = label
        self.text_bbox = None
        self.bbox = None

    def update(self, x1, y1):
        self.x1, self.y1 = x1, y1

    def set_label(self, label):
        self.label = label

    def copy(self):
        return BoundingBox(self.x0, self.y0, self.x1, self.y1, self.label)

    def get_diag(self):
        return math.sqrt((self.x0 - self.x1) ** 2 + (self.y0 - self.y1) ** 2)

    def draw(self, imageLabel: QLabel):
        pixmap = imageLabel.pixmap()
        painter = QPainter(pixmap)
        painter.setWindow(imageLabel.geometry())
        font = QFont('Helvetica', 12)
        painter.setFont(font)
        fontMetrics = QtGui.QFontMetrics(font)
        painter.setPen(QtGui.QPen(Qt.GlobalColor.green, 4))
        x, y, w, h = min(self.x0, self.x1), min(self.y0, self.y1), abs(self.x0 - self.x1), abs(self.y0 - self.y1)
        self.bbox = QtCore.QRect(x, y, w, h)
        painter.drawRect(self.bbox)
        text_bbox = fontMetrics.boundingRect(self.label)
        text_bbox.moveTo(x, y - fontMetrics.height())
        painter.drawRect(text_bbox)
        self.text_bbox = painter.drawText(text_bbox, 0, self.label)
        painter.end()
        imageLabel.setPixmap(pixmap)

    def label_collides(self, x, y):
        """
        Проверяет попадание точки в область текстовой метки
        :param x: координата x
        :param y: координата y
        :return: True, если точка лежит в области текстовой метки, иначе - False
        """
        if self.text_bbox is not None:
            return self.text_bbox.contains(x, y)
        return False

    def collides(self, x, y):
        """
        Проверяет попадание точки в область границы метки
        :param x: координата x
        :param y: координата y
        :return: True, если точка лежит в области границы метки, иначе - False
        """
        eps = 5
        if self.bbox is not None and self.bbox.contains(x, y):
            return abs(x - self.x0) < eps or abs(x - self.x1) < eps or abs(y - self.y0) < eps or abs(y - self.y1) < eps
        return False


# noinspection PyArgumentList
class MyMainWindow(QtWidgets.QMainWindow, Ui_MainWindow):
    """
    Основное окно приложения
    """

    def __init__(self):
        super().__init__()  # Инициализация базовых классов
        self.active_bbox = None
        self.image_pixmap = None
        self.last_x = None
        self.last_y = None
        self.drawing = False
        self.label = None
        self.bboxes = []
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
        filePath, _ = QFileDialog.getOpenFileName(self, 'Открытие файла', '',
                                                  'Images (*.png *.jpeg *.jpg *.bmp *.gif)')
        fileName = filePath.split('/')[-1]  # Название файла
        folderName = filePath.split('/')[-2]  # Папка, содержащая файл
        if filePath:
            image = QImage(filePath)
            if image.isNull():
                QMessageBox.information(self, "Image Viewer", "Cannot load %s." % filePath)
                return
            self.__clean_frame()
            # Активация пункта меню с масштабированием изображения
            self.fitToWindowAct.setEnabled(True)
            # Загрузка изображения в форму
            self.image_pixmap = QPixmap.fromImage(image)
            self.imageLabel.setPixmap(self.image_pixmap)
            self.scaleFactor = 1.0  # Множитель масштабирования
            self.scrollArea.setVisible(True)  # Делаем видимым слайдеры
            self.pushButton.setVisible(False)  # Скрываем кнопку StartStop
            self.updateActions()  # Включаем возможности масштабирования
            self.label.setText(f"Из файла {fileName}")
            self.lineEdit.setText(folderName)
            if not self.fitToWindowAct.isChecked():
                self.imageLabel.adjustSize()

    def open_full_screen(self):
        """ Открытие полноэкранного просмотра
        - приостанавливает отображение данных в текущем окне
        - создает объект нового окна MyFullScreenWindow - передает ему мета-информацию
        - подписывает новое окно на процедуру обновления кадров """
        threadState = self.threadOn
        if self.thread is not None:
            self.thread.pause()  # Если поток активен - останавливаем на паузу
            self.threadOn = False
        self.imageLabel.setVisible(False)
        print('self.imageLabel.setVisible(False)')
        self.full_screen_window = MyFullScreenWindow()
        print('MyFullScreenWindow created')
        self.full_screen_window.closeSignal.connect(self.__close_full_screen)
        self.full_screen_window.fcButton.clicked.connect(self.__toggle_video)
        self.full_screen_window.fcButton.setText('Start')
        self.full_screen_window.fcTextEdit.setText(self.lineEdit.text())
        self.full_screen_window.fcLabel.setText(self.label.text())
        if self.thread is not None:  # сигнал видео-потока
            self.full_screen_window.set_source(self.imageLabel.pixmap())
            self.thread.change_pixmap_signal.connect(self.full_screen_window.update_frame)
            self.full_screen_window.fcButton.setVisible(True)
        else:  # изображение
            self.full_screen_window.set_source(self.imageLabel.pixmap())
            self.full_screen_window.fcButton.setVisible(False)
        self.full_screen_window.showFullScreen()
        if self.thread is not None and threadState:  # Если поток жил, и был активен, то пробуждаем его
            self.thread.resume()
            self.full_screen_window.fcButton.setText("Stop")
            self.threadOn = True

    @pyqtSlot()
    def __close_full_screen(self):
        """
        Закрытие полноэкранного просмотра
        - отписывает окно full_screen_window от обновления кадров
        - возобновляет просмотр в основном окне
        """
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
        """
        self.__clean_frame()  # Очищаем текущий кадр, закрываем поток кадров

        self.thread = VideoThread()  # Создаем объект потока кадров с веб-камеры
        # добавляем к потоку метод обновления кадра
        self.thread.change_pixmap_signal.connect(self.update_frame)
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
        """
        filePath, _ = QFileDialog.getOpenFileName(self, 'QFileDialog.getOpenFileName()', '', '')
        fileName = filePath.split("/")[-1]  # Название файла
        folderName = filePath.split('/')[-2]  # Папка, содержащая файл
        try:
            if self.thread is not None:
                self.__clean_frame()

            self.thread = VideoThread(source=filePath, fps=30)  # Создаем объект потока кадров из файла

            # добавляем к потоку метод обновления кадра
            self.thread.change_pixmap_signal.connect(self.update_frame)
            self.threadOn = True  # Устанавливаем флаг, что видео-поток запущен
            self.thread.start()  # Запускаем входящий поток
            self.scrollArea.setVisible(True)
            self.pushButton.setVisible(True)  # Делаем кнопку видимой
            self.pushButton.setText("Stop")  # Меняем надпись на "Стоп"
            self.label.setText(f"Из файла {fileName}")
            self.lineEdit.setText(folderName)
        except Exception as e:
            print(e)

    @pyqtSlot(np.ndarray)
    def update_frame(self, frame):
        """
        Метод обновления кадра
        :param frame: новый кадр, который необходимо отобразить
        """

        def frameToPixmap(input_frame):
            image = cv2.cvtColor(input_frame, cv2.COLOR_BGR2RGB)
            h, w, ch = image.shape
            bytes_per_line = ch * w
            q_image = QImage(image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            return QPixmap(q_image)

        pixmap = frameToPixmap(frame)
        self.image_pixmap = pixmap
        self.imageLabel.setPixmap(pixmap)
        self.draw_bboxes()
        self.fitToWindowAct.setEnabled(True)

    def draw_bboxes(self):
        self.imageLabel.setPixmap(self.image_pixmap)
        for bbox in self.bboxes:
            bbox.draw(self.imageLabel)

        if self.active_bbox is not None:
            self.active_bbox.draw(self.imageLabel)

    def mousePress(self, event):
        self.imageLabel.setMouseTracking(True)
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            print(f"[mousePressEvent] {event.pos()}")
            x, y = event.pos().x(), event.pos().y()
            for bbox in self.bboxes:
                if bbox.label_collides(x, y):
                    text, ok = QInputDialog.getText(self, 'Изменение метки', 'Введите название метки:')
                    if ok:
                        bbox.set_label(text)
                        self.draw_bboxes()
                    return
                if bbox.collides(x, y):
                    text, ok = QInputDialog.getText(self, 'Удаление метки', 'Введите название метки:')
                    if ok:
                        # bbox.set_label(text)
                        self.bboxes.remove(bbox)
                        self.draw_bboxes()
                    return
            self.drawing = True
            self.last_x = x
            self.last_y = y

    def mouseMove(self, event):
        if event.buttons() and Qt.MouseButton.LeftButton and self.drawing:
            curr_x, curr_y = event.pos().x(), event.pos().y()
            self.active_bbox = BoundingBox(self.last_x, self.last_y, curr_x, curr_y)
            self.draw_bboxes()
            self.update()

    def mouseRelease(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            text, ok = QInputDialog.getText(self, 'Новая метка',
                                            'Введите название метки:')
            if ok:
                self.active_bbox.set_label(text)
                self.bboxes.append(self.active_bbox.copy())
                print(self.active_bbox.get_diag())
            self.active_bbox = None
            self.drawing = False
            self.draw_bboxes()
            self.repaint()

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
                self.full_screen_window.fcButton.setText("Start")
            self.threadOn = False
        else:
            self.thread.resume()
            self.pushButton.setText("Stop")
            if self.full_screen_window is not None:
                self.full_screen_window.fcButton.setText("Stop")
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

        self.imageLabel.mousePressEvent = self.mousePress
        self.imageLabel.mouseMoveEvent = self.mouseMove
        self.imageLabel.mouseReleaseEvent = self.mouseRelease

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
