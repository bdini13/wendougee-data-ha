"""CRC16-Modbus support for Wendougee wire frames."""


def crc16_modbus(data: bytes) -> int:
    """Return the CRC16-Modbus value for *data*."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc


def append_crc(data: bytes) -> bytes:
    """Append a CRC in Modbus wire order (low byte, then high byte)."""
    return data + crc16_modbus(data).to_bytes(2, byteorder="little")
