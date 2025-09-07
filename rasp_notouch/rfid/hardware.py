# rfid/hardware.py
from gpiozero import DigitalOutputDevice

_lock = None

def get_lock():
    global _lock
    if _lock is None:
        _lock = DigitalOutputDevice(21, active_high=True)
    return _lock
