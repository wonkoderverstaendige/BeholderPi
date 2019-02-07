#!/bin/bash
# MIT License 
# Copyright (c) 2017 Ken Fallon http://kenfallon.com
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# Check if super user, required for mounting
if [[ "$EUID" -ne 0 ]]
  then echo "Please run as root"
  exit
fi

# Script location
this_path="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
base_path="$( dirname "${this_path}" )"
scripts_path="${base_path}/scripts/"
echo "Base path at ${base_path}"
echo "scripts path at ${scripts_path}"

# Change these
root_password_clear="correct horse battery staple"
pi_password_clear="supersecret"
image_to_download="https://downloads.raspberrypi.org/raspbian_lite_latest"
github_repo="https://github.com/MemDynLab/BeholderPi.git"

# Get SHA-256 for the lite image
# Lite is currently the third item on the download page
checksum="$(wget --quiet https://www.raspberrypi.org/downloads/raspbian/ -O - | egrep -m 3 'SHA-256' | awk -F '<|>' '{i++}i==3{print $9}')"

sdcard_mount="/mnt/beholderpi_sdcard"
public_key_file="id_ed25519.pub"

if [[ ! -e "${public_key_file}" ]]
then
    echo "Can't find the public key file \"${public_key_file}\""
    echo "You can create one using:"
    echo "   ssh-keygen -t ed25519 -f ./id_ed25519 -C \"BeholderPi keys\""
    exit
fi

# Download the latest image, using the  --continue "Continue getting a partially-downloaded file"
wget --continue ${image_to_download} -O raspbian_lite_image.zip

echo "Checking the SHA-256 of the downloaded image matches \"${checksum}\""

if [[ $( sha256sum raspbian_lite_image.zip | grep ${checksum} | wc -l ) -eq "1" ]]
then
    echo "The checksums match"
else
    echo "The checksums do not match"
    exit 1
fi

# Following the tutorial
mkdir ${sdcard_mount}

# unzip
extracted_image=$( 7z l raspbian_lite_image.zip | awk '/-raspbian-/ {print $NF}' )
echo "The name of the image is \"${extracted_image}\""

# to overwrite, -aoa, to skip, -aos
7z x raspbian_lite_image.zip -aoa

if [[ ! -e ${extracted_image} ]]
then
    echo "Can't find the image \"${extracted_image}\""
    exit
fi

echo ""
echo "Mounting the sdcard boot disk"
unit_size=$(fdisk --list --units  "${extracted_image}" | awk '/^Units/ {print $(NF-1)}')
start_boot=$( fdisk --list --units  "${extracted_image}" | awk '/W95 FAT32/ {print $2}' )
offset_boot=$((${start_boot} * ${unit_size})) 
mount -o loop,offset="${offset_boot}" "${extracted_image}" "${sdcard_mount}"
ls -al ${sdcard_mount}
if [[ ! -e "${sdcard_mount}/kernel.img" ]]
then
    echo "Can't find the mounted card\"${sdcard_mount}/kernel.img\""
    exit
fi

touch "${sdcard_mount}/ssh"
if [[ ! -e "${sdcard_mount}/ssh" ]]
then
    echo "Can't find the ssh file \"${sdcard_mount}/ssh\""
    exit
fi

umount "${sdcard_mount}"

echo ""
echo "Mounting the SD card root disk"
unit_size=$(fdisk --list --units  "${extracted_image}" | awk '/^Units/ {print $(NF-1)}')
start_boot=$( fdisk --list --units  "${extracted_image}" | awk '/Linux/ {print $2}' )
offset_boot=$((${start_boot} * ${unit_size})) 
mount -o loop,offset="${offset_boot}" "${extracted_image}" "${sdcard_mount}"
ls -al ${sdcard_mount}

if [[ ! -e "${sdcard_mount}/etc/shadow" ]]
then
    echo "Can't find the mounted card\"${sdcard_mount}/etc/shadow\""
    exit
fi

# Security and Access
echo ""
echo "Change the passwords and sshd_config file"
root_password="$( python3 -c "import crypt; print(crypt.crypt('${root_password_clear}', crypt.mksalt(crypt.METHOD_SHA512)))" )"
pi_password="$( python3 -c "import crypt; print(crypt.crypt('${pi_password_clear}', crypt.mksalt(crypt.METHOD_SHA512)))" )"
sed -e "s#^root:[^:]\+:#root:${root_password}:#" "${sdcard_mount}/etc/shadow" -e  "s#^pi:[^:]\+:#pi:${pi_password}:#" -i "${sdcard_mount}/etc/shadow"
sed -e 's;^#PasswordAuthentication.*$;PasswordAuthentication no;g' -e 's;^PermitRootLogin .*$;PermitRootLogin no;g' -i "${sdcard_mount}/etc/ssh/sshd_config"
mkdir "${sdcard_mount}/home/pi/.ssh"
chmod 0700 "${sdcard_mount}/home/pi/.ssh"
chown 1000:1000 "${sdcard_mount}/home/pi/.ssh"
cat ${public_key_file} >> "${sdcard_mount}/home/pi/.ssh/authorized_keys"
chown 1000:1000 "${sdcard_mount}/home/pi/.ssh/authorized_keys"
chmod 0600 "${sdcard_mount}/home/pi/.ssh/authorized_keys"

# Clone github repository
#src_dir="${sdcard_mount}/home/pi/src"
#mkdir ${src_dir}
#
#if [[ ! -e ${src_dir} ]]
#then
#    echo "Can't create directory \"${src_dir}\""
#    exit
#fi
# Clone source directory to target
#git clone "${github_repo}" "${src_dir}/BeholderPi"

# Install discovery service
echo "Installing Discovery service"
sender_py="${scripts_path}/services/discovery/beholder_discovery_sender.py"
if [[ ! -e ${sender_py} ]]
then
    echo "Can't find the sender script \"${sender_py}\""
    exit
fi
cp -v ${sender_py} "${sdcard_mount}/home/pi/"

sender_service="${scripts_path}/services/discovery/beholder_discovery_sender.service"
if [[ ! -e ${sender_service} ]]
then
    echo "Can't find the sender service file \"${sender_service}\""
    exit
fi
cp -v ${sender_service} "${sdcard_mount}/etc/systemd/system/"

# Unit files are enabled by symlinking the unit file to a target.wants directory
echo "Creating symlink to enable discovery service unit file"
ln -s -v "/etc/systemd/system/beholder_discovery_sender.service" "${sdcard_mount}/etc/systemd/system/multi-user.target.wants/beholder_discovery_sender.service"

# Done modifying image
echo ""
echo "Preparation done, copying image"
umount "${sdcard_mount}"
new_name="${extracted_image%.*}-ansible-ready.img"
cp -v "${extracted_image}" "${new_name}"

echo ""
lsblk

echo ""
echo "Now you can burn the disk using something like:"
echo "      dd bs=4M status=progress if=${new_name} of=/dev/sdX??"
echo ""
