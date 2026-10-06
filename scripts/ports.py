"""
Helper script to list available serial ports on the system.
"""

import serial.tools.list_ports as list_ports


def ports():
    ports = list(list_ports.comports())

    print("Available serial ports:\n")
    print(f"{'Port':<10} {'Description'}")
    print(f"{'-' * 10} {'-' * 40}")

    for p in ports:
        print(f"{p.device:<10} {p.description}")


if __name__ == "__main__":
    ports()
