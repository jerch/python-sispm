# The MIT License (MIT)
#
# Copyright (c) 2014 Joerg Breitbart
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

__author__ = 'Joerg Breitbart'
__copyright__ = 'Copyright (C) 2014 Joerg Breitbart'
__license__ = 'MIT'
__version__ = '0.1.0'

from usb.core import find, USBError
from usb.util import dispose_resources
from time import sleep
from functools import wraps

VENDOR = 0x04B4  # Gembird

# known working devices
MSISPM_OLD = 0xFD10
SISPM = 0xFD11
MSISPM_FLASH = 0xFD12
MSISPM_FLASH_NEW = 0xFD13

DEVICE_TYPES = {
    MSISPM_OLD:         ((1,),          '1-socket mSiS-PM'),
    SISPM:              ((1, 2, 3, 4),  '4-socket SiS-PM'),
    MSISPM_FLASH:       ((1,),          '1-socket mSiS-PM'),
    MSISPM_FLASH_NEW:   ((1, 2, 3, 4),  '4-socket SiS-PM'),
}

TRIES = 5


def autodispose(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            result = func(self, *args, **kwargs)
        except:
            raise
        finally:
            try:
                if self.autodispose:
                    dispose_resources(self.device)
            except USBError:
                pass
        return result
    return wrapper


class OutletException(Exception):
    def __init__(self, outlet):
        self.outlet = outlet

    def __str__(self):
        return 'illegal outlet id %s' % self.outlet


class OutletDevice(object):
    """
    OutletDevice - class for a Gembird USB Outlet.

    The class encapsulates the USB commands needed to control the devices.
    By default the device gets auto disposed after an interaction to ensure,
    other applications can still access the device meanwhile.
    Set `autodispose` to `False` if you want to occupy the device or have
    many actions in bulk. To dispose the device manually, call `dispose()`.

    NOTE: All methods need appropriate user permissions for the device.
    """
    def __init__(self, device):
        self.device = device
        self.device.set_configuration()
        self.autodispose = True

    def __str__(self):
        return repr(self)

    def __repr__(self):
        return '<OutletDevice%s' % repr(self.device)[7:]

    def _usb_command(self, req_type, req, value, index, bytes, timeout):
        for i in range(TRIES-1, -1, -1):
            try:
                return self.device.ctrl_transfer(
                    req_type, req, value, index, bytes, timeout)
            except USBError:
                if not i:
                    raise
                sleep(.05)

    @autodispose
    def _get_serial(self):
        return self._usb_command(
            0xa1, 0x01, (0x03 << 8) | 1, 0, bytearray(6), 500)

    def _status(self, num):
        bytes = bytearray(6)
        bytes[0] = num * 3
        return bool(self._usb_command(
            0x21 | 0x80, 0x01, (0x03 << 8) | (num * 3), 0, bytes, 500)[1])

    def _on(self, num):
        if self._status(num):
            return True
        bytes = bytearray(6)
        bytes[0] = num * 3
        bytes[1] = 0x03
        self._usb_command(0x21, 0x09, (0x03 << 8) | (num * 3), 0, bytes, 500)
        return self._status(num)

    def _off(self, num):
        if not self._status(num):
            return True
        bytes = bytearray(6)
        bytes[0] = num * 3
        self._usb_command(0x21, 0x09, (0x03 << 8) | (num * 3), 0, bytes, 500)
        return not self._status(num)

    def dispose(self):
        """
        Release device resources so other applications can use it meanwhile.
        A disposed device gets auto claimed upon the next interaction.
        """
        dispose_resources(self.device)

    @property
    def info(self):
        """
        Get various informations about the device.
        """
        return {
            'manufacturer': self.device.manufacturer,
            'product': self.device.product,
            'idVendor': '0x' + hex(self.device.idVendor)[2:].zfill(4),
            'idProduct': '0x' + hex(self.device.idProduct)[2:].zfill(4),
            'serial': self.serial,
            'devicetype': DEVICE_TYPES[self.device.idProduct][1],
            'outlets': self.outlets,
            'bus': self.device.bus,
            'address': self.device.address}

    @property
    def serial(self):
        """
        Get serial number as hex string from device.
        """
        return ':'.join(hex(i)[2:].zfill(2) for i in self._get_serial())

    @property
    def outlets(self):
        """
        Get outlet ids for device.
        """
        return DEVICE_TYPES[self.device.idProduct][0]

    @autodispose
    def status(self, num):
        """
        Get status of outlet `num` (`True` for powered on,
        `False` for powered off).
        If `num` is 'all' a dictionary of all outlet ids and their
        status is returned.
        """
        if num in self.outlets:
            return self._status(num)
        if num == 'all':
            return dict((i, self._status(i)) for i in self.outlets)
        raise OutletException(num)

    @autodispose
    def on(self, num):
        """
        Power outlet `num` on. Returns `True` on sucess, `False` on failure.
        Success is checked by an additionally status request.
        If `num` is 'all' all available outlets will get powered on and
        a dictionary of outlet ids and success is returned.
        """
        if num in self.outlets:
            return self._on(num)
        if num == 'all':
            return dict((i, self._on(i)) for i in self.outlets)
        raise OutletException(num)

    @autodispose
    def off(self, num):
        """
        Power outlet `num` off. Returns `True` on sucess, `False` on failure.
        Success is checked by an additionally status request.
        If `num` is 'all' all available outlets will get powered off and
        a dictionary of outlet ids and success is returned.
        """
        if num in self.outlets:
            return self._off(num)
        if num == 'all':
            return dict((i, self._off(i)) for i in self.outlets)
        raise OutletException(num)

    @autodispose
    def toggle(self, num):
        """
        Toggle outlet `num`. Returns `True` on sucess, `False` on failure.
        Success is checked by an additionally status request.
        If `num` is 'all' all available outlets will get toggled and
        a dictionary of outlet ids and success is returned.
        """
        if num in self.outlets:
            return self._off(num) if self._status(num) else self._on(num)
        if num == 'all':
            return dict((i, self._off(i) if self._status(i) else self._on(i))
                        for i in self.outlets)
        raise OutletException(num)


def get_devices(products=(MSISPM_OLD, SISPM, MSISPM_FLASH, MSISPM_FLASH_NEW)):
    """
    Returns a generator of Gembird USB outlet devices.
    `products` defaults to a tuple of known working Gembird device identifiers.
    Override products with caution, the usb commands might destroy a wrong device.

    NOTE: You need appropriate user permissions to access the devices.
    """
    for device in find(idVendor=VENDOR, find_all=True):
        if device.idProduct in products:
            yield OutletDevice(device)


def get_device_by_serial(serial, products=(MSISPM_OLD, SISPM, MSISPM_FLASH,
                                           MSISPM_FLASH_NEW)):
    """
    Returns the device with `serial`.
    Serial is a string of the form 'xx:xx:xx:xx:xx'. (You can get it from the
    device attribute `.serial`)
    `products` defaults to a tuple of known working Gembird device identifiers.
    Override products with caution, the usb commands might destroy a wrong device.

    NOTE: To read the serial of a device you need appropriate user permissions.
    """
    for device in get_devices(products):
        if device.serial == serial:
            return device