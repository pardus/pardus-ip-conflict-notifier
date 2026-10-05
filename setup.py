#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from setuptools import setup
import os, subprocess


def create_mo_files():
    podir = "po"
    mo = []
    for po in os.listdir(podir):
        if po.endswith(".po"):
            os.makedirs(
                "{}/{}/LC_MESSAGES".format(podir, po.split(".po")[0]), exist_ok=True
            )
            mo_file = "{}/{}/LC_MESSAGES/{}".format(
                podir, po.split(".po")[0], "pardus-ip-conflict-notifier.mo"
            )
            msgfmt_cmd = "msgfmt {} -o {}".format(podir + "/" + po, mo_file)
            subprocess.call(msgfmt_cmd, shell=True)
            mo.append(
                (
                    "/usr/share/locale/" + po.split(".po")[0] + "/LC_MESSAGES",
                    ["po/" + po.split(".po")[0] + "/LC_MESSAGES/pardus-ip-conflict-notifier.mo"],
                )
            )
    return mo


changelog = "debian/changelog"
if os.path.exists(changelog):
    head = open(changelog).readline()
    try:
        version = head.split("(")[1].split(")")[0]
    except:
        print("debian/changelog format is wrong for get version")
        version = "0.0.0"
    f = open("src/__version__", "w")
    f.write(version)
    f.close()

data_files = [
    (
        "/usr/share/pardus/pardus-ip-conflict-notifier/src",
        [
            "src/notifier.py",
            "src/__version__",
        ],
    ),
    ("/etc/xdg/autostart",
        ["data/tr.org.pardus.ip-conflict-notifier-autostart.desktop"]
    ),
] + create_mo_files()


setup(
    name="pardus-ip-conflict-notifier",
    version=version,
    packages=[],
    py_modules=[],
    scripts=["pardus-ip-conflict-notifier"],
    data_files=data_files,
    author="Emel Öztürk",
    author_email="emel.ozturk@pardus.org.tr",
    description="Desktop notifier for IPv4 address conflicts",
    license="MIT",
    keywords="pardus-ip-conflict-notifier, ip, conflict",
    url="https://github.com/pardus/pardus-ip-conflict-notifier",
)
