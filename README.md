# Online Corpus Editor

A tool for browsing and annotating corpora online.

## Usage (Server)

See `docs/INSTALL.md` for basic installation steps.

After installation, run `start-server` from the server directory (`start-server.bat` for Windows).

    $ ./start-server

Pass `-h` or `--help` as an argument to see the other options available.

## Usage (Client)

Serve the entire `client` directory with your favourite web server.

## Usage (Client - Alpha)

**Note**: The alpha client is *not* yet usable in its current state.

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
