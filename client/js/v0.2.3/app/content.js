/**
 * Online Corpus Editor -- Content Manager
 * Deals with dynamically generated content
 * Zechy Wong
 * Last Modified: 23 June 2015
 */

define(function (require) {
    "use strict";

    var $ = require('jquery'),
        Config = require('app/config'),
        Log = require('app/log'),
        Util = require('app/util'),

        Processor = require('app/content.processor');

    var Content = {};

    // Load submodules
    Processor(Content);

    Log.debugLog("  [content]: Module ready.");

    return Content;
});
