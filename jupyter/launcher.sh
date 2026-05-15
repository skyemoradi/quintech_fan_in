#!/bin/bash

VENVDIR="./venv"
REQFILE="./requirements.txt"
LIBDIR="./lib"

if [ ! -d "$LIBDIR" ] ; then
	echo WARNING: Missing csi_client library
	make setup
fi

if [ ! -d "$VENVDIR" ] ; then
	echo 'Please wait...creating virtual environment'
	python3 -m venv $VENVDIR
	. $VENVDIR/bin/activate
	pip install --upgrade --no-cache-dir -r $REQFILE
else
	. $VENVDIR/bin/activate
fi

echo ''
echo 'Starting up jupyter-lab...'

jupyter-lab test_harness.ipynb
