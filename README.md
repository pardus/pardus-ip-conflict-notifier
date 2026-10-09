# Pardus IP Conflict Notifier

Shows a desktop notification when ipwatchd detects an IPv4 address conflict,
similar to the Windows "IP address conflict" warning.

Drop-in replacement for `ipwatchd-gnotify`: the package installs
`/usr/sbin/ipwatchd-gnotify` as a symlink to `/usr/bin/pardus-ip-conflict-notifier`,
which the stock `/usr/sbin/ipwatchd-script` already calls. No configuration
is changed and desktop users need no extra privileges.

```
ipwatchd (root)
  -> user_script /usr/sbin/ipwatchd-script "dev" "ip" "mac"
    -> /usr/sbin/ipwatchd-gnotify --broadcast --title ... --message ...
      -> notify-send as each local graphical user (logind + setpriv)
```

## Usage

```
pardus-ip-conflict-notifier [--debug] [--broadcast] --title TITLE --message MESSAGE
```

`--broadcast` notifies every local X11/Wayland session and requires root.

## Build

```
dpkg-buildpackage -us -uc -b
```

## Translations

```
./update-translations.sh   # updates po/*.pot and po/*.po from po/files
```

## Limitation

Only runtime conflicts seen by ipwatchd are reported. A conflict detected by
NetworkManager while activating a connection (the address is never configured)
is not visible to ipwatchd.
