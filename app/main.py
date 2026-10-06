import argparse
import socket
import threading

from app.commands import enable_aof, execute_command, start_expiry_sweeper
from app.persistence import FSYNC_POLICIES
from app.resp import ProtocolError, RespParser, encode_error

HOST = "localhost"
PORT = 6379


def handle_client(connection):
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
                replies = b"".join(execute_command(command) for command in commands)
                if replies:
                    connection.sendall(replies)
        except ConnectionResetError:
            pass


def serve(server_socket):
    while True:
        try:
            connection, _ = server_socket.accept()
        except OSError:
            return
        # Handle each client connection in a separate thread
        thread = threading.Thread(target=handle_client, daemon=True, args=(connection,))
        thread.start()


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="A Redis-compatible server.")
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


def main(argv=None):
    args = parse_args(argv)
    if args.aof:
        restored, truncated = enable_aof(args.aof, args.appendfsync)
        if truncated:
            print(f"Ignored an incomplete command at the end of {args.aof}")
        print(f"Restored {restored} keys from {args.aof}", flush=True)
    server_socket = socket.create_server((HOST, args.port), reuse_port=True)
    start_expiry_sweeper()
    print(f"Listening on {HOST}:{args.port}", flush=True)
    serve(server_socket)


if __name__ == "__main__":
    main()
