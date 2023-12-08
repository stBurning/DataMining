from typing import List

import cv2
import numpy as np
from PyQt6 import QtWidgets
from PyQt6.QtCore import pyqtSignal, pyqtSlot
from PyQt6.QtGui import QImage, QPixmap, QPalette
from PyQt6.QtWidgets import QLabel, QSizePolicy

from FullScreenWindow import Ui_Form
from utils.BoundingBox import BoundingBox


class MyFullScreenWindow(QtWidgets.QWidget, Ui_Form):
    """
    Окно полноэкранного просмотра
    """
    closeSignal = pyqtSignal()  # Сигнал, к которому подписывается основное окно, чтобы узнать о закрытии данного окна

    def __init__(self):
        super().__init__()  # Инициализация базовых классов
        self.setupUi(self)  # Инициализация базовых UI элементов, определенных в базовом классе Ui_FullScreenWindow
        self.imageLabel = QLabel()  # Поле для отображения
        self.imageLabel.setBackgroundRole(QPalette.ColorRole.Base)
        self.imageLabel.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.imageLabel.setScaledContents(True)
        self.fcScrollArea.setVisible(True)
        self.fcButton.setVisible(True)
        self.bboxes: List[BoundingBox] = []
        self.fcScrollArea.setWidget(self.imageLabel)
        self.fcFullScreenButton.clicked.connect(self.exit_full_screen)
        self.imageLabel.adjustSize()

    @pyqtSlot(np.ndarray)
    def updateFrame(self, frame):
        """
        Функция обновления кадра, производит масштабирование и вывод на imageLabel
        :param frame: входящий кадр
        """
        image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = image.shape
        bytes_per_line = ch * w
        q_image = QImage(image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        self.imageLabel.setPixmap(QPixmap(q_image))
        self.drawBoxes()

    def drawBoxes(self):
        for bbox in self.bboxes:
            bbox.draw(self.imageLabel)
        self.update()

    def setImage(self, pixmap: QPixmap):
        """Обновление для картинки
        - используется, для изменения изображения в данном окне из других окон.
        """
        self.imageLabel.setPixmap(QPixmap(pixmap))

    def exit_full_screen(self):
        """
        Выход из полноэкранного режима
        - уведомляет подписчиков о закрытии данного окна
        """
        self.closeSignal.emit()
