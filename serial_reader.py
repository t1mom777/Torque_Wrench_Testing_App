import serial
import time
import re

def parse_range(range_str: str):
    """Converts a range string like '67.2 - 72.8' into a tuple of floats (67.2, 72.8)."""
    low_str, high_str = range_str.split('-')
    return float(low_str.strip()), float(high_str.strip())

def within_allowance(target: float, range_str: str) -> bool:
    """Returns True if target is within the numeric bounds defined by range_str."""
    low, high = parse_range(range_str)
    return low <= target <= high

def parse_torque_value(line: str):
    """
    Extracts the first float from the string.
    E.g. "HI 301.5 ft.lb" -> 301.5.
    """
    match = re.search(r"([\d.]+)", line)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None

def find_fits_in_selected_row(target: float, row: dict) -> list:
    """
    Checks each allowance (allowance1, allowance2, allowance3) of 'row'
    to see if target is within range. Returns a list of matching allowances,
    sorted by how close target is to the center of the range.
    """
    fits = []
    for i in range(1, 4):
        key = f"allowance{i}"
        rng_str = row[key]
        if within_allowance(target, rng_str):
            low, high = parse_range(rng_str)
            mid = (low + high) / 2.0
            diff = abs(mid - target)
            fits.append({
                "row": row,
                "allowance_index": i,
                "range_str": rng_str,
                "diff": diff
            })
    fits.sort(key=lambda x: x["diff"])
    return fits

def read_from_serial(port: str, baudrate: int, callback, stop_event) -> None:
    """
    Opens the serial port and continuously reads lines.
    When a valid float is parsed, callback(float_value) is invoked.
    The loop exits when stop_event is set.
    """
    try:
        with serial.Serial(port, baudrate, timeout=1) as ser:
            while not stop_event.is_set():
                line = ser.readline().decode('utf-8', errors='replace').strip()
                if line:
                    target_torque = parse_torque_value(line)
                    if target_torque is not None:
                        callback(target_torque)
                time.sleep(0.01)
    except Exception as e:
        print("Serial read error:", e)
