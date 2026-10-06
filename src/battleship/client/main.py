import os
import sys

from battleship.client.uart import DEFAULT_COM_PORT, SerialConnection


def main():
    print("Hello world from battleship client!")

    port = os.environ.get("BATTLESHIP_PORT") or DEFAULT_COM_PORT
    try:
        with SerialConnection(port=port) as ser:
            print(f"Connected to {port}.")

            # UART Hello world
            while True:
                line = ser.readline(timeout=0.1)
                if line is not None:
                    print(line)
    except Exception as e:
        sys.exit(f"Serial error on {port}: {e}")
    except KeyboardInterrupt:
        print("Exiting...")
        sys.exit(0)
