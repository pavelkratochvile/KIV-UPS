# SocketLib.py
# Pomocná knihovna pro odesílání a přijímání zpráv přes sockety, funguje na principu prefixu "ML" následovaného délkou zprávy.
# Vše řešeno zde na úrovních obalových funkcí nad sockety. Maximální velikost zprávy je 10 MB. 
# Príklad poslané zprávy "ML16LK:LOGIN_SUCCESS"

# Autor: Pavel Kratochvíle 2025

MAX_SIZE = 10 * 1024 * 1024
PREFIX = "ML"

# Odeslání zprávy přes socket
# Knihovna se automaticky postará o přidání prefixu a délky zprávy.
def sendMessage(sock, payload: bytes):
    length = len(payload)
    if length > MAX_SIZE:
        raise ValueError("Message too large")

    header = f"{PREFIX}{length}".encode()
    sock.sendall(header + payload)

# Přijmutí přesného počtu bajtů ze socketu
def recv_exact(sock, n: int) -> bytes:
    data = bytearray()
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("Disconnected while reading")
        data.extend(chunk)
    return bytes(data)

# Přijmutí zprávy ze socketu
# První načte prefix a poté délku, dokud nedorazí na první nečíselný znak, který je začátkem payloadu. Poté načítá payload.
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
