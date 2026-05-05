import sys

from cli.main import app


if __name__ == "__main__":
    app(sys.argv[1:] or ["standalone"])
