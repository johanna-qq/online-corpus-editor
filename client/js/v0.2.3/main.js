/**
 * Online Corpus Editor
 * Zechy Wong
 * Last Modified: 26 June 2015
 *
 * External Resources:
 * minEmoji     (https://github.com/rodrigopolo/minEmoji)
 * noty         (http://ned.im/noty/)
 * tag-it       (https://github.com/aehlke/tag-it)
 * RequireJS    (http://requirejs.org/)
 * Markup.js    (https://github.com/adammark/Markup.js)
 */

requirejs.config({
    paths: {
        app: "../app"
    }
});

// Load up error handling script for more complex cases
requirejs(["app/error"]);

// Load up jQuery, wait for initial document ready event before continuing
requirejs(["jquery"], function () {
    $(function () {
        requirejs(["app/init"]);
    });
});

/**
 * Changelog
 * =========
 * v0.2:    Don't cache me, bro - Version-based cache busting introduced
 * v0.2.1:  Pako-pako - Compression of WebSocket frames
 * v0.2.2:  The Great Tagsby - Tagging works again
 */