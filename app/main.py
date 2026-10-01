import socket
import threading

from app.resp import encode_bulk_string, parse_command

HOST = "localhost"
PORT = 6379

redis_store = {}


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
                    response = encode_bulk_string(args[0])
                    connection.sendall(response)
            elif command == "SET":
                if len(args) < 2:
                    connection.sendall(
                        b"-ERR wrong number of arguments for 'SET' command\r\n"
                    )
                else:
                    key = args[0]
                    value = args[1]
                    redis_store[key] = value
                    connection.sendall(b"+OK\r\n")
            elif command == "GET":
                if len(args) < 1:
                    connection.sendall(
                        b"-ERR wrong number of arguments for 'GET' command\r\n"
                    )
                else:
                    key = args[0]
                    value = redis_store.get(key)
                    if value is None:
                        connection.sendall(b"$-1\r\n")
                    else:
                        response = encode_bulk_string(value)
                        connection.sendall(response)
            elif command == "DEL":
                if len(args) < 1:
                    connection.sendall(
                        b"-ERR wrong number of arguments for 'DEL' command\r\n"
                    )
                else:
                    deleted_count = 0
                    for key in args:
                        if key in redis_store:
                            del redis_store[key]
                            deleted_count += 1
                    response = f":{deleted_count}\r\n".encode()
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
