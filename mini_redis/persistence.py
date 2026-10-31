"""Append-only file persistence."""

import os
import threading

from mini_redis.resp import RespParser, encode_command

FSYNC_POLICIES = ("always", "everysec", "no")


class AppendOnlyFile:
    """Appends commands to a file, synced to disk per the fsync policy."""

    def __init__(self, path: str, fsync: str = "everysec") -> None:
        if fsync not in FSYNC_POLICIES:
            raise ValueError(f"unknown fsync policy {fsync!r}")
        self.path = path
        self.fsync = fsync
        self._file = open(path, "ab")  # noqa: SIM115 - kept open, see close()
        self._stop = threading.Event()
        if fsync == "everysec":
            threading.Thread(target=self._sync_every_second, daemon=True).start()

    def append(self, parts: list[bytes]) -> None:
        self._file.write(encode_command(parts))
        self._file.flush()
        if self.fsync == "always":
            os.fsync(self._file.fileno())

    def close(self) -> None:
        self._stop.set()
        self._file.flush()
        os.fsync(self._file.fileno())
        self._file.close()

    def _sync_every_second(self) -> None:
        while not self._stop.wait(1):
            try:
                os.fsync(self._file.fileno())
            except OSError, ValueError:
                return


def read_commands(path: str) -> tuple[list[list[bytes]], bool]:
    """Replay the file; a crash can leave half a command at the end, it's ignored."""
    if not os.path.exists(path):
        return [], False
    with open(path, "rb") as file:
        data = file.read()
    parser = RespParser()
    commands = parser.feed(data)
    return commands, parser.has_pending_data()


def write_snapshot(path: str, commands: list[list[bytes]]) -> None:
    """Write to a temp file and rename it, so a crash never leaves half an AOF."""
    temporary_path = f"{path}.tmp"
    with open(temporary_path, "wb") as file:
        file.writelines(encode_command(parts) for parts in commands)
        file.flush()
        os.fsync(file.fileno())
    os.replace(temporary_path, path)
