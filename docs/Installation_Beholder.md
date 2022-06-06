# Visualizer Installation
`conda create -n beholderpi`
`pip install -e .`


# Hardware


# Software

- default Ubuntu 18.04
- install drivers for r8125 NIC
- install new nvidia drivers (418)

##### THIS IS IMPORTANT FOR HARDWARE ACCELERATION TO WORK!
- install snap ffmpeg -- devmode

# NTP/Chrony
- install chrony
- enable chrony service
- disable timesyncd service (would stop chrony from launching due to conflict)