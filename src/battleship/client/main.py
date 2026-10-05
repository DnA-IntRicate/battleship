from battleship.client.uart import SerialConnection

if __name__ == "__main__":
    print("Hello world from battleship client!")

    # UART Hello world
    with SerialConnection() as ser:
        while True:
            line = ser.readline()
            if line is not None:
                print(line)
