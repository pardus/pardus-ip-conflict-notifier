#!/bin/bash

langs=("tr")

if ! command -v xgettext &> /dev/null
then
	echo "xgettext could not be found."
	echo "you can install the package with 'apt install gettext' command on debian."
	exit
fi


echo "updating pot file"
xgettext -o po/pardus-ip-conflict-notifier.pot --files-from=po/files

for lang in ${langs[@]}; do
	if [[ -f po/$lang.po ]]; then
		echo "updating $lang.po"
		msgmerge -o po/$lang.po po/$lang.po po/pardus-ip-conflict-notifier.pot
	else
		echo "creating $lang.po"
		cp po/pardus-ip-conflict-notifier.pot po/$lang.po
	fi

	# Generate .mo files for development
	echo "generating $lang.mo for development"
	mkdir -p locale/$lang/LC_MESSAGES
	msgfmt po/$lang.po -o locale/$lang/LC_MESSAGES/pardus-ip-conflict-notifier.mo
done
