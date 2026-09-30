import socket
import threading

from app.resp import parse_command

HOST = "localhost"
PORT = 6379


def handle_client(connection):
    with connection:
        while True:
            data = connection.recv(1024)
            if not data:
                break
            command, args = parse_command(data)
            if command == "PING":
                connection.sendall(b"+PONG\r\n")
            elif command == "ECHO":
                if not args:
                    connection.sendall(
                        b"-ERR wrong number of arguments for 'ECHO' command\r\n"
                    )
                else:
                    value = args[0].encode()
                    response = f"${len(value)}\r\n".encode() + value + b"\r\n"
                    connection.sendall(response)
            else:
                connection.sendall(b"-ERR unknown command\r\n")


def run_server():
    # Create a server socket and listen for incoming connections
    server_socket = socket.create_server((HOST, PORT), reuse_port=True)
    while True:
        connection, _ = server_socket.accept()
        # Handle each client connection in a separate thread
        thread = threading.Thread(target=handle_client, daemon=True, args=(connection,))
        thread.start()


def main():
    run_server()


if __name__ == "__main__":
    main()
