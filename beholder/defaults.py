from math import ceil

FRAME_METADATA_H = 0
N_FRAMES_FPS_LOG = 20

PIEYE_SUB_TOPIC = b'PYSPY'

FFMPEG_BINARY = 'ffmpeg'

FFMPEG_COMMAND = [FFMPEG_BINARY,
                  '-y',
                  '-hide_banner',
                  '-loglevel', 'error',
                  '-nostats',
                  '-f', 'mjpeg',
                  # '-hwaccel', 'nvdec',
                  '-r', '30.',
                  '-i', '-',
                  # '-pix_fmt', 'yuv420p',
                  '-c:v', 'libx264',
                  # '-c:v', 'h264_nvenc',
                  # '-c:v', 'copy',
                  '-preset', 'fast',
                  # '-profile:v', 'high',
                  '-vf', 'hqdn3d'
                  ]

SOCKET_RECV_TIMEOUT = 1000
