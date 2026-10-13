import os
import sys

from battleship.client.uart import DEFAULT_COM_PORT, SerialConnection


def main():
    print("Hello world from battleship client!")

    port = os.environ.get("BATTLESHIP_PORT") or DEFAULT_COM_PORT
    try:
        with SerialConnection(port=port) as conn:
            print(f"Connected to {port}.")

            # recv_message_from_server_demo(conn)
            send_message_to_server_demo(conn)
    except Exception as e:
        sys.exit(f"Serial error on {port}: {e}")
    except KeyboardInterrupt:
        print("Exiting...")
        sys.exit(0)


def recv_message_from_server_demo(conn: SerialConnection):
    # UART Hello world
    while True:
        line = conn.readline(timeout=0.1)
        if line is not None:
            print(line)


def send_message_to_server_demo(conn: SerialConnection):
    # Allows the user to type messages, sends to server on enter
    while True:
        line = input("\n")
        if line:
            line = line.strip() + "\r\n"
            conn.write(line.encode("UTF-8"))

        # Receive replies and print them
        reply = conn.readline(timeout=0.1)
        if reply is not None:
            print(f"REPLY: {reply}")
