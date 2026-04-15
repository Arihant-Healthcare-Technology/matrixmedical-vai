"""Allow running as `python -m src`."""
import sys
from src.presentation.cli.main import main

if __name__ == "__main__":
    sys.exit(main())
