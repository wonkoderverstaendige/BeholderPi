# SD card installation
To bootstrap network discovery and [Ansible](https://www.ansible.com/) access, the default RaspbianOS
image is modified with the bash script in `scripts/prepare_raspbian_eyestalk_image.bash`.
It copies files required for the initial services, enables ssh, copies ssh keys and sets default passwords.

Running the script will require `sudo`, as does flashing to SD card. When flashing with the official flasher,
make sure not to modify any of the configuration there as it may override changes made by us. 

# Ansible setup
From a linux machine with ansible installed, run the following from outside the `BeholderPi/ansible` directory
(ansible does not like running from the working directory containing the playbook).

`ansible-playbook ansible/install_eye.yml 
    --private-key ~/.ssh/id_beholderpi
    --inventory ansible/inventory-local
    --extra-vars "@ansible/vars_eyes-local.yml"
    --limit new_eyes`

# What the Script does
RaspberryIS Buster is distributed with SSH is disabled by default.
To enable, an (empty) `ssh` file needs to be present in the `/boot` partition

See this [blog post](https://kenfallon.com/safely-enabling-ssh-in-the-default-raspbian-image/)
for details.

Add beholderpi key to the known_known hosts of all devices, including
*spectator* and *beholder*

### Network
The *spectator* RaspberryPi acts as DNS and DCHP server for all hosts on the
10.0.0.* network. It serves with the `dnsmasq` package.

> TODO: Make a template of the *spectator* `dhcpcd.conf` and `dnsmasq.conf`.

- `apt install dnsmasq`

### Security
- copy ssh keys
- prevent/allow password authentication

### Network discovery

To facilitate host discovery by the master *beholder* instance
in an unknown network environment (external DHCP? static IPs?),
the nodes run a systemd service broadcasting __UDP on port 50101__ with
messages containing IP and hostname (`IP:hostname`, though IP is strictly
not needed and known from the socket connection).

The system running Ansible can then take over given
a list of ssh-enabled hosts and apply their roles (including adjusting
the hostnames).

#### Discovery Sender setup
This requires copying the `beholder_discovery_sender.py` files to the
home directory of the `pi` user, the `beholder_discovery_sender.service`
to `/etc/systemd/system` as well as enabling the systemd unit file to
launch on reboot by creating a symlink to it in
`/etc/systemd/multi-user.target.wants`. Upon reboot the script will
continuously broadcast at ~ 3s intervals.

The machine running Ansible now only has to listen on UDP port 50101
to discover client addresses to include as hosts.

#### Discovery Receiver setup

Just launch the `scripts/services/discovery/beholder_discovery_reciever.py`
script.

# Ansible Playbooks

The following tasks are required:

## Eyes

### Network configuration
- set up hostname and configuration (e.g. network)
> Launch the ansible/setup/network playbook

__For more detail see (Networking.md)[Networking.md]__

### Basic packages
- install packages (python3, ntp, camera, git, vim, htop, byobu)

### Telemetry
- install and configure telemetry (telegraf)

### BeholderPi code
- clone and install BeholderPi repository
- install service for camera feed
- update any service affected by new code (discovery, streaming)
