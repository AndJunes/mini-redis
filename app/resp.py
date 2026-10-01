def parse_command(data):
    lines = data.split(b"\r\n")
    if len(lines) < 3:
        return None, None
    command = lines[2].decode().upper()
    args = [line.decode() for line in lines[4::2]]
    return command, args


def encode_bulk_string(value):
    if value is None:
        return b"$-1\r\n"
    elif isinstance(value, str):
        encoded_value = value.encode()
        return f"${len(encoded_value)}\r\n".encode() + encoded_value + b"\r\n"
    else:
        raise ValueError("Unsupported value type for encoding")
