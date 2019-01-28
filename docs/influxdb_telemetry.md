# InfluxDB telemetry

- install Raspbian Stretch Lite
- update && upgrade, set up ssh, keyboard, passwd, vim, byobu, htop etc...
- Set up InfluxDB repo
	- `$ curl -sL https://repos.influxdata.com/influxdb.key | sudo apt-key add -`
	- `$ echo "deb https://repos.influxdata.com/debian stretch stable" | sudo tee /etc/apt/sources.list.d/influxdb.list`
	- `$ sudo apt update`
	- `$ sudo apt install telegraf influxdb chronograf kapacitor`

## InfluxDB
- `$ sudo systemctl start influxdb`, defaults to port 8086
- `$ influx` to start influxdb shell, `> auth` to authenticate

Influxdb will require authentication the moment here is a admin user.

- `> CREATE USER admin WITH PASSWORD 'adminpw' WITH ALL PRIVILEGES`
- in `/etc/influxdb/influxdb.conf` under `[http]` set `auth-enabled = true`

- `> CREATE DATABASE telegraf`
	- `> SHOW DATABASES`
    - `> CREATE USER telegraf WITH PASSWORD 'userpw'`
    	- (`> SET PASSWORD FOR "user" = 'abcdef'`  to change)
    - `> GRANT ALL ON telegraf TO telegraf`
    - `> SHOW USERS`
    
    Optionally set the retention policy to reduce space use
    - `> CREATE RETENTION POLICY thirty_days ON telegraf DURATION 30d REPLICATION 1 DEFAULT`
    - `> SHOW RETENTION POLICIES ON telegraf`

## Telegraf

To store the configuration file in the github repo, we need to either
modify the telegraf service, or link the default location to our version.

- create symlink from `/etc/telegraf/telegraf.conf` to repo conf file
- Add password and username environment variables to `/etc/default/telegraf`
- `$ sudo systemctl start telegraf`
