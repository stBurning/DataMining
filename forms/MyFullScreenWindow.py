from typing import Optional, Union

import cv2
import numpy as np
from PyQt6 import QtWidgets
from PyQt6.QtGui import QImage, QPixmap, QPalette
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QLabel, QSizePolicy, QMenu, QWidgetAction, QMainWindow
from PyQt6.QtCore import QTimer, QThread, pyqtSignal, pyqtSlot, QEvent, Qt, QMutex, QWaitCondition, QMutexLocker
from FullScreenWindow import Ui_Form


class MyFullScreenWindow(QtWidgets.QWidget, Ui_Form):
    """
    Основное окно приложения
    """
    closeSignal = pyqtSignal()

    def __init__(self):
        super().__init__()  # Инициализация базовых классов
        self.setupUi(self)  # Инициализация базовых UI элементов, определенных в базовом классе Ui_MainWindow
        self.imageLabel = QLabel()
        self.imageLabel.setBackgroundRole(QPalette.ColorRole.Base)
        self.imageLabel.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.imageLabel.setScaledContents(True)
        self.scrollArea.setVisible(True)
        self.exitFullScreenButton.setVisible(True)
        self.scrollArea.setWidget(self.imageLabel)
        self.exitFullScreenButton.clicked.connect(self.exit_full_screen)
        self.imageLabel.adjustSize()


    @pyqtSlot(np.ndarray)
    def update_frame(self, frame):
        image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = image.shape
        bytes_per_line = ch * w
        q_image = QImage(image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        self.imageLabel.setPixmap(QPixmap(q_image))

    def set_source(self, pixmap: QPixmap):
        """Обновление для картинки"""
        self.imageLabel.setPixmap(QPixmap(pixmap))

    def exit_full_screen(self):
        self.closeSignal.emit()
