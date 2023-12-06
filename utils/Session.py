from collections import defaultdict
from enum import Enum
from typing import Dict, List

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
        self.bboxes: List[BoundingBox] = []  # Сохраненные метки
        self.camera_id = None
        self.streamType: StreamType = StreamType.none  # Вид данных

    def __getstate__(self) -> dict:  # Как мы будем "сохранять" класс
        state = {"filePath": self.filePath,
                 "fileName": self.fileName,
                 "folderName": self.folderName,
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
        self.streamType = StreamType(state["streamType"])
        self.camera_id = state["camera_id"]
        self.bboxes = []
        for label, points in state["bboxes"].items():
            p0 = points["p0"]
            p1 = points["p1"]
            bbox = BoundingBox(*p0, *p1, label=label)
            print(bbox)
            self.bboxes.append(bbox)

    def save(self):
        pass

    def load(self):
        pass

    def info(self):
        print("Активная сессия")
        print(f"Рабочая директория: {self.folderName}")
        print(f"Файл: {self.fileName}")
        print(f"Формат ввода: {self.streamType.name}")
        for bbox in self.bboxes:
            print(bbox)
