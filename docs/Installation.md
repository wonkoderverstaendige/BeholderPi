# SD card installation

## Create custom raspbian image

SSH is disabled by default. To enable, an (empty) `ssh` file needs to be
 present the `/boot` partition

See this [blog post](https://kenfallon.com/safely-enabling-ssh-in-the-default-raspbian-image/)
for details, and `scripts/prepare_raspbian_piEye_image.bash`. This creates a
raspbian image with ssh enabled, keys copied and default passwords set.

