"""TCP server and command-line entry point."""

import argparse
import logging
import signal
import socket
import threading
from types import FrameType

from mini_redis.commands import Database
from mini_redis.persistence import FSYNC_POLICIES
from mini_redis.resp import ProtocolError, RespParser, encode_error

HOST = "localhost"
PORT = 6379

logger = logging.getLogger(__name__)


def handle_client(connection: socket.socket, database: Database) -> None:
    parser = RespParser()
    with connection:
        try:
            while True:
                data = connection.recv(4096)
                if not data:
                    break
                try:
                    commands = parser.feed(data)
                except ProtocolError as error:
                    connection.sendall(encode_error(f"ERR Protocol error: {error}"))
                    break
                replies = b"".join(
                    database.execute_command(command) for command in commands
                )
                if replies:
                    connection.sendall(replies)
        except ConnectionResetError:
            pass


def serve(server_socket: socket.socket, database: Database) -> None:
    """Accept clients until the listening socket is closed."""
    while True:
        try:
            connection, _ = server_socket.accept()
        except OSError:
            return
        # Handle each client connection in a separate thread
        thread = threading.Thread(
            target=handle_client, daemon=True, args=(connection, database)
        )
        thread.start()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A Redis-compatible server.")
    parser.add_argument(
        "--host", default=HOST, help=f"interface to bind (default: {HOST})"
    )
    parser.add_argument(
        "--port", type=int, default=PORT, help=f"port to listen on (default: {PORT})"
    )
    parser.add_argument(
        "--aof", metavar="FILE", help="enable append-only file persistence"
    )
    parser.add_argument(
        "--appendfsync",
        choices=FSYNC_POLICIES,
        default="everysec",
        help="how often the AOF is synced to disk (default: everysec)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    database = Database()
    if args.aof:
        restored, truncated = database.enable_aof(args.aof, args.appendfsync)
        if truncated:
            logger.warning("Ignored an incomplete command at the end of %s", args.aof)
        logger.info("Restored %d keys from %s", restored, args.aof)
    server_socket = socket.create_server((args.host, args.port))

    # Closing the socket unblocks accept(), so serve() returns and the AOF
    # can be flushed before the process exits.
    def shut_down(signum: int, frame: FrameType | None) -> None:
        server_socket.close()

    signal.signal(signal.SIGINT, shut_down)
    signal.signal(signal.SIGTERM, shut_down)

    stop_sweeper = database.start_expiry_sweeper()
    logger.info("Listening on %s:%d", args.host, args.port)
    serve(server_socket, database)
    stop_sweeper.set()
    database.disable_aof()


if __name__ == "__main__":
    main()
