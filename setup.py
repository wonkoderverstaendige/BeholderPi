try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

setup(name='BeholderPi',
      description='BeholderPi',
      author='Ronny Eichler',
      author_email='ronny.eichler@gmail.com',
      version='0.1.5',
      # install_requires=['nose', 'termcolor', 'vispy', 'numpy', 'tqdm', 'scipy', 'matplotlib', 'h5py', 'hdf5storage'],
      packages=['beholder', 'piEye'],
      # entry_points="""[console_scripts]
      #       dm=dataman.dataman:main"""
      )
