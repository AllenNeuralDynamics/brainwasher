from __future__ import annotations

import sys

"""Compcooler chiller driver"""

from dataclasses import dataclass, field, fields
import bitstring
from bitstring import Bits, BitArray, BitStream
from typing import Optional, Union

bitstring.options.lsb0 = True


class D2Request(BitArray):

    def __init__(self):
        super().__init__()
        self.append("0x00")  # Workaround to prepulate BitArray as
                                 # calling super here doesn't work.

    @property
    def communication(self):
        return bool(self[7])

    @communication.setter
    def communication(self, value):
        self.set(value, 7)

    @property
    def chiller(self):
        return bool(self[6])

    @chiller.setter
    def chiller(self, value):
        self.set(value, 6)

    @property
    def pump(self):
        return bool(self[5])

    @pump.setter
    def pump(self, value):
        self.set(value, 5)

    @property
    def enable(self):
        """aka "quickstart" bit."""
        return bool(self[4])

    @enable.setter
    def enable(self, value):
        self.set(value, 4)


class D3Request(BitArray):

    def __init__(self):
        super().__init__()
        self.append("0x00")  # Workaround to prepulate BitArray as
                             # calling super here doesn't work.

    @property
    def timer(self):
        return bool(self[6])

    @timer.setter
    def timer(self, value):
        self.set(value, 6)

    @property
    def sleep(self):
        return bool(self[5])

    @sleep.setter
    def sleep(self, value):
        self.set(value, 5)

    @property
    def cooling(self):
        return bool(self[4])

    @cooling.setter
    def cooling(self, value):
        self.set(value, 4)

    @property
    def heating(self):
        return bool(self[3])

    @heating.setter
    def heating(self, value):
        self.set(value, 3)

    @property
    def set_temp(self):
        return bool(self[0])

    @set_temp.setter
    def set_temp(self, value):
        self.set(value, 0)


@dataclass
class Request:
    """Dataclass to enable changing of individual fields within the packet.

    .. code-block:: python
        request = Request()
        request.enable = True  # start the system.
        request.temperature.int = 33  # Set temperature field.

    """
    frame_head: Bits = Bits(hex="0x80", length=8)  # immutable
    chiller_status: D2Request = field(default_factory=D2Request)
    operation_mode: D3Request = field(default_factory=D3Request)
    temperature: BitArray = field(default_factory=lambda: BitArray(int=32, length=8))
    duration: BitArray = field(default_factory=lambda: BitArray(int=0, length=8))
    frame_tail: Bits = Bits(hex="0x78", length=8)  # immutable

    def to_bytes(self):
        """Return a bytes representation of the Request packet for easy
        dispatch over an open serial port."""
        aggregate = BitArray()
        for f in fields(self):
            aggregate.append(getattr(self, f.name))
        bit_array = BitArray(aggregate)
        # Convert to big-endian for dispatch as-is from a serial port.
        if sys.byteorder == 'little':
            bit_array.byteswap()
        return bytes(bit_array)


class D2Reply(BitArray):
    def __init__(self, auto: Optional[Union[BitsType, int]] = None, /, **kwargs):
        super().__init__(auto=auto, length=8, **kwargs)

    @property
    def chiller(self):
        return bool(self[7])

    @property
    def pump(self):
        return bool(self[6])

    @property
    def compressor(self):
        return bool(self[5])

    @property
    def heating(self):
        return bool(self[4])

    @property
    def fan_on(self):
        return bool(self[3])

    @property
    def pump_on(self):
        return bool(self[2])

    @property
    def sensor_fault(self):
        return bool(self[1])

    @property
    def refrigerant_short(self):
        return bool(self[0])


class D3Reply(BitArray):

    def __init__(self, auto: Optional[Union[BitsType, int]] = None, /, **kwargs):
        super().__init__(auto=auto, length=8, **kwargs)

    @property
    def timer(self):
        return bool(self[6])

    @property
    def sleep(self):
        return bool(self[5])

    @property
    def cooling(self):
        return bool(self[4])

    @property
    def heating(self):
        return bool(self[3])

    @property
    def water_shortage(self):
        return bool(self[2])

    @property
    def water_less(self):
        return bool(self[1])

    @property
    def temp_setting(self):
        return bool(self[0])


@dataclass
class Reply:
    """Dataclass to enable changing of individual fields within the packet.

    .. code-block:: python
        reply = Reply()
        print(reply.chiller_status.chiller)  # If True, we are chilling.
        print(reply.measured_temperature)

    """
    frame_head: BitArray = BitArray(hex="0xC0", length=8)
    chiller_status: D2Reply = field(default_factory=lambda: D2Reply)
    operation_mode: D3Reply = field(default_factory=lambda: D3Reply)
    measured_temperature: BitArray = field(default_factory=lambda: BitArray(int=0, length=8))
    duration: BitArray = field(default_factory=lambda: BitArray(int=0, length=8))
    frame_tail: BitArray = BitArray(hex="0x3F", length=8)

    @classmethod
    def from_bytes(cls, reply_bytes: bytes) -> Reply:
        """Parse a raw reply into a Reply instance."""
        reply = Reply()  # Empty reply
        bit_stream = BitStream(reply_bytes)
        # Convert to big-endian for dispatch as-is from a serial port.
        if sys.byteorder == 'little':
            bit_stream.byteswap()
        for f in fields(reply):
            attribute = getattr(reply, f.name)
            constructor = eval(f.type)
            # Note: cannot do attribute.length because inheritance from  BitArray is buggy.
            new_word = hex(bit_stream.read(f"bits8").uint)
            new_attr = constructor(new_word)
            # Check Packet signature.
            if f.name in ("frame_head", "frame_tail") and attribute != new_attr:
                raise ValueError(f"{f.name} does not match expected value."
                                 f"Expected: {attribute}, actual: {new_attr}")
            attribute = new_attr
        return reply
