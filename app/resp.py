def parse_command(data):
    lines = data.split(b"\r\n")
    if len(lines) < 3:
        return None, None
    command = lines[2].decode().upper()
    args = [line.decode() for line in lines[4::2]]
    return command, args
