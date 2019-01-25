# BeholderPi
piEye of the Beholder


# piEye
- raspberries with camera module, streaming via ZMQ

# Beholder
- Master, gathering streams, displaying and writing to disk


# Outline

- array of ~12 camera nodes covering a 4 m * 8 m space with small overlap in FOV

- reliable recording for offline analysis, either
    a) local to the raspberry (USB drive, SD card)
    b) remotely by master computer after streaming

- minimally 640x480 @ 15 fps, better 720p30 if possible

- for online scoring, we want a live stream, stitching the individual views

- low latency, no (few) dropped frames

- common reference frame for timestamps across all cameras

- synchronizable to external system (e.g. ephys)

There's hundreds of ways and options to go about streaming the video. Most importantly, encoding/decoding needs to be done in hardware, so it needs libraries/tools that support the Raspberry hardware.

FFMPEG can read from V4L2 driver, I got RTSP to work, but with lag. I needed to increase the key frame interval, or the stream got corrupted.

Raspivid is the tool provided to easily interface the camera module. It can directly grab the JPEG or x264 frames without the need to decode/reencode the frames.

We could grab the frame in raspivid and relay the x264 frame directly via e.g. ZMQ to a master PC that stitches and transcodes/stores.

# Hardware

- [RaspberryPi 3B+](https://www.raspberrypi.org/documentation/hardware/raspberrypi/README.md)
	- ~250-300 Mbit ethernet
	- 1 GByte RAM
- [PiCamera v2.1](https://www.raspberrypi.org/documentation/hardware/camera/README.md)
	- FOV: 62.2° horizontal, , 48.8° vertical, i.e. 2.5 m x 1.7 m at 210 cm distance

**Read: ** [How the PiCamera works](https://picamera.readthedocs.io/en/release-1.13/fov.html)

- [PoE hat](https://www.raspberrypi.org/products/poe-hat/) for power/network

- PoE capable switch (max. 10W / Raspberry), e.g. [Netgear GS116PP](https://www.netgear.com/support/product/GS116PP.aspx)


# Software

- Raspian Stretch Lite
- Camera -> CSI -> GPU -> OpenMAX -> [MMAL](https://github.com/techyian/MMALSharp/wiki/What-is-MMAL%3F) -> raspivid/v4l2/uvc/python
- `raspivid` to grab/display/stream/store frames from PiCamera

# Inspiration

## Raspicam paper
There's some prior work done by [Saxena et al. 2018](https://www.physiology.org/doi/full/10.1152/jn.00215.2018), [code here](https://github.com/DeshmukhLab/PicameraPaper). They however record videos only localy for offline analysis.

## Netcat stream forwarding

https://dantheiotman.com/2017/08/23/using-raspivid-for-low-latency-pi-zero-w-video-streaming/

## Raspivid
[Documentation](https://www.raspberrypi.org/documentation/usage/camera/raspicam/raspivid.md)
[Source]()


# Installation

## Hardware

- screw in spacers
- open camera FPC cable slot
- attach PoE hat, carefully aligning the standoffs and headers
- slide in camera flat cable, shiny silver pins facing towards HDMI connector
- gently press down FPC lever with blade from top
- attach keyboard, mouse, ethernet and/or power, HDMI

## Raspbian

- download and flash [Raspbian Stretch lite](https://www.raspberrypi.org/downloads/raspbian/) to microSD card (e.g. using [Etcher](etcher.io))
- check boot screen for obvious errors
- log in with `pi:raspberry`
- Configure with `sudo rapsi-config`:
	- set locale (Localisation -> Keyboard Layout -> US, by default, keyboard is UK mapping!! Beware for password!)
	- enable camera (Interfacing -> Camera)
	- enable ssh (Interfacing -> SSH)

- change passord with `passwd`
- connect to network with internet access
- update/upgrade `sudo apt update && sudo apt upgrade
- test camera with `raspivid -t 0`
- edit `/etc/dhcpcd.conf` to set up static IP

## Picamera/Python
- `sudo apt install byobu htop vim python3-pip python3-picamera python3-zmq`


# TODO:
- grab in YUV, drop UV, raw grayscale -> write to grayscale x264 directly. All buffersizes known, no decoding step.
- set up NTP server on master, slaves `iburst` synchronize on startup
- fuzz for corner cases when recording and clients drop out
