try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

setup(name='beholderpi',
      description='BeholderPi',
      author='Ronny Eichler',
      author_email='ronny.eichler@gmail.com',
      version='0.1.5',
      packages=['beholder', 'piEye'],
      install_requires=['numpy', 'opencv-contrib-python', 'networkx', 'pyzmq', 'pyyaml'],
      # entry_points="""[console_scripts]
      #       beholder=beholder.main:main"""
      )
