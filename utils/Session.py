from collections import defaultdict
from enum import Enum
from typing import Dict, List

from PyQt6.QtCore import QRect

from utils.BoundingBox import BoundingBox


class StreamType(Enum):
    none = 0
    image = 1
    video = 2
    camera = 3


class Session:
    """Настройки приложения"""

    def __init__(self):
        self.filePath = None  # Путь до рабочего файла
        self.fileName = None  # Название файла
        self.folderName = None  # Название папки
        self.workingDir = None
        self.bboxes: List[BoundingBox] = []  # Сохраненные метки
        self.camera_id = None
        self.streamType: StreamType = StreamType.none  # Вид данных

    def __getstate__(self) -> dict:  # Как мы будем "сохранять" класс
        state = {"filePath": self.filePath,
                 "fileName": self.fileName,
                 "folderName": self.folderName,
                 "workingDir": self.workingDir,
                 "streamType": self.streamType.value,
                 'camera_id': self.camera_id}
        bbox_dict = {}
        for bbox in self.bboxes:
            bbox_dict[bbox.label] = {"p0": bbox.p0, "p1": bbox.p1}
        state['bboxes'] = bbox_dict

        return state

    def __setstate__(self, state: dict):  # Как мы будем восстанавливать класс из байтов
        self.filePath = state["filePath"]
        self.fileName = state["fileName"]
        self.folderName = state["folderName"]
        self.workingDir = state["workingDir"]
        self.streamType = StreamType(state["streamType"])
        self.camera_id = state["camera_id"]
        self.bboxes = []
        for label, points in state["bboxes"].items():
            p0 = points["p0"]
            p1 = points["p1"]
            bbox = BoundingBox(*p0, *p1, label=label)
            self.bboxes.append(bbox)

    def save(self):
        for bbox in self.bboxes:
            bbox.save(self.workingDir)

    def load(self):
        pass

    def info(self):
        print("[Session] Активная сессия")
        print(f"[Session] Рабочая директория: {self.workingDir}")
        print(f"[Session] Файл: {self.fileName}")
        print(f"[Session] Формат ввода: {self.streamType.name}")
        for bbox in self.bboxes:
            print(bbox)
