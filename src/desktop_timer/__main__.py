import argparse

from .app import main


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start the desktop timer.")
    return parser.parse_args()


if __name__ == "__main__":
    parse_args()
    main()
