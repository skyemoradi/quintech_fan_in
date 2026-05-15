# (c) 2023 The MITRE Corporation, All Rights Reserved
## 
# Makefile

# Include variables from .env file
include .env

DIRNAME := $(shell basename $(shell pwd))
DATE := $(shell date +%Y%m%d)
TARDIR := dist/${PROXY_NAME}-${VERSION}-${DATE}
TARBALL := ${TARDIR}/deployment/tarballs/${PROXY_NAME}.tgz

help:
	echo "SVC_NAME is ${SVC_NAME}"
	echo "Common commands are 'make all | build | up | update_dist_dir'"
	echo "See doc 010_Tutorials/CSI-010-008_CSI_Container_Local_Deployment.ipynb for details on usage"

all: build up

up:
	docker-compose up

build: clean checklibs
	docker-compose build

dcrun:
	docker container run -e PYTHONPATH=/usr/local/src/src/${PROXY_NAME} --network host --rm -it ${SVC_NAME} /bin/bash

checklibs: buildlibs
	cp src/commonlib/csi_properties/dist/*whl .

buildlibs:
	cd src/commonlib/csi_properties && make clean build


# building a dist

clean: 
	rm -rf venv client/venv lib dist dash/venv jupyter/venv csi_properties-*.whl

dist: clean build mkdistdir tarball save_image build_release_tarfile

update_dist_dir: build mkdistdir tarball save_image

mkdistdir:
	@echo Creating ${TARDIR}
	mkdir -p ${TARDIR} ${TARDIR}/deployment/images ${TARDIR}/deployment/tarballs
	cp -r deployment .env ${TARDIR}
	cp deployment/csi_deploy.sh ${TARDIR}/deployment
	cp README.dist ${TARDIR}/README.md

tarball: mkdistdir
	tar -C .. --exclude-vcs --exclude dist -czvf ${TARBALL} ${DIRNAME}

save_image: mkdistdir build
	docker save ${SVC_NAME} -o ${TARDIR}/deployment/images/${SVC_NAME}.img

build_release_tarfile:
	cd dist ; tar czvf ${PROXY_NAME}-${VERSION}-${DATE}.tgz ./${PROXY_NAME}-${VERSION}-${DATE}
