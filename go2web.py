#!/usr/bin/env python3

import argparse
import re
import socket
import ssl
from html import unescape
from urllib.parse import parse_qs, quote_plus, urljoin, urlparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="go2web",
        description="Simple CLI HTTP client over TCP sockets",
    )
    parser.add_argument(
        "-u",
        "--url",
        help="Make an HTTP request to the specified URL",
    )
    parser.add_argument(
        "-s",
        "--search",
        nargs="+",
        help="Search the term and print top results",
    )
    return parser


def parse_url(url: str) -> tuple[str, str, int, str]:
    parsed = urlparse(url)

    scheme = parsed.scheme or "http"
    host = parsed.hostname
    if not host:
        raise ValueError("Invalid URL")

    port = parsed.port or (443 if scheme == "https" else 80)

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


def split_headers_and_body(response: str) -> tuple[str, str]:
    parts = response.split("\r\n\r\n", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return "", response


def get_status_code(headers: str) -> int:
    first_line = headers.splitlines()[0] if headers else ""
    parts = first_line.split()
    if len(parts) >= 2 and parts[1].isdigit():
        return int(parts[1])
    return 0


def get_header_value(headers: str, header_name: str) -> str | None:
    for line in headers.splitlines():
        if ":" in line:
            name, value = line.split(":", 1)
            if name.strip().lower() == header_name.lower():
                return value.strip()
    return None


def decode_chunked_body(body: str) -> str:
    decoded = ""
    rest = body

    while rest:
        line_end = rest.find("\r\n")
        if line_end == -1:
            break

        chunk_size_line = rest[:line_end].strip()
        rest = rest[line_end + 2:]

        try:
            chunk_size = int(chunk_size_line, 16)
        except ValueError:
            break

        if chunk_size == 0:
            break

        decoded += rest[:chunk_size]
        rest = rest[chunk_size + 2:]

    return decoded


def html_to_text(html: str) -> str:
    html = re.sub(r"(?is)<script.*?>.*?</script>", "", html)
    html = re.sub(r"(?is)<style.*?>.*?</style>", "", html)
    html = re.sub(r"(?i)<br\s*/?>", "\n", html)
    html = re.sub(r"(?i)</p>", "\n", html)
    html = re.sub(r"(?i)</div>", "\n", html)
    html = re.sub(r"<[^>]+>", "", html)
    html = unescape(html)
    html = re.sub(r"\r", "", html)
    html = re.sub(r"\n\s*\n+", "\n\n", html)
    return html.strip()


def fetch_url_text(url: str, max_redirects: int = 5) -> str:
    current_url = url

    for _ in range(max_redirects):
        response = make_http_request(current_url)
        headers, body = split_headers_and_body(response)
        status_code = get_status_code(headers)

        if status_code in (301, 302, 303, 307, 308):
            location = get_header_value(headers, "Location")
            if not location:
                return "Invalid redirect response."
            current_url = urljoin(current_url, location)
            continue

        transfer_encoding = get_header_value(headers, "Transfer-Encoding")
        if transfer_encoding and "chunked" in transfer_encoding.lower():
            body = decode_chunked_body(body)

        return html_to_text(body)

    return "Too many redirects."


def build_search_url(search_terms: list[str]) -> str:
    query = quote_plus(" ".join(search_terms))
    return f"https://html.duckduckgo.com/html/?q={query}"

def normalize_search_result_url(url: str) -> str:
    if url.startswith("//"):
        url = f"https:{url}"

    parsed = urlparse(url)

    if "duckduckgo.com" in parsed.netloc and parsed.path == "/l/":
        params = parse_qs(parsed.query)
        real_urls = params.get("uddg")
        if real_urls:
            return unescape(real_urls[0])

    return url


def extract_search_results(html: str, max_results: int = 10) -> list[tuple[str, str]]:
    results: list[tuple[str, str]] = []

    pattern = re.compile(
        r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="(.*?)"[^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )

    for match in pattern.finditer(html):
        url = normalize_search_result_url(unescape(match.group(1)).strip())
        title_html = match.group(2).strip()
        title = html_to_text(title_html)

        if title and url:
            results.append((title, url))

        if len(results) == max_results:
            break

    return results


def search_web(search_terms: list[str]) -> list[tuple[str, str]]:
    search_url = build_search_url(search_terms)
    response = make_http_request(search_url)
    headers, body = split_headers_and_body(response)

    transfer_encoding = get_header_value(headers, "Transfer-Encoding")
    if transfer_encoding and "chunked" in transfer_encoding.lower():
        body = decode_chunked_body(body)

    return extract_search_results(body)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.url:
        try:
            print(fetch_url_text(args.url))
        except Exception as error:
            print(f"Error: {error}")
        return

    if args.search:
        try:
            results = search_web(args.search)

            if not results:
                print("No results found.")
                return

            for index, (title, url) in enumerate(results, start=1):
                print(f"{index}. {title}")
                print(f"   {url}")
        except Exception as error:
            print(f"Error: {error}")
        return

    parser.print_help()


if __name__ == "__main__":
    main()