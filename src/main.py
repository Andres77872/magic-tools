#!/usr/bin/env python3
"""Main entry point for Magic Tools application."""

import sys
import os

# Ensure the src directory is on sys.path
src_dir = os.path.dirname(__file__)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from magic_tools.core import create_app


def main():
    """Main entry point for the application."""
    try:
        # Create and run the application
        app = create_app()
        return app.run()
    except Exception as e:
        print(f"Error starting Magic Tools: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
