/**
 * Online Corpus Editor -- User Interaction
 * Zechy Wong
 * Last Modified: 23 June 2015
 */

define(function (require) {
    "use strict";

    var $ = require('jquery'),
        Config = require('app/config'),
        Log = require('app/log'),
        Util = require('app/util'),

        Nav = require('app/controller.nav'),
        Requests = require('app/controller.requests'),
        Edit = require('app/controller.edit'),
        Pager = require('app/controller.pager');

    var Controller = {};

    // Load submodules
    Nav(Controller);
    Requests(Controller);
    Edit(Controller);
    Pager(Controller);

    Log.debugLog("  [controller]: Module ready.");

    return Controller;
});