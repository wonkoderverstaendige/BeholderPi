![BeholderPi logo](docs\images\BeholderPiLogo.svg.png "BeholderPI logo")

# BeholderPi
piEye of the Beholder

# Outline

- scalable array of networked camera nodes
- low-cost (relatively) ~100--200 Euro/node
- 800x600 @ 30 fps in visible or IR
- low latency preview of merged views
- synchronized to sub-millisecond time resolution
- hardware accelerated encoding
- synchronization with external systems (e.g. elecrophysiology recordings)

# Hardware

- [RaspberryPi 3B+/4B](https://www.raspberrypi.org/documentation/hardware/raspberrypi/README.md)
- [Raspberry/Picamera compatible camera module](https://www.raspberrypi.org/documentation/hardware/camera/README.md)
    - e.g. Camera Module v2 (8MP, FOV: 62.2° horizontal, 48.8° vertical)
    - **Read: ** [How the PiCamera works](https://picamera.readthedocs.io/en/release-1.13/fov.html)
- [PoE hat](https://www.raspberrypi.org/products/poe-hat/) for power/network
- A decent receiving computer (ideally 1 CPU core/node)
- optional hardware encoding GPU
- PoE capable ethernet switch if PoE is used

# Software
- based on Picamera, ZMQ, OpenCV, FFmpeg

# Inspiration
## Raspicam paper
Inspiration of the system was taken from prior work done by [Saxena et al. 2018](https://www.physiology.org/doi/full/10.1152/jn.00215.2018),
[code here](https://github.com/DeshmukhLab/PicameraPaper).

# Installation
1) [System Overview](docs/SystemOverview.md)
2) [Beholder Installation](docs/Installation_Beholder.md)
3) [Eye Installation](docs/Installation_Eye.md)
4) [General Usage](docs/Usage.md)
5) [Troubleshooting](docs/Troubleshooting.md)

## Hardware
- [Camera Mounts](docs/CameraMounts.md)
- [Sync Lights](docs/SyncLights.md)

## Processing
- [Stitching](docs/processing/Stitching.md)
- [Synchronization](docs/Synchronization.md)
- [Tracing](docs/Tracing.md)
- [Tracking](docs/Tracking.md)

# TODO
- see [current todo list](docs/todo.md)