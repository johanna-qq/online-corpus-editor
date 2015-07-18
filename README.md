# Online Corpus Editor

A tool for browsing and annotating corpora online.

## Usage (Server)

Install Python 3.4.3 and the dependencies listed in `main.py`.

Some of the dependencies are bundled; note that these will take precedence over versions installed elsewhere on the system for the server script.

Put your corpus database and other data files in the `data` folder -- See the configuration sections of `main.py` and `oce/config.py` for more information.

From the server directory, start `main.py`:

    python3 main.py

## Usage (Client)

Install `npm`, `bower` and `grunt-cli`.

    npm install -g bower grunt-cli

From the client directory, install the application dependencies:

    npm install
    bower install

Build the application:

    grunt build

(Optionally, use `grunt build-imagemin` to use `grunt-contrib-imagemin` as well.)

Serve the `dist` folder.