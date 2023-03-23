# Hardware
- decently powered desktop GPU
  - a core per stream is recommended
- optionally a hardware encoding capable GPU
  - even smaller NVIDIA Quadro cards allow multiple encode/decode streams
  - note consumer cards are limited to 2 streams only and hence useless for larger setups
- ideally two network interfaces
  - it's best to keep the eyes on their own isolated subnet

# OS and Environment
- default Ubuntu 22.04 LTS
- Install AnyDesk (optional, only for our setup)
- `apt install build-essential vim git htop byobu unzip wget cmake yasm`
- copy `id_beholderpi` ssh keys

# The whole NVIDIA mess...
It can be tricky to match compatible versions of the nvidia-drivers, nvidia-compute-utils, nvidia-cuda-toolkit and the
ffmpeg nv headers. Best use the nvidia repositories to get cuda, which comes with
a matching driver etc., then we just need to make sure the ffmpeg nv headers
are up to date to work with them.

See https://docs.nvidia.com/cuda/cuda-installation-guide-linux/index.html#ubuntu
- `wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.0-1_all.deb`
- `sudo dpkg -i cuda-keyring_1.0-1_all.deb`
- `echo "deb [signed-by=/usr/share/keyrings/cuda-archive-keyring.gpg] https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/ /" | sudo tee /etc/apt/sources.list.d/cuda-ubuntu2204-x86_64.list`

pin file to prioritize CUDA repo:
- `wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-ubuntu2204.pin`
- `sudo mv cuda-ubuntu2204.pin /etc/apt/preferences.d/cuda-repository-pin-600`
Install CUDA
- `sudo apt update && sudo apt install cuda`
- Reboot
- Add cuda to PATH
  - `PATH="/usr/local/cuda/bin:$PATH"`

## FFMPEG with Nvidia nvenc
### Install Headers
- `git clone https://github.com/FFmpeg/nv-codec-headers.git`
- `cd nv-codec-headers && sudo make install && cd –`

### FFMPEG from source
- `apt install build-essential yasm cmake libtool libc6 libc6-dev libnuma1 libnuma-dev`
- `git clone https://git.ffmpeg.org/ffmpeg.git ffmpeg/`
- `cd ffmpeg`

**Note: Perhaps static is better to not be affected if libs change/wander about with driver updates?**
- `./configure  --enable-nonfree --enable-cuda-nvcc --enable-libnpp --extra-cflags=-I/usr/local/cuda/include --extra-ldflags=-L/usr/local/cuda/lib64`
**Else we can compile with shared libs:**
- `./configure --enable-nonfree --enable-cuda-nvcc --enable-libnpp --extra-cflags=-I/usr/local/cuda/include --extra-ldflags=-L/usr/local/cuda/lib64 --disable-static --enable-shared`

- add ffmpeg/ffprobe to PATH, either copy executables to ~/.local/bin or make local bin directory with links:
  - `mkdir ~/bin && cd bin`
  - `ln -s ~/src/ffmpeg/ffmpeg ffmpeg_gpu`
  - `ln -s ~/src/ffmpeg/ffprobe ffprobe_gpu`
  - Append to `~/.bashrc`:
  ```bash
  if [ -d "$HOME/bin" ] ; then
    PATH="$HOME/bin:$PATH"
  fi
  ```

# Beholder
## Python
- get Anaconda or miniconda Python
  - download from https://anaconda.com
  - `chmod +x <installer-file-name>.sh`
  - `./<installer-file-name>.sh`
  - Accept licence and default `$HOME/anaconda3` path
  - init anaconda (in installer, or via `conda init`)
  - restart shell, conda base should be active `(base) username@beholder-desktop:~$ `
  - update conda `conda update -n base -c defaults conda`

## BeholderPi
- `cd ~/src/`
- `git clone https://github.com/wonkoderverstaendige/BeholderPi`
- `cd BeholderPi`
- `conda env create -n beholder -f requirements.yaml`
- `conda activate beholder`
- `pip install -e .`
- `cp scripts/launchers/* ~/bin/`
- check if beholder launches with `beholder`

# NTP/Chrony
- `sudo apt install chrony`
- `sudo timedatectl set-ntp off`
- copy the chrony conf file
  - `mv /etc/chrony/chrony.conf /etc/chrony/chrony.conf.bak` 
  - `cp ~/src/BeholderPi/ansible/templates/beholder/chrony.conf.j2 /etc/chrony/chrony.conf`
- `sudo systemctl enable --now chrony`
- check chrony status occasionally

## Verify NTP synchronization
- check `chronyc tracking` on beholder
  - connected to a reference server?
- check `chronyc tracking` on spectator+eyes
  - is beholder PC the reference server and are offsets low? 

# Disable automatic upgrades of especially the nvidia drivers etc.
- `sudo apt-mark hold `:
  - `nvidia-compute-utils-XXX`
  - `nvidia-dmks-XXX`
  - `nvidia-driver-XXX`
  - `nvidia-kernel-common-XXX`
  - `nvidia-kernel-source-XXX`
  - `nvidia-utils-XXX`
  - `nvidia-modprobe`
can be reversed with `apt-mark unhold ...`

# Conveniences
- disable screen suspend
- disable sleep/hibernate/power keys to prevent accidental shutoffs mid experiment
  - `sudo -e logind.config`
  - uncomment and change `HandleSuspendKey` and  `HandleHibernateKey` to `ignore`
