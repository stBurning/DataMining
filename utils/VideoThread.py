from typing import Union

import cv2
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal, QMutex, QWaitCondition, QMutexLocker


class VideoThread(QThread):
    """Видеопоток, наследуется от класса QThread"""
    change_pixmap_signal = pyqtSignal(np.ndarray)
    finish_signal = pyqtSignal()

    def __init__(self, source: Union[int, str] = 0, fps=30):
        super().__init__()
        self.running = False  # Флаг активации
        self.paused = bool()  # Флаг для паузы
        self.mutex = QMutex()  # Блокировщик потока
        self.cond = QWaitCondition()  # Условие блокировки
        self.source = source  # Источник потока (путь до видео-файла, номер веб-камеры)
        self.fps = fps  # Кол-во кадров в секунду

    def run(self):
        """Запуск видеопотока"""
        print("[VideoThread] Thread is running")
        self.running = True
        capture = cv2.VideoCapture(self.source)
        while self.running:
            with QMutexLocker(self.mutex):
                while self.paused:
                    self.cond.wait(self.mutex)
                ret, cv_img = capture.read()
                if ret:
                    self.change_pixmap_signal.emit(cv_img)
                    self.msleep(int(1000. / self.fps))
                else:
                    break
        capture.release()
        self.running = False
        self.paused = True
        self.finish_signal.emit()
        print("[VideoThread] Thread is finished")

    def close(self):
        if self.running:
            self.running = False
            self.resume()
            print("[VideoThread] Closing thread")

    def pause(self):
        print("[VideoThread] Thread is paused")
        """Выставление паузы у потока"""
        with QMutexLocker(self.mutex):
            self.paused = True

    def resume(self):
        """Возобновление после паузы"""
        if not self.paused:
            print("[VideoThread] Thread is not paused")
            return
        with QMutexLocker(self.mutex):
            print("[VideoThread] Thread is resumed")
            self.paused = False
            self.cond.wakeOne()  # Пробуждаем другие потоки
