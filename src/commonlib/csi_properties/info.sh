#!/bin/bash

echo -n "Python install: "
which python3
status=$?
if (( status == 0 ))
then
    echo "Python version: $(python3 --version)"
else
    echo "NOT FOUND"
fi

echo -n "Poetry install: "
which poetry
status=$?
if (( status == 0 ))
then
    echo "Poetry version: $(poetry --version)"
else
    echo "NOT FOUND"
fi

echo "Environment variables:"
env
ls -l