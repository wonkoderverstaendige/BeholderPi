from math import ceil

FRAME_METADATA_H = 0
N_FRAMES_FPS_LOG = 20

PIEYE_SUB_TOPIC = b'PYSPY'

FFMPEG_BINARY = 'ffmpeg'

FFMPEG_COMMAND = [FFMPEG_BINARY,
                  '-y', '-hide_banner',
                  '-f', 'mjpeg',
                  '-r', '20.',
                  '-i', '-',
                  '-c:v', 'libx264',
                  '-preset', 'veryfast',
                  # '-fps', '30',
                  ]

# N_ROWS = 2
# N_COLS = ceil(len(SOURCES) / N_ROWS)
# N_COLORS = 3

# IMG_WIDTH = 640
# IMG_HEIGHT = 480

SOCKET_RECV_TIMEOUT = 1000
