#!/usr/bin/env/python3

import pytest
from brainwasher.devices.compcooler.protocol import Request, Reply
from brainwasher.devices.compcooler.chiller import Chiller
from bitstring import BitArray


def test_request_mutability():
    req = Request()
    # alter fields.
    req.temperature.uint = 10
    req.duration.uint = 30
    req.chiller_status.pump = True
    req.chiller_status.chiller = True
    # Check to make sure the right bits were set.
    assert req.chiller_status == BitArray("0x60")
    assert req.temperature.uint == 10
    assert req.duration.uint == 30


def test_many_request_instances():
    req = Request()
    req2 = Request()
    # alter fields.
    req.temperature.uint = 10
    req2.temperature.uint = 32
    assert req.temperature.uint == 10
    assert req2.temperature.uint == 32

def test_request_to_bytes():
    chiller = Chiller()
    assert chiller._request.to_bytes() == b"\x80\x00\x00 \x00\x78"

def test_reply():
    raw_reply_bytes = b"\xC0\x00\x00\x00\x00\x3F"
    reply = Reply.from_bytes(raw_reply_bytes)
    assert reply.frame_head.uint == 0xC0
    assert reply.frame_tail.uint == 0x3F
    assert reply.measured_temperature.uint == 0
