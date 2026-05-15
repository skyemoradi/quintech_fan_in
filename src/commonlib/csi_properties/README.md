Welcome to the csi_client library

This version of the csi_client library uses Poetry in a docker container to
build the package. To build:

- make build: builds the python package, creates image/container if neeeded

- make clean: removes contents of dist directory and container

- make extraclean: also removes the image along with dist & container

To run in a vscode devcontainer:

- install the Dev Containers extension in vscode

- remove the existing container:

- $ docker-compose down

- open the csi_client workspace in vscode

- click the green box in the lower left-hand corner, and select
  "Reopen in Container"

- poetry & the virtual environment will already be activated

To exit the devcontainer:

- click the green box in the lower left-hand corner, and select
  "Reopen in Host" (or "Reopen in WSL" if using WSL)

