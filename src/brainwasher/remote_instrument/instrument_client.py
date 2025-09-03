"""Instrument client for controlling/monitoring a remote instrument. Basis for GUIs."""

import zmq
import pickle

class RouterClient:

    def __init__(self, rpc_port: str = "5555", broadcast_port: str = "5556"):
        self.rpc_client = ZMQRPCClient(rpc_port)
        self.broadcaster_client = ZMQBroadcasterClient(broadcast_port)

    def call(self, name, *args, **kwds):
        """Call a function/method and return the response."""
        return self.rpc_client.call(name, *args, **kwds)

    def receive_broadcast(self):
        """Receive the results of periodically called functions"""
        return self.broadcaster_client.receive()

    def close(self):
        self.broadcaster_client.close()


class ZMQRPCClient:

    def __init__(self, port: str = "5555"):
        # Receive periodic broadcasted messages setup.
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.full_address = f"tcp://localhost:{port}"
        self.socket.connect(self.full_address)
        #self.socket.subscribe("")  # Subscribe to all topics.

    def call(self, callable_name: str, *args, **kwargs):
        """Call a function and return the result."""
        self.socket.send(pickle.dumps((callable_name, args, kwargs)))
        return pickle.loads(self.socket.recv())


class ZMQBroadcasterClient:
    """Connect to an instrument server (likely running on an actual instrument)
    and interact with it via remote control. (A remote procedure call interface)"""

    def __init__(self, port):
        # Receive periodic broadcasted messages setup.
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.SUB)
        self.full_address = f"tcp://localhost:{port}"
        self.socket.connect(self.full_address)
        self.socket.subscribe("")  # Subscribe to all topics.

    def receive(self):
        # Publish message
        return pickle.loads(self.socket.recv())

    def close(self):
        self.socket.close()

