# Copyright (c) 2016-2017 The Regents of the University of Michigan
# This file is part of the Fresnel project, released under the BSD 3-Clause License.

R"""
The fresnel ray tracing package.
"""

import os

from . import geometry
from . import tracer
from . import camera

class Device:
    R""" Hardware device to use for ray tracing.

    Args:

        mode (str): Specify execution mode: Valid values are `auto`, `gpu`, and `cpu`.

    :py:class:`Device` defines hardware device to use for ray tracing. :py:class:`Scene` and
    :py:mod:`tracer <fresnel.tracer>` instances must be attached to a :py:class:`Device`. You may attach any number of
    instances to a single :py:class:`Device`.

    When mode is `auto`, the default, Device will automatically select all available GPU devices in the system or
    fall back on CPU rendering if there is no GPU available or GPU support was not compiled in. Set mode to
    `gpu` or `cpu` to force a specific mode.

    .. tip::
        Use only a single :py:class:`Device` to reduce memory consumption.
    """

    def __init__(self, mode='auto'):
        # attempt to import the cpu and gpu modules
        try:
            from fresnel import _cpu;
        except ImportError as e:
            print("Error importing:", e.msg);
            _cpu = None;

        try:
            from fresnel import _gpu;
        except ImportError as e:
            print("Error importing:", e.msg);
            _gpu = None;

        # determine the number of available GPUs
        num_gpus = 0;
        if _gpu is not None:
            num_gpus = _gpu.get_num_available_devices();

        # determine the selected mode
        selected_mode = '';

        if mode == 'auto':
            if num_gpus > 0:
                selected_mode = 'gpu'
            else:
                selected_mode = 'cpu'
                if _cpu is None:
                    raise RuntimeError("No GPUs available AND CPU fallback library is not compiled");

        if mode == 'gpu':
            if _gpu is None:
                raise RuntimeError("GPU implementation is not compiled");
            if num_gpus == 0:
                raise RuntimeError("No GPUs are available");
            selected_mode = 'gpu';

        if mode == 'cpu':
            if _cpu is None:
                raise RuntimeError("CPU implementation is not compiled");
            selected_mode = 'cpu';

        # inititialize the device
        if selected_mode == 'gpu':
            self.module = _gpu;
            self._device = _gpu.Device(os.path.dirname(os.path.realpath(__file__)));
        elif selected_mode == 'cpu':
            self.module = _cpu;
            self._device = _cpu.Device();
        else:
            raise ValueError("Invalid mode");

class Scene:
    R""" Content of the scene to ray trace.

    Args:

        device (:py:class:`Device`): Device to create this Scene on.

    :py:class:`Scene` defines the contents of the scene to be ray traced, including any number of
    :py:mod:`geometry <fresnel.geometry>` objects.

    Every :py:class:`Scene` attaches to a :py:class:`Device`. For convenience, :py:class:`Scene` creates a default
    :py:class:`Device` when **device** is *None*. If you want a non-default device, you must create it explicitly.

    Attributes:

        device (:py:class:`Device`): Device this Scene is attached to.
        camera (:py:class:`camera.Camera`): Camera view parameters.
        background_color (tuple[float]): Background color (r,g,b) as a tuple or other 3-length python object.
        background_alpha (float): Background alpha (opacity).
    """

    def __init__(self, device=None, camera=camera.Orthographic(position=(0,0, 1), look_at=(0,0,0), up=(0,1,0), height=3)):
        if device is None:
            device = Device();

        self.device = device;
        self._scene = self.device.module.Scene(self.device._device);
        self.geometry = [];
        self.camera = camera;

    @property
    def camera(self):
        # TODO: implement me
        raise NotImplemented;

    @camera.setter
    def camera(self, value):
        self._scene.setCamera(value._camera);

    @property
    def background_color(self):
        color = self._scene.getBackgroundColor();
        return (color.r, color.g, color.b);

    @background_color.setter
    def background_color(self, value):
        self._scene.setBackgroundColor(_common.RGBf(*value));

    @property
    def background_alpha(self):
        return self._scene.getBackgroundAlpha();

    @background_alpha.setter
    def background_alpha(self, value):
        self._scene.setBackgroundAlpha(value);

    @property
    def light_direction(self):
        v = self._scene.getLightDirection();
        return (v.x, v.y, v.z);

    @light_direction.setter
    def light_direction(self, value):
        self._scene.setLightDirection(_common.vec3f(*value));
