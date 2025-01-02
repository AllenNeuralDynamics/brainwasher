"""Generic Base Class Mixer"""


class Mixer:

    def set_mixing_speed(self, rpm: float):
        raise NotImplementedError

    def start_mixing(self):
        raise NotImplementedError

    def stop_mixing(self):
        raise NotImplementedError
