"""Instrument client for controlling/monitoring a remote instrument. Basis for GUIs."""

import zmq
import pickle


class InstrumentClient:
    """Connect to an instrument server (likely running on an actual instrument)
    and interact with it via remote control. (A remote procedure call interface)"""

    def __init__(self, port):
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.SUB)
        self.full_address = "tcp://localhost:%s" % port
        self.socket.connect(self.full_address)
        self.socket.subscribe("")  # Subscribe to all topics.

    def receive(self):
        # Publish message
        return pickle.loads(self.socket.recv())

    def close(self):
        self.socket.close()
