"""Private-image surface rendering; workers never access a QWidget."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from threading import Event
import numpy as np
from PySide6.QtCore import Qt,QPointF
from PySide6.QtGui import QImage,QPainter,QColor,QPolygonF


@dataclass(frozen=True)
class SurfaceFrame:
    faces: np.ndarray
    colors: tuple
    center: np.ndarray
    pan: np.ndarray
    right: np.ndarray
    up: np.ndarray
    factor: float
    width: int
    height: int
    top: int
    device_pixel_ratio: float


def render_surface_image(frame,cancelled):
    """Match the existing painter's polygon order, lighting and alpha."""
    if cancelled.is_set():return None
    image=QImage(int(round(frame.width*frame.device_pixel_ratio)),
        int(round(frame.height*frame.device_pixel_ratio)),QImage.Format.Format_ARGB32_Premultiplied)
    if image.isNull():raise RuntimeError('Unable to allocate a surface image.')
    image.setDevicePixelRatio(frame.device_pixel_ratio);image.fill(QColor('#101c2b'))
    painter=QPainter(image)
    if not painter.isActive():raise RuntimeError('Unable to paint the surface image.')
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setClipRect(0,frame.top,frame.width,max(0,frame.height-frame.top-25))
        painter.setPen(Qt.PenStyle.NoPen)
        relative=frame.faces-frame.center
        x=(relative@frame.right+frame.pan[0])*frame.factor+frame.width/2
        y=-(relative@frame.up+frame.pan[1])*frame.factor+(frame.height+frame.top)/2
        direction=np.cross(frame.right,frame.up);depth=np.mean(relative@direction,axis=1)
        normals=np.cross(frame.faces[:,2]-frame.faces[:,0],frame.faces[:,3]-frame.faces[:,1])
        lengths=np.linalg.norm(normals,axis=1)
        lighting=np.divide(np.abs(normals@direction),lengths,out=np.zeros_like(lengths),where=lengths>1e-12)
        for order,index in enumerate(np.argsort(depth)):
            if order%256==0 and cancelled.is_set():return None
            color=QColor(frame.colors[index]);shade=.55+.45*lighting[index]
            color.setRgbF(color.redF()*shade,color.greenF()*shade,color.blueF()*shade,.28)
            painter.setBrush(color)
            painter.drawPolygon(QPolygonF([QPointF(float(a),float(b)) for a,b in zip(x[index],y[index])]))
    finally:painter.end()
    return None if cancelled.is_set() else image


class SurfaceRenderQueue:
    """At most one active image and one replaceable latest request.

    All methods run on the owner thread. Only render_surface_image runs on the
    executor, receiving an immutable snapshot and a cancellation Event.
    """
    def __init__(self,render=render_surface_image):
        self._render=render;self._executor=None;self._future=None;self._token=None
        self._active_key=None;self._pending=None;self.desired_key=None
        self.image=None;self.image_key=None;self.error=None;self.closed=False

    @property
    def busy(self):return self._future is not None or self._pending is not None

    def request(self,key,frame):
        if self.closed or key==self.desired_key:return
        self.desired_key=key;self._pending=(key,frame);self.error=None
        if self._future is not None:self._token.set()
        else:self._launch()

    def _launch(self):
        if self.closed or self._pending is None:return
        key,frame=self._pending;self._pending=None;self._active_key=key;self._token=Event()
        if self._executor is None:self._executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='blade-surface')
        self._future=self._executor.submit(self._render,frame,self._token)

    def poll(self):
        if self._future is None or not self._future.done():return False
        key=self._active_key;changed=False
        try:
            image=self._future.result()
            if key==self.desired_key and image is not None:
                self.image=image;self.image_key=key;changed=True
        except Exception as exc:
            if key==self.desired_key:self.error=str(exc);changed=True
        self._future=None;self._token=None;self._active_key=None;self._launch()
        return changed

    def cancel(self):
        if self._token is not None:self._token.set()
        self._pending=None;self.desired_key=None

    def reuse(self,key):
        if self.image_key!=key or self.closed:return False
        self.desired_key=key;self._pending=None;self.error=None
        if self._token is not None and self._active_key!=key:self._token.set()
        return True

    def shutdown(self,*unused):
        self.cancel();self.closed=True
        if self._executor is not None:self._executor.shutdown(wait=False,cancel_futures=True)
