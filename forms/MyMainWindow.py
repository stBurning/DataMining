import pickle

import cv2
import numpy as np
from PyQt6 import QtWidgets, QtCore
from PyQt6.QtCore import pyqtSlot, Qt
from PyQt6.QtGui import QImage, QPixmap, QPalette
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QLabel, QSizePolicy
from PyQt6.QtWidgets import (QWidgetAction,
                             QInputDialog)

from MainWindow import Ui_MainWindow
from MyFullScreenWindow import MyFullScreenWindow
from utils.BoundingBox import BoundingBox
from utils.Session import Session, StreamType
from utils.VideoThread import VideoThread
from resources import resources

# noinspection PyArgumentList
class MyMainWindow(QtWidgets.QMainWindow, Ui_MainWindow):
    """
    Основное окно приложения
    """

    def __init__(self):
        super().__init__()  # Инициализация базовых классов
        self.session = None

        self.active_bbox = None  # Активная область
        self.image_pixmap = None  # Текущий кадр
        self.last_point = None  # Последняя нажатая точка
        self.drawing = False  # Флаг активного рисования метки
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
        self.threadOn = False  # Флаг состояния потока вывода\

        self.load_session()
        self.draw_bboxes()

    def __clean_frame(self):
        if self.thread is not None:
            self.thread.resume()  # Выводим из паузы
            self.threadOn = False  # Предупреждаем о выключении
            self.thread.close()  # Закрываем

    def openImageDialog(self):
        """
        Метод, вызываемый при активации события открытия изображения.
        Вызывает диалоговое окно для выбора изображения из файловой системы и
        выводит его в поле imageLabel.
        :return:
        """
        filePath, _ = QFileDialog.getOpenFileName(self, 'Открытие файла', '../sample_data/',
                                                  'Images (*.png *.jpeg *.jpg *.bmp *.gif)')

        if filePath:
            self.session.filePath = filePath
            self.session.fileName = self.session.filePath.split('/')[-1]  # Название файла
            self.session.folderName = self.session.filePath.split('/')[-2]  # Папка, содержащая файл
            self.openImage()

    def openImage(self, path=None):
        if path is not None:
            self.session.filePath = path
            self.session.fileName = self.session.filePath.split("/")[-1]  # Название файла
            self.session.folderName = self.session.filePath.split('/')[-2]  # Папка, содержащая файл

        image = QImage(self.session.filePath)
        if image.isNull():
            QMessageBox.information(self, "Открытие изображения", "Не удалось открыть %s." % self.session.filePath)
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
        self.label.setText(f"Из файла {self.session.fileName}")
        self.lineEdit.setText(self.session.folderName)
        if not self.fitToWindowAct.isChecked():
            self.imageLabel.adjustSize()
        self.session.streamType = StreamType.image

    def openCamera(self, source=0):
        """
        Функция включения веб-камеры.
        """
        self.__clean_frame()  # Очищаем текущий кадр, закрываем поток кадров
        self.session.camera_id = source
        self.thread = VideoThread(self.session.camera_id)  # Создаем объект потока кадров с веб-камеры
        # добавляем к потоку метод обновления кадра
        self.thread.change_pixmap_signal.connect(self.update_frame)
        self.thread.start()  # Запускаем входящий поток
        self.threadOn = True  # Устанавливаем флаг, что видео-поток запущен
        self.pushButton.setVisible(True)  # Делаем кнопку видимой
        self.pushButton.setText("Stop")  # Меняем надпись на "Стоп"
        self.label.setText("Из камеры")
        self.lineEdit.setText("")
        self.session.streamType = StreamType.camera

    def openVideoDialog(self):
        """
        Функция открытия видео-потока из файла.
        Вызывает диалоговое окно для выбора видео-файла из файловой системы и
        выводит его в поле imageLabel.
        """
        filePath, _ = QFileDialog.getOpenFileName(self, 'QFileDialog.getOpenFileName()', '../sample_data/', '')
        if filePath:
            self.session.filePath = filePath
            self.session.fileName = self.session.filePath.split("/")[-1]  # Название файла
            self.session.folderName = self.session.filePath.split('/')[-2]  # Папка, содержащая файл
            self.openVideo()

    def openVideo(self, path=None):
        try:
            if path is not None:
                self.session.filePath = path
                self.session.fileName = self.session.filePath.split("/")[-1]  # Название файла
                self.session.folderName = self.session.filePath.split('/')[-2]  # Папка, содержащая файл

            if self.thread is not None:
                self.__clean_frame()

            self.thread = VideoThread(source=self.session.filePath, fps=30)  # Создаем объект потока кадров из файла

            # Добавляем к потоку метод обновления кадра
            self.thread.change_pixmap_signal.connect(self.update_frame)
            self.threadOn = True  # Устанавливаем флаг, что видео-поток запущен
            self.thread.start()  # Запускаем входящий поток
            self.scrollArea.setVisible(True)
            self.pushButton.setVisible(True)  # Делаем кнопку видимой
            self.pushButton.setText("Stop")  # Меняем надпись на "Стоп"
            self.label.setText(f"Из файла {self.session.filePath}")
            self.lineEdit.setText(self.session.folderName)
            self.session.streamType = StreamType.video

        except Exception as e:
            print(e)

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
        self.full_screen_window = MyFullScreenWindow()
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
        if self.image_pixmap is not None:
            self.imageLabel.setPixmap(self.image_pixmap)
        for bbox in self.session.bboxes:
            bbox.draw(self.imageLabel)

        if self.active_bbox is not None:
            self.active_bbox.draw(self.imageLabel)

    def mousePress(self, event):
        self.imageLabel.setMouseTracking(True)
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            x, y = event.pos().x(), event.pos().y()
            for bbox in self.session.bboxes:
                if bbox.label_collides(x, y):
                    text, ok = QInputDialog.getText(self, 'Изменение метки', 'Введите название метки:')
                    if ok:
                        bbox.set_label(text)
                        self.draw_bboxes()
                    return
                if bbox.border_collides(x, y):
                    dlg = QMessageBox.question(self, "Удаление метки", "Вы хотите удалить метку?")
                    if dlg == QMessageBox.StandardButton.Yes:
                        self.session.bboxes.remove(bbox)
                        self.draw_bboxes()
                    return
            self.drawing = True
            self.last_point = (x, y)

    def mouseMove(self, event):
        """
        Обработка движения мыши для отрисовки метки
        """
        if event.buttons() and Qt.MouseButton.LeftButton and self.drawing:
            current_point = (event.pos().x(), event.pos().y())
            self.active_bbox = BoundingBox(*self.last_point, *current_point)
            self.draw_bboxes()
            self.update()

    def mouseRelease(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            text, ok = QInputDialog.getText(self, 'Новая метка',
                                            'Введите название метки:')
            if ok:
                self.active_bbox.set_label(text)
                self.session.bboxes.append(self.active_bbox.copy())
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
        fit_to_window = self.fitToWindowAct.isChecked()
        self.scrollArea.setWidgetResizable(fit_to_window)
        if not fit_to_window:
            self.normalSize()
        self.updateActions()

    def createActions(self):
        self.actionImage.triggered.connect(self.openImageDialog)
        self.actionImage.setShortcut("Ctrl+O")
        self.actionVideo.triggered.connect(self.openVideoDialog)
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

    def closeEvent(self, event):
        """ Обработчик нажатия на крестик (при закрытии приложения) """
        close = QMessageBox.question(self,
                                     "Закрытие сессии",
                                     "Вы уверены, что хотите завершить сессию?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if close == QMessageBox.StandardButton.Yes:
            with open("./session.pickle", "wb") as f:
                pickle.dump(self.session, f, protocol=pickle.HIGHEST_PROTOCOL)
            event.accept()
        else:
            event.ignore()

    def load_session(self):
        try:
            with open("./session.pickle", 'rb') as fp:
                self.session = pickle.load(fp, fix_imports=True, encoding='ASCII', errors='strict', buffers=None)
                self.session.info()
                if self.session.streamType == StreamType.image:
                    self.openImage()
                elif self.session.streamType == StreamType.video:
                    self.openVideo()
                elif self.session.streamType == StreamType.camera:
                    self.openCamera(self.session.camera_id)
                else:
                    print("Новая сессия")

        except pickle.UnpicklingError as e:
            print("Не удалось загрузить сессию")
            self.session = Session()
        except FileNotFoundError as e:
            print("Не удалось загрузить сессию")
            self.session = Session()


if __name__ == "__main__":
    import sys

    app = QtWidgets.QApplication(sys.argv)
    MyWindow = MyMainWindow()
    MyWindow.show()
    sys.exit(app.exec())
