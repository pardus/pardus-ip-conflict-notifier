"""Desktop notification for ipwatchd IP conflicts.

Called through /usr/sbin/ipwatchd-gnotify (see Main.py for the call chain).

Differences from ipwatchd-gnotify (by design):
  - sessions come from logind, not from scanning /proc/*/environ
  - privileges are dropped per child with setpriv, not seteuid() + system()
  - no shell is involved, so title/message are never shell-expanded
  - ipwatchd's English message is shown localized when its format is known
"""

import locale
import os
import pwd
import re
import subprocess
import sys

APP_NAME = "pardus-ip-conflict-notifier"

NOTIFY_SEND = "/usr/bin/notify-send"
LOGINCTL = "/usr/bin/loginctl"
SETPRIV = "/usr/bin/setpriv"
CHILD_TIMEOUT = 3

# Message format of /usr/sbin/ipwatchd-script.
IPWATCHD_MESSAGE_RE = re.compile(
    r"MAC address (?P<mac>\S+) causes IP conflict with address "
    r"(?P<ip>\S+) set on interface (?P<iface>\S+)"
)

GRAPHICAL_TYPES = ("x11", "wayland")

try:
    locale.setlocale(locale.LC_ALL, "")
except locale.Error:
    pass

# Development: ../po (after msgfmt), Production: /usr/share/locale
localedir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../po")
if not os.path.isdir(os.path.join(localedir, "tr", "LC_MESSAGES")):
    localedir = "/usr/share/locale"

locale.bindtextdomain(APP_NAME, localedir)
locale.textdomain(APP_NAME)
_ = locale.gettext


def normalize_mac(value):
    """ipwatchd prints octets without zero padding (8:0:27:...)."""

    parts = value.split(":")
    if len(parts) == 6 and all(re.fullmatch(r"[0-9A-Fa-f]{1,2}", p) for p in parts):
        return ":".join(f"{int(p, 16):02x}" for p in parts)
    return value


def build_notification(title, message):
    """Localize ipwatchd's known message; otherwise show it as given."""

    match = IPWATCHD_MESSAGE_RE.search(message)
    if match is None:
        return title, message

    body = _("IP address {} is being used by another device on the network.").format(
        match.group("ip")
    )
    body += "\n" + _("Interface: {}").format(match.group("iface"))
    body += "\n" + _("Hardware address of the conflicting device: {}").format(
        normalize_mac(match.group("mac"))
    )

    return _("IP Address Conflict"), body


class Notifier:
    def __init__(self, debug=False):
        self.debug_enabled = debug

    def debug(self, message):
        if self.debug_enabled:
            print(message, flush=True)

    @staticmethod
    def error(message):
        print(f"Error: {message}", file=sys.stderr, flush=True)

    @staticmethod
    def notify_command(title, body):
        return [
            NOTIFY_SEND,
            "--urgency=critical",
            "--icon=dialog-warning",
            "--app-name=Pardus",
            title,
            body,
        ]

    def run(self, command, env=None):
        self.debug(f"    run: {command}")
        try:
            result = subprocess.run(
                command,
                env=env,
                stdin=subprocess.DEVNULL,
                check=False,
                timeout=CHILD_TIMEOUT,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            self.error(f"unable to run {command[0]}: {exc}")
            return False

        if result.returncode != 0:
            self.error(f"{command[0]} exited with {result.returncode}")
            return False

        return True

    @staticmethod
    def session_property(session_id, name):
        result = subprocess.run(
            [LOGINCTL, "show-session", session_id, "--property", name, "--value"],
            capture_output=True,
            text=True,
            check=False,
            timeout=CHILD_TIMEOUT,
        )
        return result.stdout.strip()

    def graphical_session_uids(self):
        """UIDs that own a local X11/Wayland session (one session bus per UID)."""

        result = subprocess.run(
            [LOGINCTL, "list-sessions", "--no-legend"],
            capture_output=True,
            text=True,
            check=False,
            timeout=CHILD_TIMEOUT,
        )

        uids = set()

        for line in result.stdout.splitlines():
            fields = line.split()
            if not fields:
                continue

            session_id = fields[0]
            session_type = self.session_property(session_id, "Type")
            remote = self.session_property(session_id, "Remote")
            uid = self.session_property(session_id, "User")

            self.debug(f"  session {session_id}: type={session_type} remote={remote} uid={uid}")

            if session_type in GRAPHICAL_TYPES and remote == "no" and uid.isdigit():
                uids.add(int(uid))

        return sorted(uids)

    def notify_user(self, uid, title, body):
        try:
            user = pwd.getpwuid(uid)
        except KeyError:
            self.error(f"unknown uid {uid}")
            return False

        bus_path = f"/run/user/{uid}/bus"
        if not os.path.exists(bus_path):
            self.error(f"no session bus for {user.pw_name} ({bus_path})")
            return False

        env = {
            "PATH": "/usr/bin:/bin",
            "HOME": user.pw_dir,
            "USER": user.pw_name,
            "LOGNAME": user.pw_name,
            "DBUS_SESSION_BUS_ADDRESS": f"unix:path={bus_path}",
        }

        command = [
            SETPRIV,
            f"--reuid={uid}",
            f"--regid={user.pw_gid}",
            "--init-groups",
            "--no-new-privs",
            "--",
        ] + self.notify_command(title, body)

        self.debug(f"  notifying {user.pw_name} (uid {uid})")
        return self.run(command, env=env)

    def broadcast(self, title, body):
        if os.geteuid() != 0:
            self.error("You must be root to broadcast a message")
            return 1

        uids = self.graphical_session_uids()
        sent = sum(1 for uid in uids if self.notify_user(uid, title, body))

        self.debug(f"Notification sent to {sent} of {len(uids)} users")
        return 0 if sent == len(uids) else 1

    def notify(self, title, message, broadcast=False):
        title, body = build_notification(title, message)

        if broadcast:
            return self.broadcast(title, body)

        return 0 if self.run(self.notify_command(title, body)) else 1
