# Setup

When setting up, we need access to the internet (to pull packages etc.).
After that we can switch to the local beholder.pi network.

When connecting a freshly flashed raspberry, it will start broadcasting
discovery packages.

The `influxpi` raspberry is running the local DHCP and DNS servers on
10.0.0.1 and has a static IP reserved for the beholder (currently antigoon)
at 10.0.0.11.

 >TODO: Install NTP server, too.

# Bootstrapping

- monitor the appearance of a new host in the discovery table.
- look up MAC adress of the new host:
    `ssh pi@host.ip 'cat /sys/class/net/eth0/address'`
- enter new MAC mapping in the `ansible/setup/network/vars.yml` file
- enter temporary IP in `ansible/setup/network/inventory`
- Execute the network setup playbook in the `ansible/setup/network` directory:
    `ansbible-playbook -i inventory main.yml`

This should set up the new host with proper IP.

- Verify new IP and correct host name in the discovery table
- update eye IP in `ansible/setup/network/inventory` file

> TODO: allow passing a new_host_ip variable to target only new hosts

<!--# Maintenance-->

<!--- For each node, start up wifi, connect to access point-->
<!--- update-->
<!--- shut down wifi-->
