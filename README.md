<<<<<<< HEAD
# csi_quintech_RF_Matrix
=======
Quintech RF Matrix Proxy README file

Current status (02/2026)

Added snmpv3 support, added https support to jupyter-notebook, added field level user-authorization

Prerequisites

Need to have a copy of commonlib (submodule under src).

    $ git clone --recurse-submodules [link to repository]

If this repository has already been cloned, the submodule can be added by:

    $ cd [repository]
    $ git submodule update --init --recursive

Building

    $ make build

Running 

    $ make up

Debugging

    $ make bash

Creating a distribution

    $ make dist

Please reference the tutorial for more available make commands.

C2 / Testing

Use the jupyter-lab notebook in the jupyter directory to test the proxy

    $ cd jupyter
    $ ./launcher.sh
>>>>>>> b078ac2 (test upload)
