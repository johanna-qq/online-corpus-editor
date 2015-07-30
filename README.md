# Online Corpus Editor

A tool for browsing and annotating corpora online.

## Usage (Server)

Install Python 3.4.3 and the dependencies listed in `main.py`.

Some of the dependencies are bundled in the `lib` directory; note that these will take precedence over versions installed elsewhere on the system (but only for the server script).

You will need to provide your own corpus database and other data files; put them in the `data` folder.  See the configuration sections of `main.py` and `oce/config.py` for more information.

From the server directory, run `start-server` (`start-server.bat` for Windows).

    $ ./start-server

## Usage (Client)

Serve the entire `client` directory with your favourite web server.


## Usage (Client -- Alpha)

Install `npm`, `bower` and `grunt-cli`.

    $ npm install -g bower grunt-cli

From the `client-alpha` directory, install the application dependencies:

    $ npm install
    $ bower install

Build the application:

    $ grunt build

(Optionally, use `grunt build-imagemin` to use `grunt-contrib-imagemin` as well.)

Serve the `dist` folder with your favourite web server or `grunt serve:dist`

### Development

From the `client-alpha` directory, start the development server:

    $ grunt serve

Any changes made to the application files will be live-reloaded.
