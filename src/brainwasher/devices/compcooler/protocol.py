from __future__ import annotations
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
    frame_head: Bits = Bits(hex="0x80", length=8)  # immutable
    chiller_status: D2Request = field(default_factory=D2Request)
    operation_mode: D3Request = field(default_factory=D3Request)
    temperature: BitArray = field(default_factory=lambda: BitArray(int=32, length=8))
    duration: BitArray = field(default_factory=lambda: BitArray(int=0, length=8))
    frame_tail: Bits = Bits(hex="0x78", length=8)  # immutable

    def to_bytes(self):
        aggregate = BitArray()
        for f in fields(self):
            aggregate.append(getattr(self, f.name))
        return BitArray(aggregate)


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
    frame_head: Bits = Bits(hex="0xC0", length=8)  # immutable.
    chiller_status: D2Reply = field(default_factory=lambda: D2Reply)
    operation_mode: D3Reply = field(default_factory=lambda: D3Reply)
    liquid_temperature: BitArray = field(default_factory=lambda: BitArray(int=0, length=0))
    duration: BitArray = field(default_factory=lambda: BitArray(int=0, length=8))
    frame_tail: Bits = Bits(hex="0x3F", length=8)  # immutable.

    @classmethod
    def reply_from_bytes(cls, reply_bytes: bytes) -> Reply:
        """Parse a raw reply into a Reply instance."""
        reply = Reply()  # Empty reply
        bit_stream = BitStream(reply_bytes)
        for f in fields(reply):
            attribute = getattr(reply, f.name)
            constructor = type(attribute)
            new_attr = constructor(bit_stream.read(f"bits{attribute.length}"))
            # Check Packet signature.
            if f.name in("frame_head", "frame_tail") and attribute != new_attr:
                raise ValueError(f"{f.name} does not match expected value.")
            attribute = new_attr
        return reply
