import math
import os
from typing import Optional

from PyQt6 import QtGui, QtCore
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QPainter, QFont, QPixmap
from PyQt6.QtWidgets import QLabel


class BoundingBox:
    def __init__(self, x0: int, y0: int, x1: int, y1: int,
                 label="Новая метка", color=Qt.GlobalColor.green):
        """
        Класс для реализации метки - выделения области изображения (видео)
        """
        self.p0, self.p1 = (x0, y0), (x1, y1)
        self.label: str = label
        self.color = color
        self.text_bbox: Optional[QRect] = None
        self.bbox: Optional[QRect] = None
        self.img: Optional[QPixmap] = None

    def __getstate__(self) -> dict:  # Как мы будем "сохранять" класс
        state = {"p0": self.p0,
                 "p1": self.p1,
                 "label": self.label,
                 "color": self.color}

        return state

    def __setstate__(self, state: dict):  # Как мы будем восстанавливать класс из байтов
        self.p0 = state["p0"]
        self.p1 = state["p1"]
        self.label = state["label"]
        self.color = state["color"]

    def __str__(self):
        return f"[BoundingBox] Метка {self.label} P0: {self.p0} P1: {self.p1}"

    def update(self, x1, y1):
        self.p1 = (x1, y1)

    def save(self, path):
        save_path = os.path.join(path, f"{self.label}.png")
        print(f"[BoundingBox] Save {self.label} to {save_path}")
        if self.img is not None:
            self.img.save(save_path)

    def set_label(self, label):
        self.label = label

    def copy(self):
        bbox = BoundingBox(*self.p0, *self.p1, label=self.label)
        bbox.img = self.img.copy()
        return bbox

    def get_diag(self):
        return math.sqrt((self.p0[0] - self.p1[0]) ** 2 + (self.p0[1] - self.p1[1]) ** 2)

    def draw(self, imageLabel: QLabel):
        pixmap = imageLabel.pixmap()
        painter = QPainter(pixmap)
        geometry = imageLabel.geometry()
        painter.setWindow(geometry)
        font = QFont('Helvetica', 12)
        painter.setFont(font)
        font_metrics = QtGui.QFontMetrics(font)
        painter.setPen(QtGui.QPen(self.color, 4))

        x, y, w, h = (min(self.p0[0], self.p1[0]),
                      min(self.p0[1], self.p1[1]),
                      abs(self.p0[0] - self.p1[0]),
                      abs(self.p0[1] - self.p1[1]))

        self.bbox = QtCore.QRect(x, y, w, h)
        painter.drawRect(self.bbox)
        text_bbox = font_metrics.boundingRect(self.label)
        text_bbox.moveTo(x, y - font_metrics.height())
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

    def border_collides(self, x, y):
        """
        Проверяет попадание точки в область границы метки
        :param x: координата x
        :param y: координата y
        :return: True, если точка лежит в области границы метки, иначе - False
        """
        eps = 8
        if self.bbox is not None and self.bbox.contains(x, y):
            return (abs(x - self.p0[0]) < eps or abs(x - self.p1[0]) < eps
                    or abs(y - self.p1[1]) < eps or abs(y - self.p1[1]) < eps)
        return False
