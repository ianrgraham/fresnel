import sys
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtGui import QPainter, QColor, QFont, QImage, QPixmap
from PyQt5.QtCore import Qt, QTimer
import numpy
import time
import collections
import math

import fresnel

def q_mult(q1, q2):
    w1, x1, y1, z1 = q1
    w2, x2, y2, z2 = q2
    w = w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2
    x = w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2
    y = w1 * y2 + y1 * w2 + z1 * x2 - x1 * z2
    z = w1 * z2 + z1 * w2 + x1 * y2 - y1 * x2
    return w, x, y, z

def q_conjugate(q):
    w, x, y, z = q
    return (w, -x, -y, -z)

def qv_mult(q1, v1):
    q2 = (0.0,) + v1
    return q_mult(q_mult(q1, q2), q_conjugate(q1))[1:]

def axisangle_to_q(v, theta):
    x, y, z = v
    theta /= 2
    w = math.cos(theta)
    x = x * math.sin(theta)
    y = y * math.sin(theta)
    z = z * math.sin(theta)
    return w, x, y, z

class CameraController3D:
    def __init__(self, camera):
        self.camera = camera;

    def orbit(self, yaw=0, pitch=0, roll=0, factor=-0.0025, slight=False):
        R""" Rotate the camera position about the look at point

            TODO: document me
        """

        if slight:
            factor = factor * 0.1;

        r, d, u = self.camera.basis

        q1 = axisangle_to_q(u, factor * yaw)
        q2 = axisangle_to_q(r, factor * pitch)
        q3 = axisangle_to_q(d, factor * roll)
        q = q_mult(q1, q2);
        q = q_mult(q, q3);

        px, py, pz = self.camera.position
        ax, ay, az = self.camera.look_at
        v = (px - ax, py - ay, pz - az)
        vx, vy, vz = qv_mult(q, v)

        self.camera.position = (vx + ax, vy + ay, vz + az)
        self.camera.up = qv_mult(q, u)

    def pan(self, x, y, slight=False):
        R""" Move both the camera and the lookat point

            TODO: document me
        """

        # TODO: this should be the height at the focal plane
        factor = self.camera.height

        if slight:
            factor = factor * 0.1;

        r, d, u = self.camera.basis

        rx, ry, rz = r
        ux, uy, uz = u
        delta_x, delta_y, delta_z = factor*(x*rx + y*ux), factor*(x*ry + y*uy), factor*(x*rz + y*uz)

        px, py, pz = self.camera.position
        ax, ay, az = self.camera.look_at

        self.camera.position = px+delta_x, py+delta_y, pz+delta_z
        self.camera.look_at = ax+delta_x, ay+delta_y, az+delta_z

    def zoom(self, s, slight=False):
        R""" Zoom the view in or out
        """
        factor = 0.0015

        if slight:
            factor = factor * 0.1;

        # TODO: different types of zoom for perspective cameras
        self.camera.height = self.camera.height * (1 - s*factor)

class SceneView(QWidget):
    R""" View a fresnel Scene in real time

    :py:class:`SceneView` is a Qt widget that provides a real time updating view of a fresnel scene.

    Args:

        scene (:py:class:`fresnel.Scene`) Scene to display.
    """
    def __init__(self, scene):
        super().__init__()

        # pick a default camera if one isn't already set
        self.scene = scene
        if self.scene.camera == 'auto':
            self.scene.camera = fresnel.camera.fit(scene)
        self.camera_controller = CameraController3D(self.scene.camera)

        # use a ring buffer of recorded times to generate FPS information
        self.times = collections.deque(maxlen=100)

        # fire off a timer to repaint the window as often as possible
        self.repaint_timer = QTimer(self)
        self.repaint_timer.timeout.connect(self.update)
        self.repaint_timer.start()

        # fire off a timer to print fps information every second
        self.fps_timer = QTimer(self)
        self.fps_timer.timeout.connect(self.print_fps)
        self.fps_timer.start(1000)

        # initialize a single-shot timer to delay resizing
        self.resize_timer = QTimer(self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self.resize_done)

        # initialize the tracer
        self.tracer = fresnel.tracer.Path(device=scene.device, w=10, h=10)

        # flag to notify view rotation
        self.camera_update_mode = None;
        self.mouse_initial_pos = None;

    def paintEvent(self, event):
        # track frame render times for FPS counting
        self.times.append(time.time())

        # Render the scene
        self.image_array = self.tracer.render(self.scene)

        # dispaly the rendered scene in the widget
        self.image_array.buf.map();
        img = QImage(self.image_array.buf,self.image_array.shape[1],self.image_array.shape[0],QImage.Format_RGBA8888)
        qp = QPainter(self)
        qp.drawImage(0,0,img);
        qp.end()
        self.image_array.buf.unmap();

    def mouseMoveEvent(self, event):
        delta = event.pos() - self.mouse_initial_pos;
        self.mouse_initial_pos = event.pos();

        if self.camera_update_mode == 'pitch/yaw':
             self.camera_controller.orbit(yaw=delta.x(),
                                          pitch=delta.y(),
                                          slight=event.modifiers() & Qt.ControlModifier)

        elif self.camera_update_mode == 'roll':
            self.camera_controller.orbit(roll=delta.x(),
                                         slight=event.modifiers() & Qt.ControlModifier)

        elif self.camera_update_mode == 'pan':
            h = self.height()
            self.camera_controller.pan(x=-delta.x()/h,
                                       y=delta.y()/h,
                                       slight=event.modifiers() & Qt.ControlModifier)


        self.tracer.reset();
        self.update();
        event.accept();


    def mousePressEvent(self, event):
        self.mouse_initial_pos = event.pos()
        event.accept();

        if event.button() == Qt.LeftButton:
            self.camera_update_mode = 'pitch/yaw';
        elif event.button() == Qt.RightButton:
            self.camera_update_mode = 'roll';
        elif event.button() == Qt.MiddleButton:
            self.camera_update_mode = 'pan';

    def mouseReleaseEvent(self, event):
        if self.camera_update_mode is not None:
            self.camera_update_mode = None;
            event.accept()

    def wheelEvent(self, event):
        self.camera_controller.zoom(event.angleDelta().y(),
                                    slight=event.modifiers() & Qt.ControlModifier)
        self.tracer.reset();
        event.accept()

    def resizeEvent(self, event):
        # defer resizing the tracer until the window sits still for a bit
        self.resize_timer.start(50)

    def resize_done(self):
        # resize the tracer
        self.tracer.resize(w=self.width(), h=self.height());
        self.update();

    def print_fps(self):
        # print the average FPS to the console
        t1 = self.times[0];
        t2 = self.times[-1];
        print(len(self.times) / (t2 - t1), " FPS")

