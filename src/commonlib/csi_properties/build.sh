#!/bin/bash

poetry build
USER=$(stat -c '%u' .)
GROUP=$(stat -c '%g' .)
chown -R $USER dist
chgrp -R $GROUP dist
