MAX_SIZE = 10 * 1024 * 1024
PREFIX = "ML"

def sendMessage(sock, payload: bytes):
    length = len(payload)
    if length > MAX_SIZE:
        raise ValueError("Message too large")

    header = f"{PREFIX}{length}".encode()  # ML23
    sock.sendall(header + payload)

def recv_exact(sock, n: int) -> bytes:
    data = bytearray()
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("Disconnected while reading")
        data.extend(chunk)
    return bytes(data)


def recvMessage(sock):
    prefix = recv_exact(sock, 2).decode()
    if prefix != "ML":
        raise ValueError(f"Invalid message prefix: {prefix}")

    length_str = ""

    while True:
        ch = sock.recv(1)
        if not ch:
            raise ConnectionError("Disconnected while reading length")

        ch = ch.decode()

        if ch.isdigit():
            length_str += ch
        else:
            # první ne-číslo patří payloadu
            first_payload_byte = ch.encode()
            break

    if not length_str:
        raise ValueError("Length missing after ML")

    length = int(length_str)
    if length > MAX_SIZE:
        raise ValueError("Message too large")

    payload = first_payload_byte
    if length > 1:
        payload += recv_exact(sock, length - 1)

    return payload
