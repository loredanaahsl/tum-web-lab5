#!/usr/bin/env python3

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="go2web",
        description="Simple CLI HTTP client over TCP sockets"
    )
    parser.add_argument("-u", "--url", help="Make an HTTP request to the specified URL")
    parser.add_argument("-s", "--search", nargs="+", help="Search the term and print top results")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.url:
        print(f"URL mode: {args.url}")
        return

    if args.search:
        print(f"Search mode: {' '.join(args.search)}")
        return

    parser.print_help()


if __name__ == "__main__":
    main()