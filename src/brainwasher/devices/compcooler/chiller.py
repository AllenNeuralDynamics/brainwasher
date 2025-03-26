"""Compcooler chiller driver"""

import logging
from brainwasher.devices.compcooler.protocol import Request, Reply


class Chiller:
    """Compcooler chiller. (Request-Reply interface.)

    This device is controlled by writing a single frame containing multiple
    settings and receiving the reply containing the settings that took place.
    """

    def __init__(self):
        self.log = logging.getLogger(__name__)
        self._request = Request()
        #self._reply = Reply()

    def enable(self):
        # Send the latest request and
        self._request.chiller_status.chiller = True
        self._send(self._request)

    def disable(self):
        pass

    def set_temperature_c(self):
        pass

    def get_temperature_c(self):
        pass

    def _apply_config(self):
        pass

    def _get_config(self):
        pass

    def _send(self, request: Request):
        print(f"sending: ")
        print(request.to_bytes())
