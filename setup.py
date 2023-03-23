try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

# Most packages are available from conda and we can get the tricky
# opencv package via `conda install -c conda-forge opencv` built with qt
conda_packs = []

# But if not using conda, we can go with the pip available package:
pip_packs = {'pip': ['opencv-contrib-python', 'numpy', 'networkx', 'pyzmq', 'pyyaml']}

setup(name='beholderpi',
      description='BeholderPi',
      author='Ronny Eichler',
      author_email='ronny.eichler@gmail.com',
      version='0.1.5',
      packages=['beholder', 'piEye'],
      install_requires=conda_packs,
      extras_require=pip_packs,
      # entry_points="""[console_scripts]
      #       beholder=beholder.main:main"""
      )
