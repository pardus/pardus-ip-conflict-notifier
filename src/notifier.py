#!/usr/bin/env python3
"""Pardus IP conflict desktop notifier.

Sources (read from journald):
  - ipwatchd       : runtime IPv4 conflict
  - NetworkManager : activation-time IPv4 ACD conflict

Policy:
  conflict matched -> notify
  invalid IP       -> drop
  valid MAC        -> show it
  bad/missing MAC  -> notify anyway, without MAC
"""

import ipaddress
import locale
import os
import re
import subprocess
import time

from systemd import journal

# Development: ../locale, Production: /usr/share/locale
localedir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../locale')
if not os.path.exists(localedir):
    localedir = '/usr/share/locale'

# No GTK here to call setlocale() implicitly; gettext needs it.
try:
    locale.setlocale(locale.LC_ALL, '')
except locale.Error:
    pass

locale.bindtextdomain('pardus-ip-conflict-notifier', localedir)
locale.textdomain('pardus-ip-conflict-notifier')
_ = locale.gettext


DEBOUNCE_SECONDS = 60
NOTIFY_TIMEOUT = 3

IP_RE = r"(?:\d{1,3}\.){3}\d{1,3}"

NM_CONFLICT_RE = re.compile(
    rf"device \((?P<iface>[^)]+)\).*?"
    rf"IP address (?P<ip>{IP_RE}) cannot be configured because "
    rf"it is already in use in the network by host (?P<mac>\S+)"
)

IPWATCHD_CONFLICT_RE = re.compile(
    rf"MAC address (?P<mac>\S+) causes IP conflict with address "
    rf"(?P<ip>{IP_RE}) set on interface (?P<iface>\S+)"
)


class Debouncer:
    """Suppress repeats of a conflict that was actually shown to the user."""

    def __init__(self, seconds):
        self.seconds = seconds
        self.last = {}

    @staticmethod
    def _key(iface, ip, mac):
        return (iface, ip, mac or "")

    def is_suppressed(self, iface, ip, mac):
        previous = self.last.get(self._key(iface, ip, mac))

        if previous is None:
            return False

        return time.monotonic() - previous < self.seconds

    def mark(self, iface, ip, mac):
        now = time.monotonic()
        self.last[self._key(iface, ip, mac)] = now

        # Prevent unbounded growth.
        cutoff = now - (self.seconds * 2)
        self.last = {
            k: ts
            for k, ts in self.last.items()
            if ts >= cutoff
        }


def normalize_mac(value):
    """Normalize MAC, accepting ipwatchd's non-zero-padded octets."""

    value = value.rstrip(".,;")
    parts = value.split(":")

    if len(parts) != 6:
        return None

    if not all(
        re.fullmatch(r"[0-9A-Fa-f]{1,2}", part)
        for part in parts
    ):
        return None

    return ":".join(
        f"{int(part, 16):02x}"
        for part in parts
    )


def valid_ipv4(value):
    try:
        return str(ipaddress.IPv4Address(value))
    except ipaddress.AddressValueError:
        return None


def check_journal_access():
    """Fail if this user cannot read any system journal entries.

    sd_journal_open() silently skips unreadable files, so probe for real.
    Requires membership in 'systemd-journal' or 'adm' group.
    """

    probe = journal.Reader(flags=journal.SYSTEM)
    probe.seek_head()

    if probe.get_next():
        return

    raise RuntimeError(
        "System journal is not readable. "
        "The notifier cannot monitor NetworkManager/ipwatchd events."
    )


def open_reader():
    # Only system units are watched; user journals are irrelevant.
    reader = journal.Reader(flags=journal.SYSTEM)

    # Trusted journald fields. Users cannot forge _SYSTEMD_UNIT.
    reader.add_match("_SYSTEMD_UNIT=NetworkManager.service")
    reader.add_disjunction()
    reader.add_match("_SYSTEMD_UNIT=ipwatchd.service")

    # Ignore conflicts that happened before notifier startup.
    # get_previous() is required: seek_tail() alone never yields new entries.
    reader.seek_tail()
    reader.get_previous()

    return reader


def parse_entry(entry):
    message = entry.get("MESSAGE")

    if not isinstance(message, str):
        return None

    unit = entry.get("_SYSTEMD_UNIT")

    if unit == "NetworkManager.service":
        source = "NetworkManager"
        match = NM_CONFLICT_RE.search(message)

    elif unit == "ipwatchd.service":
        source = "ipwatchd"
        match = IPWATCHD_CONFLICT_RE.search(message)

    else:
        return None

    if match is None:
        return None

    ip = valid_ipv4(match.group("ip"))

    if ip is None:
        return None

    # MAC is additional information only.
    # Never suppress a valid conflict because MAC parsing failed.
    mac = normalize_mac(match.group("mac"))

    iface = match.group("iface")

    return source, iface, ip, mac


def notify(iface, ip, mac):
    """Show the desktop notification. Returns True only on confirmed success."""

    body = _("IP address {} is being used by another device on the network.").format(ip)
    body += "\n" + _("Interface: {}").format(iface)

    if mac:
        body += "\n" + _("Hardware address of the conflicting device: {}").format(mac)

    try:
        result = subprocess.run(
            [
                "/usr/bin/notify-send",
                "-u", "critical",
                "-i", "dialog-warning",
                "-a", "Pardus",
                _("IP Address Conflict"),
                body,
            ],
            check=False,
            timeout=NOTIFY_TIMEOUT,
        )

        if result.returncode != 0:
            print(
                f"notify-send failed: exit={result.returncode}",
                flush=True,
            )
            return False

        return True

    except subprocess.TimeoutExpired:
        print(
            "notify-send timed out",
            flush=True,
        )
        return False

    except OSError as error:
        print(
            f"notify-send failed: {error}",
            flush=True,
        )
        return False


def main():
    try:
        check_journal_access()
    except RuntimeError as error:
        print(f"pardus-ip-conflict-notifier: {error}", flush=True)
        return 1

    reader = open_reader()
    debouncer = Debouncer(DEBOUNCE_SECONDS)

    print(
        "Pardus IP conflict notifier listening...",
        flush=True,
    )

    while True:
        result = reader.wait()

        if result == journal.NOP:
            continue

        for entry in reader:
            conflict = parse_entry(entry)

            if conflict is None:
                continue

            source, iface, ip, mac = conflict

            if debouncer.is_suppressed(iface, ip, mac):
                print(
                    f"[{source}] debounced "
                    f"iface={iface} "
                    f"ip={ip} "
                    f"mac={mac}",
                    flush=True,
                )
                continue

            print(
                f"[{source}] conflict "
                f"iface={iface} "
                f"ip={ip} "
                f"mac={mac}",
                flush=True,
            )

            if notify(iface, ip, mac):
                debouncer.mark(iface, ip, mac)


if __name__ == "__main__":
    try:
        raise SystemExit(main() or 0)
    except KeyboardInterrupt:
        print(
            "\nNotifier stopped.",
            flush=True,
        )
