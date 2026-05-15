#!/bin/bash

# CSI Deployment Script
# (c) 2023 The MITRE Corporation, All Rights Reserved

export ENVFILE_CONTENTS=`cat ../.env`
export `echo $ENVFILE_CONTENTS | grep SVC_NAME`
export `echo $ENVFILE_CONTENTS | grep IMG_NAME`

export CSI_SERVICE_DIR=$SVC_NAME
export CSI_SERVICE_NAME="$CSI_SERVICE_DIR"
export CSI_IMAGE_NAME="$IMG_NAME"

export CSI_IMAGE_FILENAME=`ls -1 images | head -n 1`
export CSI_TARBALL_NAME=`ls -1 tarballs | head -n 1`

function display_help() {
    echo ''
    echo "Usage"
    echo ''
    echo "  $0 { ping | install | status | sanitize }"
    echo ''
    echo 'where:'
    echo '      ping runs a ping test to machines listed in the hosts file'
    echo "      install deploys CSI service $CSI_SERVICE_DIR"
    echo '      status displays the current status of the installation'
    echo "      sanitize removes service $CSI_SERVICE_DIR and related image"
    echo ''
}

if [[ "$1" == "" ]] ; then
    display_help
    exit 0
fi

if [[ "`which ansible`" = "" ]] ; then
	echo 'Could not find ansible on this machine'
	echo ''
	echo "Please install with 'sudo apt install ansible'"
	echo ''
	echo 'and then rerun this installation script'
	echo ''
	exit -1
fi

#
export ANSIBLE_CONFIG=.ansible_output_format.cfg
echo "CSI Deployment"
echo ""

HOSTSFILE=./hosts

if [[ "$1" == "ping" ]] ; then
    echo Running ansible ping...
    ansible -i $HOSTSFILE -m ping all

elif [[ "$1" == "install" ]] ; then
    echo "Ready to install the following components for CSI service $CSI_SERVICE_NAME:"
    echo ''
    echo "  Image: $CSI_IMAGE_FILENAME"
    echo "Service: $CSI_TARBALL_NAME"
    echo ''
    echo 'Press Y to proceed:'
	read -n1 ANSWER
    if [[ "$ANSWER" == "Y" || "$ANSWER" == "y" ]] ; then
        echo ''
        # echo "Installing image from $CSI_IMAGE_FILENAME"
        ansible-playbook -i $HOSTSFILE playbooks/install_image.yml -e "csi_image=$CSI_IMAGE_FILENAME"
        # echo "Installing service from $CSI_TARBALL_NAME"
        ansible-playbook -i $HOSTSFILE playbooks/install_service.yml -e "csi_tarball=$CSI_TARBALL_NAME csi_service_dir=$CSI_SERVICE_DIR"
    else
        echo Skipping installation per user request
    fi

elif [[ "$1" == "status" ]] ; then
    echo 'Getting current status of endpoint(s)'
    ansible-playbook -i $HOSTSFILE playbooks/status.yml

elif [[ "$1" == "sanitize" ]] ; then
    echo 'Ready to remove service and related image - press Y to proceed:'
	read -n1 ANSWER
    if [[ "$ANSWER" == "Y" || "$ANSWER" == "y" ]] ; then
        echo '' ; echo 'Sanitizing service and related image, please wait...' ; echo ''
        ansible-playbook -i $HOSTSFILE playbooks/sanitize_service.yml -e "csi_service_name=$CSI_SERVICE_NAME csi_image_name=$CSI_IMAGE_NAME"
    else
        echo Skipping sanitization per user request
    fi
else
    display_help

fi

###
