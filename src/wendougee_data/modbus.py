"""Safe, read-only Modbus RTU request construction."""

from .crc import append_crc

READ_HOLDING_REGISTERS = 0x03
DEFAULT_SLAVE_ADDRESS = 0x01
MAX_READ_REGISTER_COUNT = 125


def build_read_holding_registers_request(
    start_address: int,
    count: int,
    slave_address: int = DEFAULT_SLAVE_ADDRESS,
) -> bytes:
    """Build a function-03 request for a bounded holding-register range."""
    if not 0 <= slave_address <= 0xFF:
        raise ValueError("slave address must fit in one byte")
    if not 0 <= start_address <= 0xFFFF:
        raise ValueError("start address must fit in two bytes")
    if not 1 <= count <= MAX_READ_REGISTER_COUNT:
        raise ValueError(
            f"count must be between 1 and {MAX_READ_REGISTER_COUNT} registers"
        )
    if start_address + count > 0x10000:
        raise ValueError("requested address range exceeds the register address space")

    payload = bytes((slave_address, READ_HOLDING_REGISTERS))
    payload += start_address.to_bytes(2, byteorder="big")
    payload += count.to_bytes(2, byteorder="big")
    return append_crc(payload)
