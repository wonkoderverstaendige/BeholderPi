```sh
sudo add-apt-repository ppa:graphics-drivers/ppa
sudo apt-get update && sudo apt-get -y upgrade
sudo apt-get install nvidia-kernel-source-418 nvidia-driver-418
```

This will cause freezes of the ubuntu desktop due to a conflict between the nvidia
drivers and the HWE stack. We need to reinstall the non-HWE Xorg packages.

`sudo apt install ubuntu-desktop` should pull all the non-Xorg packages in.

Next we need to grab the nvidia headers:

```sh
git clone https://git.videolan.org/git/ffmpeg/nv-codec-headers.git
cd nv-codec-headers
make
sudo make install
```


## The snap way (BAD)
Then we can just install the latest ffmpeg snap (e.g. 4.1 seems to work) with
`-nvenc-enabled` flag.

`sudo snap install ffmpeg`

--> HOWEVER, the snap has atrocious startup times, many times longer, especially the first launch. This can cause issues with dropped frames.

## The non-snap way (GOOD)
Instead we want to compile our own ffmpeg with NVENC support. Luckily I did this without taking notes due to time pressure in the moment... so you are on your own.
