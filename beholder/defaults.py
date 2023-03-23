REC_BUTTON_DEBOUNCE = 2

N_FRAMES_FPS_LOG = 20

PIEYE_SUB_TOPIC = b'piEye'
PIEYE_METADATA_DTYPE = [('name', 'S8'), ('frame_index', '<i8'),
                        ('frame_gpu_ts', '<i8'), ('callback_gpu_ts', '<i8'),
                        ('callback_clock_ts', '<f8')]

NUM_PIPE_RETRIES = 3
DISK_MIN_GB = 10
DISK_LOW_GB = 30

# name (or path) of the ffmpeg executable. Used to differentiate system
# installed ffmpeg from our hardware enabled/customized variant
FFMPEG_BINARY = 'ffmpeg_gpu'
# FFMPEG_COMMAND = [FFMPEG_BINARY,
#                   '-y',
#                   '-hide_banner',
#                   '-loglevel', 'error',
#                   '-nostats',
#
#                   # '-hwaccel', 'cuvid',
#                   # '-c:v', 'mjpeg_cuvid',
#
#                   # '-pix_fmt', 'yuvj420p',
#                   '-f', 'mjpeg',
#                   '-r', '30.',
#                   '-i', '-',
# # '-filter:v hwupload_cuda,scale_npp=format=nv12:interp_algo=lanczos,hwdownload,format=nv12',
#                   # '-c:v', 'libx264',
#                   '-c:v', 'h264_nvenc',
#                   '-b:v', '350k',
#                   # '-gpu', 'list',
#                   # '-c:v', 'copy',
#                   '-preset', 'slow',
#                   '-pix_fmt', 'yuv420p',
#                   # '-profile:v', 'high',
#                   '-vf', 'hqdn3d'
#                   ]

FFMPEG_COMMAND = [FFMPEG_BINARY,
                  '-y',
                  '-hide_banner',
                  '-loglevel', 'error',
                  '-nostats',
                  '-vsync', '0',
                  '-hwaccel', 'cuvid',
                  '-c:v', 'mjpeg_cuvid',
                  '-r', '30.',
                  '-i', '-',
                  '-c:v', 'h264_nvenc',
                  '-b:v', '400k',
                  '-preset', 'slow',
                  '-movflags', 'faststart',
                  ]

SOCKET_RECV_TIMEOUT = 1000
WRITE_QUEUE_LENGTH = 150  # frames

FORCE_RECORDING_ON_TRIAL = True
