from typing import Union

import cv2
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal, QMutex, QWaitCondition, QMutexLocker


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
