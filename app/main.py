import socket
import threading

from app.commands import execute_command, start_expiry_sweeper
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
                # Pipelined commands are answered in order with a single send.
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
            # The server socket was closed: stop accepting clients.
            return
        # Handle each client connection in a separate thread
        thread = threading.Thread(target=handle_client, daemon=True, args=(connection,))
        thread.start()


def main():
    server_socket = socket.create_server((HOST, PORT), reuse_port=True)
    start_expiry_sweeper()
    serve(server_socket)


if __name__ == "__main__":
    main()
