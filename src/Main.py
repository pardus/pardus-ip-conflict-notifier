"""Pardus IP conflict notifier.

Drop-in replacement for ipwatchd-gnotify. Same command line:

    pardus-ip-conflict-notifier [--debug] [--broadcast] --title T --message M

Call chain (nothing to configure, ipwatchd's defaults are used):

    ipwatchd (root)
      -> user_script /usr/sbin/ipwatchd-script "dev" "ip" "mac"
        -> /usr/sbin/ipwatchd-gnotify --broadcast ...   (symlink to /usr/bin/pardus-ip-conflict-notifier)
          -> notify-send, as each logged-in graphical user, on their session bus
"""

import argparse
import os

from Notifier import APP_NAME, Notifier


def read_version():
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "__version__")) as f:
            return f.read().strip()
    except OSError:
        return "0.0.0"


def parse_args():
    parser = argparse.ArgumentParser(
        prog=APP_NAME,
        description="IP conflict notification tool for ipwatchd",
    )
    parser.add_argument("-d", "--debug", action="store_true")
    parser.add_argument("-b", "--broadcast", action="store_true",
                        help="notify every local graphical session (root only)")
    parser.add_argument("-t", "--title", required=True)
    parser.add_argument("-m", "--message", required=True)
    parser.add_argument("-v", "--version", action="version", version=read_version())
    return parser.parse_args()


def main():
    args = parse_args()
    return Notifier(debug=args.debug).notify(args.title, args.message, args.broadcast)


if __name__ == "__main__":
    raise SystemExit(main())
