#!/usr/bin/env/python3

import pytest
from brainwasher.remote_instrument.instrument_client import InstrumentClient
from brainwasher.remote_instrument.instrument_server import InstrumentServer
from time import sleep
from time import perf_counter as now


# Create a simple class to pass into the server.
class TestInstrument:
    __test__ = False

    def __init__(self):
        pass

    def get_sensor_data(self, sensor_index: int = 0):
        print(f"Hello from device {sensor_index}.")
        return sensor_index


#def test_server_creation():
#    instrument_server = InstrumentServer()  # Create a server.


#def test_server_broadcast():
#    instrument = TestInstrument()  # Create an object
#    instrument_server = InstrumentServer()  # Create a server.
#    # broadcast a method at 100[Hz].
#    instrument_server.broadcast(100, instrument.get_sensor_data, 0)
#    instrument_server.broadcast(100, instrument.get_sensor_data, 1)
#    sleep(0.1)


def test_client_receive():
    port = "5555"
    instrument = TestInstrument()  # Create an object
    instrument_server = InstrumentServer(port=port)  # Create a server.
    instrument_client = InstrumentClient(port=port)  # Create a Client.
    # broadcast a method at 10[Hz].
    instrument_server.broadcast(10, instrument.get_sensor_data, 0)
    # receive data.
    received_data = None
    start_time = now()
    while received_data is None and ((now() - start_time) < 1):
        received_data = instrument_client.receive()
    print(f"received: {received_data}")
    assert received_data == 0
