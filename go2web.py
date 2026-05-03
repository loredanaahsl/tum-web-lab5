#!/usr/bin/env python3

import argparse
import socket
import ssl
from urllib.parse import urlparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="go2web",
        description="Simple CLI HTTP client over TCP sockets"
    )
    parser.add_argument("-u", "--url", help="Make an HTTP request to the specified URL")
    parser.add_argument("-s", "--search", nargs="+", help="Search the term and print top results")
    return parser


def parse_url(url: str) -> tuple[str, str, int, str]:
    parsed = urlparse(url)

    scheme = parsed.scheme or "http"
    host = parsed.hostname
    if not host:
        raise ValueError("Invalid URL")

    if scheme == "https":
        port = parsed.port or 443
    else:
        port = parsed.port or 80

    path = parsed.path or "/"
    if parsed.query:
        path += f"?{parsed.query}"

    return scheme, host, port, path


def make_http_request(url: str) -> str:
    scheme, host, port, path = parse_url(url)

    request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        "User-Agent: go2web/1.0\r\n"
        "Connection: close\r\n\r\n"
    )

    raw_response = b""

    with socket.create_connection((host, port), timeout=10) as sock:
        if scheme == "https":
            context = ssl.create_default_context()
            with context.wrap_socket(sock, server_hostname=host) as secure_sock:
                secure_sock.sendall(request.encode("utf-8"))
                while True:
                    chunk = secure_sock.recv(4096)
                    if not chunk:
                        break
                    raw_response += chunk
        else:
            sock.sendall(request.encode("utf-8"))
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                raw_response += chunk

    return raw_response.decode("utf-8", errors="replace")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.url:
        response = make_http_request(args.url)
        print(response)
        return

    if args.search:
        print(f"Search mode: {' '.join(args.search)}")
        return

    parser.print_help()


if __name__ == "__main__":
    main()