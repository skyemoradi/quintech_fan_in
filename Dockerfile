FROM ubuntu:22.04 AS builder

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get -y upgrade && apt-get install -y \
        git make curl httpie \
        redis redis-tools\
        python3-dev python3-pip python3-venv \
        libperl-dev libsnmp-dev snmp-mibs-downloader \
    && apt-get autoremove -y \
    && apt-get clean

# Remove SNMPv2-PDU file which officially has syntax error.  For details, see:
# https://serverfault.com/questions/936119/snmp-mibs-on-ubuntu-error-in-mibs
RUN rm -f /usr/share/snmp/mibs/ietf/SNMPv2-PDU

# poetry uses VIRTUAL_ENV if defined
# update path to use python from the virtual environment.
RUN python3 -m venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
WORKDIR /usr/local/src

# setup for container development in vscode.
# poetry installs a package stub that points back
# to your source code directory. the compose file
# in the .devcontainer folder overrides the
# default compose file for container development,
# using this stage as the build target.
#
# NOTE: always remove/rebuild the container when
# switching between development & deployment builds
FROM builder AS development

RUN curl -ksSL https://install.python-poetry.org | POETRY_HOME=/opt/poetry python3 -
ENV PATH="/opt/poetry/bin:$PATH"
RUN poetry completions bash >> ~/.bash_completion
COPY pyproject.toml .
# RUN poetry build
# RUN poetry install

COPY ./mibs /usr/share/snmp/mibs
COPY . .

# NOTE: not updating the dependencies here, just
# using what's in the poetry lock file. Run the
# build task in the vscode container to update
# the 
RUN poetry add /usr/local/src/csi_properties-*.whl
RUN poetry build
RUN poetry install

# just use the venv & package for deployment
# copy the venv and package fron development
# uninstall the package stub poetry installed
# install the actual package
#
# NOTE: always remove/rebuild the container when
# switching between development & deployment builds
# FROM builder as deployment
# COPY --from=development /usr/local/src/csi_properties.yml .
# COPY --from=development /usr/local/src/csi_properties-0.5.2-py3-none-any.whl .

# COPY --from=development /opt/venv /opt/venv
# COPY --from=development /usr/local/src/dist/apc_ap7900*.whl .
# COPY --from=development /usr/lib/x86_64-linux-gnu/libnetsnmp.so.40 /usr/lib/x86_64-linux-gnu/libnetsnmp.so.40
# COPY --from=development /usr/share/snmp/mibs /usr/share/snmp/mibs
# RUN pip3 uninstall -y apc_ap7900
# RUN pip3 install apc_ap7900*.whl
# RUN pip3 install csi_properties-0.5.2-py3-none-any.whl

