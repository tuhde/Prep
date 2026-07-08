from PySide6.QtCore import Qt
from PySide6.QtGui import QPen, QColor, QWheelEvent, QMouseEvent
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsPathItem

from prep.core.path_model import PathCollection


class Canvas(QGraphicsView):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(self.renderHints() | self.renderHint(self.Antialiasing))
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self._collection: PathCollection | None = None
        self._panning = False
        self._last_pos = None

    def set_collection(self, collection: PathCollection | None) -> None:
        self._collection = collection
        self._redraw()

    def _redraw(self) -> None:
        self._scene.clear()
        if not self._collection:
            return

        w = self._collection.material_width
        h = self._collection.material_height
        sheet = QGraphicsRectItem(0, 0, w, h)
        sheet.setPen(QPen(QColor(128, 128, 128), 0.5))
        sheet.setBrush(QColor(240, 240, 240))
        self._scene.addItem(sheet)

        for layer in self._collection.layers:
            color = QColor(layer.color)
            pen = QPen(color, 0.3)
            for path in layer.paths:
                coords = list(path.geometry.coords)
                if len(coords) < 2:
                    continue
                from PySide6.QtGui import QPainterPath
                qp = QPainterPath()
                qp.moveTo(coords[0][0], -coords[0][1])
                for x, y in coords[1:]:
                    qp.lineTo(x, -y)
                item = QGraphicsPathItem(qp)
                item.setPen(pen)
                self._scene.addItem(item)

        self.setSceneRect(self._scene.itemsBoundingRect().adjusted(-10, -10, 10, 10))

    def wheelEvent(self, event: QWheelEvent) -> None:
        factor = 1.15
        if event.angleDelta().y() > 0:
            self.scale(factor, factor)
        else:
            self.scale(1.0 / factor, 1.0 / factor)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MiddleButton:
            self._panning = True
            self._last_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._panning and self._last_pos:
            delta = event.pos() - self._last_pos
            self._last_pos = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MiddleButton:
            self._panning = False
            self.setCursor(Qt.ArrowCursor)
        else:
            super().mouseReleaseEvent(event)
