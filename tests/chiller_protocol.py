#!/usr/bin/env/python3

import pytest
from brainwasher.devices.compcooler.protocol import Request, Reply
from bitstring import BitArray


def test_request_mutability():
    req = Request()
    # alter fields.
    req.temperature.int = 10
    req.duration.int = 30
    req.chiller_status.pump = True
    req.chiller_status.chiller = True
    # Check to make sure the right bits were set.
    assert req.chiller_status == BitArray("0x60")
    assert req.temperature.int == 10
    assert req.duration.int == 30


def test_many_request_instances():
    req = Request()
    req2 = Request()
    # alter fields.
    req.temperature.int = 10
    req2.temperature.int = 32
    assert req.temperature.int == 10
    assert req2.temperature.int == 32


def test_reply():
    raw_reply = b"\xC0"
    pass