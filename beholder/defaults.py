from math import ceil

FRAME_METADATA_H = 0
N_FRAMES_FPS_LOG = 20

PIEYE_SUB_TOPIC = b'PYSPY'

FFMPEG_BINARY = 'ffmpeg'

FFMPEG_COMMAND = [FFMPEG_BINARY,
                  '-y', '-hide_banner',
                  '-f', 'mjpeg',
                  '-r', '30.',
                  '-i', '-',
                  '-c:v', 'libx264',
                  # '-c:v', 'copy',
                  '-preset', 'veryfast',
                  '-vf', 'hqdn3d'
                  ]

SOCKET_RECV_TIMEOUT = 1000
