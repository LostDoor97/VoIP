"""
Client STUN minimal (RFC 5389) pour découvrir l'adresse/port public UDP.
"""

import os
import socket
import struct
from typing import Optional, Tuple


MAGIC_COOKIE = 0x2112A442
BINDING_REQUEST = 0x0001
BINDING_SUCCESS_RESPONSE = 0x0101
XOR_MAPPED_ADDRESS = 0x0020
MAPPED_ADDRESS = 0x0001


def _build_binding_request() -> tuple[bytes, bytes]:
    tx_id = os.urandom(12)
    header = struct.pack("!HHI12s", BINDING_REQUEST, 0, MAGIC_COOKIE, tx_id)
    return header, tx_id


def _parse_address_attr(attr_type: int, value: bytes) -> Optional[Tuple[str, int]]:
    if len(value) < 8:
        return None

    family = value[1]
    if family != 0x01:
        return None

    if attr_type == XOR_MAPPED_ADDRESS:
        x_port = struct.unpack("!H", value[2:4])[0]
        port = x_port ^ (MAGIC_COOKIE >> 16)

        x_addr = struct.unpack("!I", value[4:8])[0]
        addr_int = x_addr ^ MAGIC_COOKIE
        ip = socket.inet_ntoa(struct.pack("!I", addr_int))
        return ip, port

    if attr_type == MAPPED_ADDRESS:
        port = struct.unpack("!H", value[2:4])[0]
        ip = socket.inet_ntoa(value[4:8])
        return ip, port

    return None


def get_stun_mapped_address(
    udp_socket: socket.socket,
    stun_host: str,
    stun_port: int = 19302,
    timeout: float = 1.5,
) -> Optional[Tuple[str, int]]:
    """
    Envoie une requête STUN Binding via un socket UDP déjà bindé,
    et retourne (ip_publique, port_public) si disponible.
    """
    request, tx_id = _build_binding_request()

    previous_timeout = udp_socket.gettimeout()
    try:
        udp_socket.settimeout(timeout)
        udp_socket.sendto(request, (stun_host, stun_port))

        data, _ = udp_socket.recvfrom(2048)
        if len(data) < 20:
            return None

        msg_type, msg_len, cookie, rx_tx_id = struct.unpack("!HHI12s", data[:20])
        if msg_type != BINDING_SUCCESS_RESPONSE:
            return None
        if cookie != MAGIC_COOKIE or rx_tx_id != tx_id:
            return None

        pos = 20
        end = 20 + msg_len
        while pos + 4 <= len(data) and pos < end:
            attr_type, attr_len = struct.unpack("!HH", data[pos:pos + 4])
            pos += 4

            if pos + attr_len > len(data):
                break

            attr_value = data[pos:pos + attr_len]
            parsed = _parse_address_attr(attr_type, attr_value)
            if parsed:
                return parsed

            padded_len = (attr_len + 3) & ~3
            pos += padded_len

        return None
    finally:
        udp_socket.settimeout(previous_timeout)
