"""CLI entry point for the OTJ Helper."""

import os

from otj_helper.app import create_app


def main():
    app = create_app()
    debug = os.environ.get("FLASK_DEBUG", "false").lower() in ("1", "true", "yes")
    app.run(debug=debug, port=5000)


if __name__ == "__main__":
    main()
