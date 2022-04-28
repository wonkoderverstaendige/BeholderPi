# Clients
## Pi 3
raise NotImplementedError

## Pi 4
Check current bootloader configuration (see [Pi4 Boot EEPROM docs](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#raspberry-pi-4-boot-eeprom)):

`sudo vcgencmd bootloader_config`

we want FREEZE_VERSION=1 and BOOT_ORDER=0x421 (L->R USB, NET, SD).

`sudo apt install rpi-eeprom`

`sudo -E rpi-eeprom-config --edit` to edit directly or

`sudo rpi-eeprom-config --apply pxe_boot.conf` to use a file

Finalize update with reboot.

# Server
## Mount points
`sudo mkdir -p /tftpboot`

`sudo chmod 777 /tftpboot`

The individual clients get their `/boot` from subdirectories in `/tftpboot`, either by MAC or IP as
configured in `dnsmasq.conf` under `tftp-unique-root`, e.g. `/tftpboot/10.0.0.103` containing the kernel, config
and `cmdline.txt` pointing to the NFS image.

One NFS mount point per client/eye

`sudo mkdir -p /nfs/eyeXX` 

for ease of access, we'll make the content in home and then move+chown to `root:root`

Copy either from a setup eye:

`sudo rsync -e "ssh -i /home/pi/.ssh/id_beholderpi" -xa --progress / pi@10.0.0.1:eye_base`

or copy from own root:

`sudo rsync -xa --progress --exclude /nfs --exclude /etc/systemd/network --exclude /etc/dnsmasq.conf  / /nfs/eye_base`

Permissions are important - `/usr/bin/sudo` must be owned by root and `chmod 4577` to work, home should be owned by `pi`


## Individual NFS roots
For each client create a NFS mount via copy from base image

`sudo rsync -xa /nfs/eye_base /nfs/eyeXX`

### Chrooting
`cd /nfs/eyeXX
sudo mount --bind /dev dev
sudo mount --bind /sys sys
sudo mount --bind /proc proc
sudo chroot . rm /etc/ssh/ssh_host_*
sudo chroot . dpkg-reconfigure openssh-server
sudo chroot . systemctl enable ssh
sudo umount dev sys proc`

## Disable dhcpcd
`sudo systemctl stop dhcpcd
sudo systemctl disable dhcpcd`

## dnsmasq config
On top of default dnsmasq config for spectator
`interface=eth0
no-hosts
enable-tftp
tftp-root=/tftpboot
pxe-service=0,"Raspberry Pi Boot"`

## tftp service
Copy the `/boot` off a configured eye (i.e. ssh, camera etc. enabled).

`sudo cp -r /boot/* /tftpboot`

or

`sudo rsync -e "ssh -i /home/pi/.ssh/id_beholderpi" -xa --progress /boot pi@10.0.0.1:`

and then some manual moving + chowning to `root:root`.

Edit kernel parameters in `/tftpboot/cmdline.txt`:

`console=serial0,115200 console=tty1 root=/dev/nfs 
nfsroot=10.0.0.1:/nfs/eye03,vers=3 rw ip=dhcp rootwait elevator=deadline`

## NFS
Add exports in `/etc/exports`:

`/nfs/eyeXX *(rw,sync,no_subtree_check,no_root_squash)
/tftpboot *(rw,sync,no_subtree_check,no_root_squash)`

edit `/nfs/eyeXX/etc/fstab`:

`proc       /proc        proc     defaults    0    0
10.0.0.1:/tftpboot /boot nfs defaults,vers=3 0 0`

Enable services

`sudo systemctl enable rpcbind
sudo systemctl restart rpcbind
sudo systemctl enable nfs-kernel-server
sudo systemctl restart nfs-kernel-server`





