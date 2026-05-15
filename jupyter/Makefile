
# Set up environment
COMMONLIB_DIR := .
CSI_CLIENTLIB_DIR := ${COMMONLIB_DIR}/csi_client

setup: build_csi_client_lib

build_csi_client_lib:
	cd ${CSI_CLIENTLIB_DIR} ; make clean build
	mkdir -p lib ; cp ${CSI_CLIENTLIB_DIR}/dist/*whl lib/
