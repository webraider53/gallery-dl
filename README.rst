==========
gallery-dl
==========

*gallery-dl* is a command-line program to download image-galleries and
-collections from several image hosting sites (see `Supported Sites`_).
It is a cross-platform tool with many configuration options
and powerful filenaming capabilities.


|pypi| |build| |gitter|


Dependencies
============

- Python_ 3.4+
- Requests_

Optional
--------

- FFmpeg_: Pixiv Ugoira to WebM conversion
- youtube-dl_: Video downloads


Installation
============

Pip
---

The stable releases of *gallery-dl* are distributed on PyPI_ and can be
easily installed or upgraded using pip_:

.. code:: bash

    $ pip install --upgrade gallery-dl

Installing the latest dev-version directly from GitHub can be done with
pip_ as well:

.. code:: bash

    $ pip install --upgrade https://github.com/mikf/gallery-dl/archive/master.zip

Be sure the Python interpreter used for pip_ is version 3.4 or higher.
You might have to use :code:`pip3` or :code:`python3 -m pip`
depending on your system's defaults.


From Source
-----------

Get the code by either

* Downloading a stable_ or dev_ archive and unpacking it
* Or via :code:`git clone https://github.com/mikf/gallery-dl.git`

Navigate into the respective directory and run the :code:`setup.py` file.

.. code:: bash

    $ wget https://github.com/mikf/gallery-dl/archive/master.zip
    $ unzip master.zip
    # or
    $ git clone https://github.com/mikf/gallery-dl.git

    $ cd gallery-dl
    $ python setup.py install


Standalone Executable (Windows only)
------------------------------------

Windows users can download a `standalone executable`_, which comes with a
Python 3.4 interpreter and all required packages included.

Put this file in your `PATH <https://en.wikipedia.org/wiki/PATH_(variable)>`__
or use it from the current directory and you are good to go,


Usage
=====

To use *gallery-dl* simply call it with the URLs you wish to download images
from:

.. code:: bash

    $ gallery-dl [OPTION]... URL...

See also :code:`gallery-dl --help`.


Examples
--------

Download images; in this case from danbooru via tag search for 'bonocho':

.. code:: bash

    $ gallery-dl http://danbooru.donmai.us/posts?tags=bonocho


Get the direct URL of an image from a site that requires authentication:

.. code:: bash

    $ gallery-dl -g -u <username> -p <password> http://seiga.nicovideo.jp/seiga/im3211703


| Search a remote resource for URLs and download images from them:
| (URLs for which no extractor can be found will be silently ignored)

.. code:: bash

    $ gallery-dl r:https://pastebin.com/raw/FLwrCYsT


Configuration
=============

Configuration files for *gallery-dl* use a JSON-based file format.

| For a (more or less) complete example with options set to their default values,
  see gallery-dl.conf_.
| For a configuration file example with more involved settings and options,
  see gallery-dl-example.conf_.
| A list of all available configuration options and their
  descriptions can be found in configuration.rst_.

*gallery-dl* searches for configuration files in the following places:

+--------------------------------------------+------------------------------------------+
| Linux                                      | Windows                                  |
+--------------------------------------------+------------------------------------------+
|* ``/etc/gallery-dl.conf``                  |*                                         |
|* ``${HOME}/.config/gallery-dl/config.json``|* ``%USERPROFILE%\gallery-dl\config.json``|
|* ``${HOME}/.gallery-dl.conf``              |* ``%USERPROFILE%\gallery-dl.conf``       |
+--------------------------------------------+------------------------------------------+

(``%USERPROFILE%`` usually refers to the user's home directory,
i.e. ``C:\Users\<username>\``)

Values in later configuration files will override previous ones.


Authentication
==============

Username & Password
-------------------

Some extractors require you to provide valid login-credentials in the form of
a username & password pair.
This is necessary for ``pixiv``, ``nijie`` and ``seiga``
and optional (but strongly recommended) for ``exhentai``,  ``luscious``,
``sankaku``, ``idolcomplex``, ``tsumino`` and ``wallhaven``.

You can set the necessary information in your configuration file
(cf. gallery-dl.conf_)

.. code::

    {
        "extractor": {
            ...
            "pixiv": {
                "username": "<username>",
                "password": "<password>"
            }
            ...
        }
    }

or you can provide them directly via the
:code:`-u/--username` and :code:`-p/--password` or via the
:code:`-o/--option` command-line options

.. code:: bash

    $ gallery-dl -u <username> -p <password> URL
    $ gallery-dl -o username=<username> -o password=<password> URL

OAuth
-----

*gallery-dl* supports user authentication via OAuth_ for
``deviantart``, ``flickr``, ``reddit``, ``smugmug`` and ``tumblr``.
This is entirely optional, but grants *gallery-dl* the ability
to issue requests on your account's behalf and enables it to access resources
which would otherwise be unavailable to a public user.

To link your account to *gallery-dl*, start by invoking it with
``oauth:<site-name>`` as an argument. For example:

.. code:: bash

    $ gallery-dl oauth:flickr

You will be sent to the site's authorization page and asked to grant read
access to *gallery-dl*. Authorize it and you will he shown one or more
"tokens", which should be added to your configuration file.


.. _gallery-dl.conf:         https://github.com/mikf/gallery-dl/blob/master/docs/gallery-dl.conf
.. _gallery-dl-example.conf: https://github.com/mikf/gallery-dl/blob/master/docs/gallery-dl-example.conf
.. _configuration.rst:       https://github.com/mikf/gallery-dl/blob/master/docs/configuration.rst
.. _Supported Sites:         https://github.com/mikf/gallery-dl/blob/master/docs/supportedsites.rst
.. _standalone executable:   https://github.com/mikf/gallery-dl/releases/download/v1.6.3/gallery-dl.exe
.. _stable:                  https://github.com/mikf/gallery-dl/archive/v1.6.3.zip
.. _dev:                     https://github.com/mikf/gallery-dl/archive/master.zip

.. _Python:     https://www.python.org/downloads/
.. _PyPI:       https://pypi.org/
.. _pip:        https://pip.pypa.io/en/stable/
.. _Requests:   http://docs.python-requests.org/en/master/
.. _FFmpeg:     https://www.ffmpeg.org/
.. _youtube-dl: https://rg3.github.io/youtube-dl/
.. _OAuth:      https://en.wikipedia.org/wiki/OAuth

.. |pypi| image:: https://img.shields.io/pypi/v/gallery-dl.svg
    :target: https://pypi.org/project/gallery-dl/

.. |build| image:: https://travis-ci.org/mikf/gallery-dl.svg?branch=master
    :target: https://travis-ci.org/mikf/gallery-dl

.. |gitter| image:: https://badges.gitter.im/gallery-dl/main.svg
    :target: https://gitter.im/gallery-dl/main
