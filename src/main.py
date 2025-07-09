#!/usr/bin/env python3
"""Main entry point for Magic Tools application."""

import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

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
