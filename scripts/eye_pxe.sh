#!/bin/bash

if ! [ $(id -u) = 0 ]; then
    echo "Run script with sudo!" >&2
    exit 1
fi

# TFT BOOT
new_eye=$1
cp -R /tftpboot/boot_template/ /tftpboot/10.0.0.1$new_eye

echo Setting up eye$new_eye
sed -i "s/eyeXX/eye$new_eye/g" /tftpboot/10.0.0.1$new_eye/cmdline.txt

# OS
rsync -ah --info=progress2 /nfs/eye_base/ /nfs/eye${new_eye}
sed -i "s/eyeXX/eye$new_eye/g" /nfs/eye$new_eye/etc/hostname
sed -i "s/eyeXX/eye$new_eye/g" /nfs/eye$new_eye/etc/hosts

sudo chown pi:pi /nfs/eye${new_eye}/home/pi
sudo chown -R root:root /nfs/eye${new_eye}/usr
sudo chmod 4577 /nfs/eye${new_eye}/usr/bin/sudo
sudo chown -R root:root /nfs/eye${new_eye}/etc

cd /nfs/eye${new_eye}
sudo mount --bind /dev dev
sudo mount --bind /sys sys
sudo mount --bind /proc proc
sudo chroot . rm /etc/ssh/ssh_host_*
sudo chroot . dpkg-reconfigure openssh-server
sudo chroot . systemctl enable ssh
sudo umount dev sys proc

grep -qF "eye${new_eye}" /etc/exports || sudo echo "/nfs/eye${new_eye} *(rw,sync,no_subtree_check,no_root_squash)" >> /etc/exports
sudo systemctl restart rpcbind
sudo systemctl restart nfs-kernel-server
