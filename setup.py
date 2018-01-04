from setuptools import setup

setup(
    name = 'AssetLabelGenerator',
    version = '0.1',
    description='A python command line tool for generating asset labels for Snipe-IT',
    long_description='''''',
    url='',
    author='Alex Tremblay',
    license='LGPLv3',
    classifiers=[
        'Development Status :: 4 - Beta',

        'Environment :: Console',

        'Intended Audience :: System Administrators',
        'Intended Audience :: Telecommunications Industry',

        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: System :: Networking',
        'Topic :: System :: Systems Administration',
        'Topic :: Utilities',

        'License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)',

        'Operating System :: MacOS',
        'Operating System :: Microsoft',
        'Operating System :: POSIX',
        'Operating System :: POSIX :: Linux',
        'Operating System :: Unix',

        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    packages = ['AssetLabelGenerator'],
    install_requires=['requests', 'pystache', 'cryptography', 'EasySettings',
                      'qrcode', 'pillow'],
    entry_points = {
        'console_scripts': [
            'mkassetlabel = AssetLabelGenerator.mkassetlabel:main'
        ]
    }
)