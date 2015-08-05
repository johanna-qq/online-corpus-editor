Installation
============

Server
------

### Python 3.4 (> 3.4.3)

#### Windows

Download and install Python 3.4. (https://www.python.org/)

Select the "Add python.exe to Path" option.

Optionally, verify that Python is accessible by starting a command prompt and running the `python` command.

#### Linux

Install Python 3.4 using your distribution's package manager.

Optionally, verify that Python is accessible by running `python3` in a terminal session.

### Python Libraries

Install the following libraries using `pip`.  (On linux, the command may be `pip3`.)

*Note*: Some of the server's dependencies are bundled in the `lib` directory.  These will take precedence over versions installed elsewhere on the system (but only for the server script).

**SQLAlchemy**: `pip install sqlalchemy`

> Windows: If you want to compile the optional C extension, you will need to have Microsoft Visual C++ 2010 installed.

**WebSockets**: `pip install websockets`

**NLTK**: `pip install nltk`

**PyEnchant**: `pip install pyenchant`

**NumPy**: `pip install numpy`

> Windows: Installation using `pip` will not work if you do not have Visual C++ 2010 installed.

> As an alternative, official binaries are available at from the NumPy sourceforge site (http://sourceforge.net/projects/numpy/files/).

### NLTK Setup

Start up the Python interpreter using `python`/`python3`.

Start the NLTK downloader:

```python
>>> import nltk
>>> nltk.download()
```

Install the `punkt` package.

### Data Files

You will need to provide your own corpus database and other data files; put them in the data folder.

See the configuration sections of main.py and oce/config.py for more information.
