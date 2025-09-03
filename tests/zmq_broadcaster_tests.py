#!/usr/bin/env/python3

import pytest
from random import uniform
from brainwasher.remote_instrument.instrument_client import RouterClient
from brainwasher.remote_instrument.instrument_server import RouterServer
from time import sleep
from time import perf_counter as now


# Create a simple class to pass into the server.
class SensorArray:
    __test__ = False

    def __init__(self):
        pass

    def get_data(self, sensor_index: int = 0):
        """Get spoofed analog voltage sensor data: 0.0-5.0 [V] measurement from
            specified sensor index."""
        return {sensor_index: uniform(0., 5.)}


def test_server_creation():
    server = RouterServer()  # Create a server.


def test_server_broadcast():
    sensors = SensorArray()  # Create an object
    server = RouterServer()  # Create a server.
    # broadcast a method at 100[Hz].
    server.add_broadcast(100, sensors.get_data, 0)
    server.add_broadcast(100, sensors.get_data, 1)
    sleep(0.05)
    server.close()


def test_client_receive():
    sensor_index = 0
    sensors = SensorArray()  # Create an object
    server = RouterServer()  # Create a server.
    client = RouterClient()  # Create a client.
    # broadcast a method at 10[Hz].
    server.add_broadcast(10, sensors.get_data, sensor_index)
    # receive data.
    received_data = None
    start_time = now()
    while ((now() - start_time) < 1):
        received_data = client.receive_broadcast()
        print(f"received: {received_data}")
        assert 0.0 <= received_data[sensor_index] <= 5.0
    server.close()


def test_live_add_remove_broadcast():
    """Add, then remove a broadcast. Ensure that it has been removed."""
    sensor_index = 0
    sensors = SensorArray()  # Create an object
    server = RouterServer()  # Create a server.
    client = RouterClient()  # Create a client.
    # broadcast a method at 10[Hz].
    server.add_broadcast(10, sensors.get_data, sensor_index)
    server.remove_broadcast(sensors.get_data)
    # FIXME: thread should exit after removing the only periodic function.
    assert server.broadcaster.func_params == {}
    #assert server.broadcaster.calls_by_frequency == {}
    #assert server.broadcaster.threads.get(10, None) == None  # might need a delay.


#def test_call_remote_method():
#    sensors = SensorArray()  # Create an object
#    server = RouterServer()  # Create a server.
#    client = RouterClient()  # Create a Client.
#    reply = client.call("sensors.get_sensor_data")
