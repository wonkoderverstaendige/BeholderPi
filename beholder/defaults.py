REC_BUTTON_DEBOUNCE = 2

N_FRAMES_FPS_LOG = 20

PIEYE_SUB_TOPIC = b'piEye'
PIEYE_METADATA_DTYPE = [('name', 'S8'), ('frame_index', '<i8'),
                        ('frame_gpu_ts', '<i8'), ('callback_gpu_ts', '<i8'),
                        ('callback_clock_ts', '<f8')]

# Note that as of Ubuntu 18.04 using ffmpeg installed with snap has
# intermittent failures acquiring a CUDA context. This can be worked around
# by installing the ffmpeg snap in --devmode
FFMPEG_BINARY = 'ffmpeg'
FFMPEG_COMMAND = [FFMPEG_BINARY,
                  '-y',
                  '-hide_banner',
                  '-loglevel', 'error',
                  '-nostats',

                  # '-hwaccel', 'cuvid',
                  # '-c:v', 'mjpeg_cuvid',

                  # '-pix_fmt', 'yuvj420p',
                  '-f', 'mjpeg',
                  '-r', '30.',
                  '-i', '-',
# '-filter:v hwupload_cuda,scale_npp=format=nv12:interp_algo=lanczos,hwdownload,format=nv12',
                  # '-c:v', 'libx264',
                  '-c:v', 'h264_nvenc',
                  '-b:v', '350k',
                  # '-gpu', 'list',
                  # '-c:v', 'copy',
                  '-preset', 'slow',
                  '-pix_fmt', 'yuv420p',
                  # '-profile:v', 'high',
                  '-vf', 'hqdn3d'
                  ]

SOCKET_RECV_TIMEOUT = 1000
WRITE_QUEUE_LENGTH = 150  # frames

FORCE_RECORDING_ON_TRIAL = True
