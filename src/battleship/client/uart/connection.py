import threading

import serial

# On Windows this can be COM3 or COM4
DEFAULT_COM_PORT: str = "COM3"

class SerialConnection:
    """
    Threaded serial connection to a UART device.

    Opens the configured port on construction and starts a background thread
    that continuously drains incoming bytes into an internal buffer. The
    `read*` methods are non-blocking - they return buffered data immediately,
    or `None` if nothing is available yet.

    It is preffered to use this class as a context manager so the
    reader thread stops and the port is released on exit.
    """

    port: str = DEFAULT_COM_PORT
    baudrate: int = 115200
    bytesize = serial.EIGHTBITS
    parity = serial.PARITY_NONE
    stopbits = serial.STOPBITS_ONE
    timeout: float = 0.1

    def __init__(self, port: str | None = None):
        """Initializes this multithreaded serial connection."""
        self.port = port or self.port

        self._conn = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=self.bytesize,
            parity=self.parity,
            stopbits=self.stopbits,
            timeout=self.timeout,
        )
        self._conn.reset_input_buffer()

        self._buffer = bytearray()
        self._cond = threading.Condition()
        self._stop_event = threading.Event()
        self._error: Exception | None = None

        self._thread = threading.Thread(target=self._reader_loop, name="serial-reader", daemon=True)
        self._thread.start()

    # For use in with-statements
    def __enter__(self):
        return self

    # For use in with-statements
    def __exit__(self, *exc):
        self.close()

    # Background reader
    def _reader_loop(self):
        while not self._stop_event.is_set():
            try:
                # Waits up to 'timeout' for 1 byte, then grabs everything pending
                data = self._conn.read(self._conn.in_waiting or 1)
            except (serial.SerialException, OSError) as e:
                with self._cond:
                    self._error = e
                    self._cond.notify_all()
                return

            if data:
                with self._cond:
                    self._buffer.extend(data)
                    self._cond.notify_all()

    def _pop(self, n: int) -> str:
        chunk = bytes(self._buffer[:n])
        del self._buffer[:n]

        return chunk.replace(b"\x00", b"").decode("utf-8", errors="replace").rstrip()

    def _raise_if_failed(self):
        if self._error is not None:
            raise self._error

    @property
    def in_waiting(self) -> int:
        """Bytes buffered and ready to be read."""
        with self._cond:
            return len(self._buffer)

    def read(self, size: int, timeout: float = 0.0) -> str | None:
        """
        Return up to `size` buffered bytes, or None if nothing is available.

        With `timeout > 0`, waits up to that long for at least one byte.
        """
        with self._cond:
            self._cond.wait_for(lambda: self._buffer or self._error is not None, timeout)
            if not self._buffer:
                self._raise_if_failed()
                return None

            return self._pop(size)

    def read_until(
        self, expected: bytes, size: int | None = None, timeout: float = 0.0
    ) -> str | None:
        """
        Return data up to and including `expected` once a full message has
        arrived, else None. Partial lines stay buffered until complete.
        """

        def end_index() -> int | None:
            i = self._buffer.find(expected)
            if i != -1:
                end = i + len(expected)
                return min(end, size) if size else end

            if size and len(self._buffer) >= size:
                return size

            return None

        with self._cond:
            self._cond.wait_for(lambda: end_index() is not None or self._error is not None, timeout)
            end = end_index()

            if end is None:
                self._raise_if_failed()
                return None

            return self._pop(end)

    def readline(self, timeout: float = 0.0) -> str | None:
        return self.read_until(b"\n", timeout=timeout)

    def write(self, data: bytes):
        self._conn.write(data)
        self._conn.flush()

    def close(self):
        self._stop_event.set()
        self._thread.join(timeout=self.timeout * 2 + 1)
        self._conn.close()
