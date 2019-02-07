# SD card installation

## Create custom Raspbian image

To bootstrap network discovery and [Ansible](https://www.ansible.com/) access, a custom Raspbian
 image is generated with the bash script in `scripts/prepare_raspbian_piEye_image.bash`.
 It copies files required for the initial services, enables ssh,
  copies ssh keys and sets default passwords.

Running the script will require `sudo`, as does flashing to SD card.

### SSH
Raspbian Stretch is distributed with SSH is disabled by default.
To enable, an (empty) `ssh` file needs to be present in the `/boot` partition

See this [blog post](https://kenfallon.com/safely-enabling-ssh-in-the-default-raspbian-image/)
for details.

### Network discovery

To facilitate piEye node discovery by the master Beholder instance
in an unknown network environment (external DHCP? static IPs?),
the nodes run a systemd service broadcasting __UDP on port 50101__ with
messages containing IP and hostname (`IP:hostname`, though IP is strictly
not needed and known from the socket connection.
The system running ansible can then take over given
a list of ssh-enabled hosts and apply their roles (including adjusting
the hostnames).

This requires copying the `beholder_discovery_sender.py` files to the
home directory of the `pi` user, the `beholder_discovery_sender.service`
to `/etc/systemd/system` as well as enabling the systemd unit file to
launch on reboot by creating a symlink to it in
`/etc/systemd/multi-user.target.wants`. Upon reboot the script will
continuously broadcast at ~ 3s intervals.

The machine running Ansible now only has to listen on UDP port 50101
to discover client addresses to include as hosts.

## Ansible Roles

The following tasks are required:

### piEyes
- set up hostname and configuration (e.g. network)
- install packages (python3, ntp, camera, git, vim, htop, byobu)
- clone and install BeholderPi repository
- update discovery service (replace files with symlinks to git repo)
- install and configure telemetry (telegraf)
- install service for camera feed
