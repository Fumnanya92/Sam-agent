"""Allow `python -m sam_v2` to run the Sam v2 entrypoint."""

from .main import main


if __name__ == "__main__":
    raise SystemExit(main())
