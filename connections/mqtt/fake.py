"""A tiny MQTT 3.1.1 broker for the tests: connect (with a username and password), subscribe with + and # wildcards,
publish at QoS 0 or 1, retained messages, ping and disconnect. Enough for paho-mqtt, which exported programs use."""
import socketserver
import struct
import threading
import time

USER, PASSWORD = "mqtt-user", "mqtt-pass"


def matches(sub, topic):
    a, b = sub.split("/"), topic.split("/")
    for i, part in enumerate(a):
        if part == "#":
            return True
        if i >= len(b) or (part != "+" and part != b[i]):
            return False
    return len(a) == len(b)


class Broker:
    def __init__(self):
        self.lock = threading.Lock()
        self.clients = []          # (handler, [subscriptions])
        self.retained = {}
        self.published = []       # (topic, text, retain) from clients

    def start(self):
        broker = self

        class Handler(socketserver.BaseRequestHandler):
            def read(self, n):
                buf = b""
                while len(buf) < n:
                    chunk = self.request.recv(n - len(buf))
                    if not chunk:
                        raise ConnectionError
                    buf += chunk
                return buf

            def packet(self):
                head = self.read(1)[0]
                mult, length = 1, 0
                while True:
                    b = self.read(1)[0]
                    length += (b & 127) * mult
                    mult *= 128
                    if not b & 128:
                        break
                return head, self.read(length) if length else b""

            def send(self, head, body=b""):
                n, enc = len(body), b""
                while True:
                    d, n = n % 128, n // 128
                    enc += bytes([d | (128 if n else 0)])
                    if not n:
                        break
                with self.wlock:
                    self.request.sendall(bytes([head]) + enc + body)

            def deliver(self, topic, text, retain=False):
                t = topic.encode()
                self.send(0x30 | (1 if retain else 0), struct.pack(">H", len(t)) + t + text.encode())

            def handle(self):
                self.wlock, subs = threading.Lock(), []
                try:
                    head, body = self.packet()
                    if head >> 4 != 1:
                        return
                    flags, i = body[7], 10
                    i += 2 + struct.unpack(">H", body[i:i + 2])[0]  # client id
                    user = pw = None
                    if flags & 0x04:  # will
                        i += 2 + struct.unpack(">H", body[i:i + 2])[0]
                        i += 2 + struct.unpack(">H", body[i:i + 2])[0]
                    if flags & 0x80:
                        n = struct.unpack(">H", body[i:i + 2])[0]
                        user = body[i + 2:i + 2 + n].decode()
                        i += 2 + n
                    if flags & 0x40:
                        n = struct.unpack(">H", body[i:i + 2])[0]
                        pw = body[i + 2:i + 2 + n].decode()
                    if (user, pw) != (USER, PASSWORD):
                        self.send(0x20, b"\x00\x05")  # not authorised
                        return
                    self.send(0x20, b"\x00\x00")
                    with broker.lock:
                        broker.clients.append((self, subs))
                    while True:
                        head, body = self.packet()
                        kind = head >> 4
                        if kind == 3:  # PUBLISH
                            qos, retain = (head >> 1) & 3, head & 1
                            n = struct.unpack(">H", body[:2])[0]
                            topic, i = body[2:2 + n].decode(), 2 + n
                            if qos:
                                pid = body[i:i + 2]
                                i += 2
                                self.send(0x40, pid)
                            broker.publish(topic, body[i:].decode("utf-8", "replace"), bool(retain), from_client=True)
                        elif kind == 8:  # SUBSCRIBE
                            pid, i, granted, new = body[:2], 2, b"", []
                            while i < len(body):
                                n = struct.unpack(">H", body[i:i + 2])[0]
                                new.append(body[i + 2:i + 2 + n].decode())
                                i += 3 + n
                                granted += b"\x00"
                            subs.extend(new)
                            self.send(0x90, pid + granted)
                            for sub in new:
                                for t, v in list(broker.retained.items()):
                                    if matches(sub, t):
                                        self.deliver(t, v, retain=True)
                        elif kind == 10:  # UNSUBSCRIBE
                            self.send(0xB0, body[:2])
                        elif kind == 12:  # PINGREQ
                            self.send(0xD0)
                        elif kind == 14:  # DISCONNECT
                            return
                except (ConnectionError, OSError, IndexError):
                    return
                finally:
                    with broker.lock:
                        broker.clients = [c for c in broker.clients if c[0] is not self]

        class Server(socketserver.ThreadingTCPServer):
            daemon_threads = True
            allow_reuse_address = True

            def handle_error(self, *a):
                pass
        self.server = Server(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return self.server.server_address[1]

    def publish(self, topic, text, retain=False, from_client=False):
        if from_client:
            self.published.append((topic, text, retain))
        if retain:
            self.retained[topic] = text
        with self.lock:
            targets = [h for h, subs in self.clients if any(matches(s, topic) for s in subs)]
        for h in targets:
            try:
                h.deliver(topic, text)
            except OSError:
                pass

    def wait_for_subscriber(self, topic, timeout=20):
        end = time.time() + timeout
        while time.time() < end:
            with self.lock:
                if any(any(matches(s, topic) for s in subs) for h, subs in self.clients):
                    return True
            time.sleep(0.1)
        return False


def start(retained=None):
    b = Broker()
    for t, v in (retained or {}).items():
        b.retained[t] = v
    return b, b.start()


if __name__ == "__main__":
    b, port = start()
    print("broker on", port)
    time.sleep(3600)
