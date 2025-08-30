"""Instrument Server for enabling remote control/monitoring of the Instrument"""

import logging
import pickle
import zmq
from threading import Thread, Event, Lock
from time import sleep
from typing import Callable
from copy import deepcopy


class RouterServer:
    """Interface for enabling remote control/monitoring of one or more object
       instances."""
    def __init__(self, rpc_port: str = "5555", broadcast_port: str = "5556"):
        self.rpc = ZMQRPC(rpc_port)
        self.broadcaster = ZMQBroadcaster(broadcast_port)

    def call(self, func_name: str, *args, **kwargs):
        return self.rpc.call(func_name, *args, **kwargs)

    def receive(self):
        pass

    def add_broadcast(self, frequency_hz: float, func: Callable, *args, **kwargs):
        self.broadcaster.add(frequency_hz, func, *args, **kwargs)

    def remove_broadcast(self, func):
        self.broadcaster.remove(func)

    def close(self):
        self.broadcaster.close()


class ZMQRPC:

    def __init__(self, port: str = "5555"):
        self.log = logging.getLogger(self.__class__.__name__)
        self.port = port
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REP)
        self.socket.bind("tcp://*:%s" % self.port)
        self.keep_receiving = Event()
        self.keep_receiving.set()

    def receive_worker(self):
        while self.keep_receiving.is_set():
            # FIXME: actually lookup and call the function.
            pickled_request = self.socket.recv()
            request = pickle.loads(pickled_request)


class ZMQBroadcaster:
    """Broadcaster for periodically calling a callable with specific args/kwargs
       at a specified frequency."""

    def __init__(self, port: str = "5556"):
        self.log = logging.getLogger(self.__class__.__name__)
        self.port = port
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUB)
        self.socket.bind("tcp://*:%s" % self.port)

        self.func_params: Dict[Callable, Tuple] = {}
        self.calls_by_frequency: Dict[float, set] = {}
        self.call_frequencies: Dict[Callable, float] = {}
        self.calls_lock = Lock()
        self.threads: Dict[float, Thread] = {}
        self.keep_broadcasting = Event()
        self.keep_broadcasting.set()

    def add(self, frequency_hz: float, func: Callable, *args, **kwargs):
        """Setup periodic function call with specific arguments at a set
        frequency.

        If the function is already being broadcasted, update the broadcast
        parameters.
        """
        # TODO: handle case where this broadcast is already stored, but at a
        # different frequency or with different parameters.
        # TODO: if calls already exist at this frequency, lock out access to
        # these containers.

        # Add/update func params and call frequency.
        self.func_params[func] = (args, tuple(sorted(kwargs.items()))) # Dicts aren't hashable.
        self.call_frequencies[func] = frequency_hz
        # Store call by frequency.
        call_names = self.calls_by_frequency.get(frequency_hz, set())
        if not call_names:  # Add to dict if nothing broadcasts at this freq.
            self.calls_by_frequency[frequency_hz] = call_names
            call_names.add(func)
        else:
            with self.calls_lock:  # TODO: do this by frequency?
                call_names.add(func)
        if frequency_hz in self.threads: # Thread already exists.
            return
        # Create a new thread for calls made at this frequency.
        broadcast_thread = Thread(target=self._broadcast_worker,
                                  name=f"{frequency_hz:.3f}[Hz]_broadcast_thread",
                                  args=[frequency_hz], daemon=True)
        broadcast_thread.start()
        self.threads[frequency_hz] = broadcast_thread

    def remove(self, func: Callable):
        """Remove a broadcasting function call that was previously added."""
        if func not in self.func_params:
            raise ValueError(f"Cannot remove {str(func)}. "
                             "Call is not being broadcasted.")
        # Delete all references!
        call_frequency = self.call_frequencies[func]
        with self.calls_lock:  # TODO: do this by frequency?
            self.calls_by_frequency[call_frequency].remove(func)
            del self.func_params[func]
            del self.call_frequencies[func]
       # Broadcast thread for this frequency will exit if it has nothing to do.

    def _broadcast_worker(self, frequency_hz: float):
        """Periodically broadcast all functions at the specified frequency.
        If there's nothing to do, exit."""
        while self.keep_broadcasting.is_set():
            # Prevent size change in self.broadcast_calls during iteration.
            with self.calls_lock:
                if not self.calls_by_frequency[frequency_hz]: # Nothing to do!
                    return
                for func in self.calls_by_frequency[frequency_hz]:
                    # Invoke the function and dispatch the result.
                    params = self.func_params[func]
                    args = params[0]
                    kwargs = dict(params[1])
                    try:
                        reply = func(*args, **kwargs)
                    except Exception as e:
                        self.log.error(f"Function: {func}({args}, {kwargs}) raised "
                                       f"an exception while executing.")
                        reply = str(e)
                    # Warning: if using TCP, and no subscribers are present,
                    #   msgs will queue up on the pubisher side.
                    self.socket.send(pickle.dumps(reply))
            sleep(1.0/frequency_hz)

    def close(self):
        self.keep_broadcasting.clear()
        try:
            for thread in self.threads.values():
                thread.join()
        finally:
            self.socket.close()
            self.context.term()
