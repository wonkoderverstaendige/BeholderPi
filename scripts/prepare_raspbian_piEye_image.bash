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

# Change these
root_password_clear="correct horse battery staple"
pi_password_clear="wrong cart charger paperclip"
image_to_download="https://downloads.raspberrypi.org/raspbian_latest"
checksum="$(wget --quiet https://www.raspberrypi.org/downloads/raspbian/ -O - | egrep -m 1 'SHA-1' | awk -F '<|>' '{print $9}')"
sdcard_mount="/mnt/sdcard"
public_key_file="id_ed25519.pub"

if [ ! -e "${public_key_file}" ]
then
    echo "Can't find the public key file \"${public_key_file}\""
    echo "You can create one using:"
    echo "   ssh-keygen -t ed25519 -f ./id_ed25519 -C \"Raspberry Pi keys\""
    exit
fi

# Download the latest image, using the  --continue "Continue getting a partially-downloaded file"
wget --continue ${image_to_download} -O raspbian_image.zip

echo "Checking the SHA-1 of the downloaded image matches \"${checksum}\""

if [ $( sha1sum raspbian_image.zip | grep ${checksum} | wc -l ) -eq "1" ]
then
    echo "The checksums matche"
else
    echo "The checksums did not match"
    exit 1
fi

# Following the tutorial
mkdir ${sdcard_mount}

# unzip
extracted_image=$( 7z l raspbian_image.zip | awk '/-raspbian-/ {print $NF}' )
echo "The name of the image is \"${extracted_image}\""

7z x raspbian_image.zip

if [ ! -e ${extracted_image} ]
then
    echo "Can't find the image \"${extracted_image}\""
    exit
fi

echo "Mounting the sdcard boot disk"
unit_size=$(fdisk --list --units  "${extracted_image}" | awk '/^Units/ {print $(NF-1)}')
start_boot=$( fdisk --list --units  "${extracted_image}" | awk '/W95 FAT32/ {print $2}' )
offset_boot=$((${start_boot} * ${unit_size})) 
mount -o loop,offset="${offset_boot}" "${extracted_image}" "${sdcard_mount}"
ls -al /mnt/sdcard
if [ ! -e "${sdcard_mount}/kernel.img" ]
then
    echo "Can't find the mounted card\"${sdcard_mount}/kernel.img\""
    exit
fi

touch "${sdcard_mount}/ssh"
if [ ! -e "${sdcard_mount}/ssh" ]
then
    echo "Can't find the ssh file \"${sdcard_mount}/ssh\""
    exit
fi

umount "${sdcard_mount}"

echo "Mounting the sdcard root disk"
unit_size=$(fdisk --list --units  "${extracted_image}" | awk '/^Units/ {print $(NF-1)}')
start_boot=$( fdisk --list --units  "${extracted_image}" | awk '/Linux/ {print $2}' )
offset_boot=$((${start_boot} * ${unit_size})) 
mount -o loop,offset="${offset_boot}" "${extracted_image}" "${sdcard_mount}"
ls -al /mnt/sdcard

if [ ! -e "${sdcard_mount}/etc/shadow" ]
then
    echo "Can't find the mounted card\"${sdcard_mount}/etc/shadow\""
    exit
fi

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

umount "${sdcard_mount}"
new_name="${extracted_image%.*}-ssh-enabled.img"
cp -v "${extracted_image}" "${new_name}"

lsblk

echo ""
echo "Now you can burn the disk using something like:"
echo "      dd bs=4M status=progress if=${new_name} of=/dev/mmcblk????"
echo ""
