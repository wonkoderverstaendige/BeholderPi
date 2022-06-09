# Base OS
Prepare and flash the ansible-ready OS image (last tested with Raspberry OS Buster 04.2022) generated with the image
preparation script.

# Network

`ansible-playbook ansible/install_spectator.yml --private-key ~/.ssh/id_beholderpi --inventory ansible/inventory-local`

# OFFLINE/ INSTALLATION
NOTE: In the CDL, there's not internet for the Pi's as LAN is blocked and Wifi requires access via a captive portal.
This means we can't run ansible to install the packages required.

Network via USB tether, then manually run all the steps ansible would do for us!
- apt install all packages listed in the playbook
- pip3 install pyyaml (why again?)
- copy and rename the up network devices templates into `/etc/systemd/network/`
- disable dhcpcd `systemctl disable dhcpcd` and enable networkd and dnsmasq
- rename in `/etc/hostname` and `/etc/hosts`
- overwrite chrony and dnsmasq configs from templates to `/etc/dnsmasq.conf` and `/etc/chrony/chrony.conf`
- modify `dnsmasq.conf` with the required MAC adresses

## OPTIONAL - DEV
Set up wifi to use as bridge into the 10.0.0.* subnet to have access without direct wiring into it.

Configure the spectator to use static IP.

`sudo apt install rsync dnsmasq chrony tcpdump`

Create `10-eth0.netdev` and `11-eth0.network` files in `/etc/systemd/network/`

- dhcpcd still default enabled on Buster, needs to be disabled.

Get client MAC and Serial

MAC: `ethtool -P eth0 | cut -d ' ' -f 3`
Serial: `grep Serial /proc/cpuinfo | cut -d ' ' -f 2 | cut -c 8-16`

# Notes on WIFI
Using Wifi on the spectator allows to have it both a connection to the eye network and the surrounding LAN/internet,
but requires routing setup to not interfere with each other.

Using the `wpa_supplicant-wlan0.conf` from `ansible/templates/spectator` in `/etc/wpa_supplicant/`:

`sudo systemctl enable wpa_supplicant@wlan0
sudo systemctl start wpa_supplicant@wlan0`

Checking for configured status via `sudo networkctl status wlan0`.

The network config files in `ansible/templates/spectator` have Metric hints, check with `route -n` that 
`eth0` has higher metric than `wlan0`. The routing table could be configured more fine-grained to use `eth0`
only for traffic in the `10.0.0.*` direction.

# PXE/Network Boot
see `Installation_PXE_Boot.md`