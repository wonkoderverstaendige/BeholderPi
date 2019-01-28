# # ZMQ setup
# zmq_sockets = []
# for n in range(NUM_STREAMS):
#     sock = context.socket(zmq.PUB)
#     target = 'tcp://*:{port:d}'.format(port=5555 + n)
#     sock.bind(target)
#     logging.debug('Socket bound at ' + target)
#     zmq_sockets.append(sock)
#
# # Buffer setup
# stream = io.BytesIO()

# last = time()
# for image in camera.capture_continuous(stream, format='jpeg', use_video_port=True):
#     logging.info(camera.frame.index)
#     elapsed = (time() - last) * 1000
#     last = time()
#     elapsed_str = "{:.1f} ms, {:.1f} ups ".format(elapsed, 1000 / elapsed)
#     camera.annotate_text = dt.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f') + ' @ ' + elapsed_str
#
#     # TODO: Check if multiple images in stream!
#     stream.truncate()
#     kB = stream.tell() / 1000
#     if kB > 230:
#         print(kB, 'kB in buffer!')
#
#     stream.seek(0)
#     for zs in zmq_sockets:
#         send_image(stream, zs)
