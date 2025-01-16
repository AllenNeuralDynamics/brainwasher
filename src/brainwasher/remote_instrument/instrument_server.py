"""Instrument Server for enabling remote control/monitoring of the Instrument"""

import logging
import pickle
import zmq
from threading import Thread, Event, Lock
from time import sleep
from typing import Callable
from copy import deepcopy


class InstrumentServer:
    """Interface for enabling remote control/monitoring of an instrument."""

    def __init__(self, port: str = "5555"):
        self.log = logging.getLogger(self.__class__.__name__)
        self.port = port
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUB)
        self.socket.bind("tcp://*:%s" % self.port)

        self.broadcast_calls = {}
        self.calls_lock = Lock()
        self.broadcast_threads = {}
        self.keep_broadcasting = Event()
        self.keep_broadcasting.set()

    def send(self, message: str):
        # Publish message
        # Warning: if using TCP, and no subscribers are pressent, msgs will
        #   queue up on the pubisher side.
        self.socket.send(pickle.dumps(message))

    def receive(self):
        pass

    def broadcast(self, frequency_hz: float, func: Callable, *args, **kwargs):
        """Setup periodic function call with specific arguments at a set
        frequency."""
        func_call = (func, args, tuple(sorted(kwargs.items())))  # Dicts not hashble.
        broadcast_calls = self.broadcast_calls.get(frequency_hz, set())
        if not broadcast_calls:  # Add to dict if nothing broadcasts at this freq.
            self.broadcast_calls[frequency_hz] = broadcast_calls
        with self.calls_lock:  # Prevent worker thread access while changing size.
            broadcast_calls.add(func_call)
        if frequency_hz in self.broadcast_threads:
            return
        broadcast_thread = Thread(target=self._broadcast_worker,
                                  args=[frequency_hz], daemon=True)
        broadcast_thread.start()
        self.broadcast_threads[frequency_hz] = broadcast_thread

    def _broadcast_worker(self, frequency_hz: float):
        while self.keep_broadcasting.is_set():
            # Prevent size change in self.broadcast_calls during iteration.
            with self.calls_lock:
                for func_call in self.broadcast_calls[frequency_hz]:
                    # Invoke the function and dispatch the result.
                    func = func_call[0]
                    args = func_call[1]
                    kwargs = dict(func_call[2])
                    try:
                        reply = func(*args, **kwargs)
                    except Exception as e:
                        self.log.error(f"Function: {func}({args}, {kwargs}) raised "
                                       f"an exception while executing.")
                        reply = str(e)
                    self.socket.send(pickle.dumps(reply))
            sleep(1.0/frequency_hz)

    def close(self):
        self.keep_broadcasting.clear()
        try:
            for thread in self.broadcast_threads.values():
                thread.join()
        finally:
            self.socket.close()
            self.context.term()
