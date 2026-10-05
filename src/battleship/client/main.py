from battleship.client.uart import SerialConnection


def main():
    print("Hello world from battleship client!")

    # UART Hello world
    with SerialConnection() as ser:
        while True:
            line = ser.readline()
            if line is not None:
                print(line)
