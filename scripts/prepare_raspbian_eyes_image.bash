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
echo "Scripts path at ${scripts_path}"

# Change these
sdcard_mount="/mnt/beholderpi_sdcard"
user_name="pi"  # NB! Changing the user name here requires changes in the systemd unit files
root_password_clear="correct horse battery staple"
user_password_clear="supersecret"
root_password_crypt="$( python3 -c "import crypt; print(crypt.crypt('${root_password_clear}', crypt.mksalt(crypt.METHOD_SHA512)))" )"
user_password_crypt="$( python3 -c "import crypt; print(crypt.crypt('${user_password_clear}', crypt.mksalt(crypt.METHOD_SHA512)))" )"
image_url="https://downloads.raspberrypi.org/raspios_oldstable_lite_armhf_latest"
#github_repo="https://github.com/MemDynLab/BeholderPi.git"
overwrite_extracted_image=false

# Resolve redirect
image_url_resolved="$( curl --silent --location --head --output /dev/null --write-out '%{url_effective}' "${image_url}" )"
echo "OS image URL: ${image_url_resolved}"
image_name_resolved="$( basename -- "$image_url_resolved" )"
echo "OS image download file: ${image_name_resolved}"

# Get SHA1 for the lite image
# Lite is currently the third item on the download page
checksum="$(wget --quiet ${image_url}.sha1 -O -| awk '{print $1}')"

# Availability of SSH key files (private and public)
if [[ "$1" != "" ]]
then
    private_key_file=$1
else
    private_key_file="id_ed25519.pub"
fi

if [[ ! -e "${private_key_file}" ]]
then
    echo "Can't find the common private key file \"${private_key_file}\""
    echo "You can create a key pair using:"
    echo "   ssh-keygen -t ed25519 -f ./id_beholderpi -C \"BeholderPi keys\""
    exit 1
fi

public_key_file="${private_key_file}.pub"

if [[ ! -e "${public_key_file}" ]]
then
    echo "Can't find the matching public key file \"${public_key_file}\" to \"${private_key_file}\""
    echo "You can create a key pair using:"
    echo "   ssh-keygen -t ed25519 -f ./id_beholderpi -C \"BeholderPi keys\""
    exit 1
fi

echo "Using key file pair \"${private_key_file}\" and \"${public_key_file}\""
echo ""

# Download the latest image, continue getting a partially-downloaded file (for shaky wifi)
wget --continue "${image_url_resolved}"

echo "Checking SHA1 of the downloaded image, expecting \"${checksum}\""

if [[ $( sha1sum "${image_name_resolved}" | grep -c "${checksum}" ) -eq "1" ]]
then
    echo "The checksums match"
else
    echo "The checksums do not match"
    exit 1
fi

## unzip
#extracted_image=$( 7z l raspbian_lite_image.zip | awk '/-raspbian-/ {print $NF}' )
#echo "The name of the image is \"${extracted_image}\""
#
## to overwrite, -aoa, to skip, -aos
#7z x raspbian_lite_image.zip -aos
#
#if [[ ! -e ${extracted_image} ]]
#then
#    echo "Can't find the image \"${extracted_image}\""
#    exit
#fi

# Decompress the downloaded image
if [[ ${image_name_resolved} == *.zip ]]
then
  echo "Unpacking zip file"
  extracted_image=$( python3 -m zipfile -l "${image_name_resolved}" | tail -n 1 | awk '{print $1}' )
  if [[ ! -e ${extracted_image} || $overwrite_extracted_image == true ]]
  then
    echo "Overwriting image ${extracted_image}"
    python3 -m zipfile -e "${image_name_resolved}" .
  fi

elif [[ ${image_name_resolved} == *.xz ]]
then
  echo "Unpacking xz file"
  xz --decompress -v --keep --force "${image_name_resolved}"
  extracted_image="${image_name_resolved%.*}"
else
  echo "Downloaded archive has unknown file format."
  exit 1
fi
# unzip without additional dependencies...
echo "Got image: \"${extracted_image}\""

if [[ ! -e ${extracted_image} ]]
then
    echo "Extraction of \"${extracted_image}\" failed."
    exit 1
fi

# Create temporary image mounting point
mkdir -p ${sdcard_mount}

echo ""
echo "Mounting the sdcard boot disk"
unit_size=$(fdisk --list --units  "${extracted_image}" | awk '/^Units/ {print $(NF-1)}')
start_boot=$( fdisk --list --units  "${extracted_image}" | awk '/W95 FAT32/ {print $2}' )
offset_boot=$((start_boot * unit_size))
mount -o loop,offset="${offset_boot}" "${extracted_image}" "${sdcard_mount}"
ls -al ${sdcard_mount}
if [[ ! -e "${sdcard_mount}/kernel.img" ]]
then
    echo "Can't find the mounted card\"${sdcard_mount}/kernel.img\""
    exit 1
fi

touch "${sdcard_mount}/ssh"
if [[ ! -e "${sdcard_mount}/ssh" ]]
then
    echo "Can't find the ssh file \"${sdcard_mount}/ssh\""
    exit 1
fi

# New User Configuration as default user "pi" no longer a thing
echo "${user_name}:${user_password_crypt}" > "${sdcard_mount}/userconf.txt"

umount "${sdcard_mount}"

echo ""
echo "Mounting the SD card root disk"
unit_size=$(fdisk --list --units  "${extracted_image}" | awk '/^Units/ {print $(NF-1)}')
start_boot=$( fdisk --list --units  "${extracted_image}" | awk '/Linux/ {print $2}' )
offset_boot=$((start_boot * unit_size))
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
sed -e "s#^root:[^:]\+:#root:${root_password_crypt}:#" "${sdcard_mount}/etc/shadow" -i "${sdcard_mount}/etc/shadow"

# sed -e  "s#^${user_name}:[^:]\+:#${user_name}:${user_password_crypt}:#" -i "${sdcard_mount}/etc/shadow" # <- we did that with the new userconfig.txt file instead
sed -e 's;^#PasswordAuthentication.*$;PasswordAuthentication no;g' -e 's;^PermitRootLogin .*$;PermitRootLogin no;g' -i "${sdcard_mount}/etc/ssh/sshd_config"
mkdir -p "${sdcard_mount}/home/${user_name}/.ssh"
chmod 0700 "${sdcard_mount}/home/${user_name}/.ssh"
chown 1000:1000 "${sdcard_mount}/home/${user_name}/.ssh"
cp -v ${private_key_file} "${sdcard_mount}/home/${user_name}/.ssh/"
cp -v ${public_key_file} "${sdcard_mount}/home/${user_name}/.ssh/"
cat ${public_key_file} >> "${sdcard_mount}/home/${user_name}/.ssh/authorized_keys"
chown -R 1000:1000 "${sdcard_mount}/home/${user_name}/.ssh"
chmod 0644 "${sdcard_mount}/home/${user_name}/.ssh/authorized_keys"
echo "Setting permission on ${sdcard_mount}/home/${user_name}/.ssh/$( basename -- "${private_key_file}" )"
chmod 0600 "${sdcard_mount}/home/${user_name}/.ssh/$( basename -- "${private_key_file}" )"
# TODO: Home directory ends up being owned by root - change now or later?

# Clone github repository
#src_dir="${sdcard_mount}/home/${user_name}/src"
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
echo ""
echo "Installing Discovery service"
sender_py="${scripts_path}/services/discovery/beholder_discovery_sender.py"
if [[ ! -e ${sender_py} ]]
then
    echo "Can't find the sender script \"${sender_py}\""
    exit
fi
cp -v "${sender_py}" "${sdcard_mount}/home/${user_name}/"

sender_service="${scripts_path}services/discovery/eye_discovery_sender.service"
if [[ ! -e ${sender_service} ]]
then
    echo "Can't find the sender service file \"${sender_service}\""
    exit
fi
cp -v "${sender_service}" "${sdcard_mount}/etc/systemd/system/beholder_discovery_sender.service"

sed -i "s/PIUSERNAME/${user_name}/g" "${sdcard_mount}/etc/systemd/system/beholder_discovery_sender.service"

# Unit files are enabled by symlinking the unit file to a target.wants directory
echo ""
echo "Creating symlink to enable discovery service unit file"
service_link_target="${sdcard_mount}/etc/systemd/system/multi-user.target.wants/beholder_discovery_sender.service"
echo ${service_link_target}

rm -f "${service_link_target}"
ln -sv "/etc/systemd/system/beholder_discovery_sender.service" "${sdcard_mount}/etc/systemd/system/multi-user.target.wants/beholder_discovery_sender.service"

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
