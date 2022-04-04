#!/usr/bin/env python3

import json
import os
import os.path
import socket
import sys
from json.decoder import JSONDecodeError
from threading import Thread

SOCK_PATH = "/tmp/socket_test.s"


def deffun(x, _):
    print(f"recieved {x}")


class SockServer:
    def __init__(self, socket_path=SOCK_PATH, dispatch_function=None, async_listen=True):
        self.socket_path = socket_path
        if dispatch_function is None:
            self.dispatcher = self.__class__.json_dispatch
        else:
            self.dispatcher = dispatch_function
        self.async_listen = async_listen
        self.thread: Thread = None
        self.socket: socket.socket = None
        self.commands: dict = {}
        self.serve()

    @staticmethod
    def json_dispatch(data: bytes, conn: socket.socket, addr, socket_server):
        data_dict = {}
        try:
            data_dict = json.loads(data.decode())
        except JSONDecodeError as e:
            err = f"Recieved malformed JSON Data: {e}\n"
            err += str(data)
            conn.sendall(json.dumps({"error": err}).encode())
            return
        if not data_dict.get("command"):
            err = f"Unrecognized data format: {data_dict}"
            conn.sendall(json.dumps({"error": err}).encode())
            return
        cmd = data_dict["command"]
        if not socket_server.commands.get(cmd):
            err = f"Unrecognized command: {data_dict['command']} {data_dict}"
            conn.sendall(json.dumps({"error": err}).encode())
            return
        resp = socket_server.commands[cmd](data_dict)
        conn.sendall(json.dumps(resp).encode())

    def register_command(self, command: str, fun):
        self.commands[command] = fun

    def serve(self):
        global SERVER_SOCKET
        if os.path.exists(self.socket_path):
            os.remove(self.socket_path)
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket = server
        server.bind(self.socket_path)
        if self.async_listen:
            self.thread = Thread(target=self.listen, daemon=True, name=self.socket_path, args=())
            self.thread.start()

    def listen(self):
        while True:
            try:
                self.socket.listen(1)
                conn, addr = self.socket.accept()
                recieved_data = conn.recv(1024)
                if recieved_data:
                    if self.dispatcher:
                        self.dispatcher(recieved_data.strip(), conn, addr, self)
                    else:
                        print("No callback defined")
                    conn.close()
            except OSError as e:
                print(f"OS Error: {e}")


def request(socket_path, request_data: dict) -> dict:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(socket_path)
    data = str(json.dumps(request_data)).encode()
    sock.sendall(data)
    answer = sock.recv(1024 * 16).decode()
    sock.close()
    return json.loads(answer)


if __name__ == "__main__":
    len(sys.argv) > 1 or exit(1)
    print(sys.argv)
    if sys.argv[1] == "server":
        print("server")
        SERVER = SockServer()
    else:
        client(SOCK_PATH, "tuddls")
