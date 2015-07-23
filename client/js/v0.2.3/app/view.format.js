/**
 * Online Corpus Editor -- View Manager (submodule)
 * Content formatting for display
 * Zechy Wong
 * Last Modified: 23 June 2015
 *
 * N.B. Submodules return a function that accept the main module as a
 * parameter for initialisation; the function will extend the main module
 * when called.
 */

define(function (require) {
    "use strict";

    var $ = require('jquery'),
        Config = require('app/config'),
        Log = require('app/log'),
        Util = require('app/util'),
        Mark = require('markup'),
        Templates = require('text!app/view.templates.html');
    require('jMinEmoji-SVG_mod');
    require('jMinEmoji_mod');

    Log.debugLog("    [view.format]: Submodule ready.");

    // Markup.js templating
    // https://github.com/adammark/Markup.js
    var templates = {};
    var chunks = Templates.split("=====").splice(1);
    var i, key;

    chunks.forEach(function (chunk) {
        i = chunk.indexOf("\n");
        key = chunk.substr(0, i).trim();
        templates[key] = chunk.substr(i).trim();
    });

    Mark.globals.emojiclass = Config.emojiClass;

    return function (View) {

        View.format = {
            _templates: templates,

            formatAsTable: function (dataArray) {
                /**
                 * dataArray should have the following properties:
                 *  rowid     : Unique ID for that record
                 *  content   : Main content of that record
                 *  flag      : Boolean (stored as integer by SQLite)
                 *  category  : Integer
                 *  comment   : Free-form comment for that record
                 *  tags      : Space-separated list of tags for the record
                 */
                var context = {
                    records: dataArray
                };
                var options = {
                    pipes: {
                        nl2br: Util.nl2br
                    }
                };
                return Mark.up(this._templates['table-data'], context, options);
            },

            formatTotalView: function (totalRecords) {
                return Mark.up(this._templates['total-view'], {
                    total: totalRecords}
                );
            },

            formatTotalSearch: function (params) {
                /**
                 * params:
                 *  first   : ID of first search result displayed
                 *  last    : ID of last search result displayed
                 *  total   : Total number of search results
                 *  query   : Search query run
                 *  elapsed : Time taken for search
                 */
                return Mark.up(this._templates['total-search'], params);
            },

            renderEmoji: function () {
                View.getCurrentView().find('.' + Config.emojiClass).minEmojiSVG();
            }
        };

        /**
         * Turns emoji in the given jQuery object back into unicode
         * @returns {Object} The original jQuery object
         */
        $.fn.derenderEmoji = function () {
            this.find('.em').each(function () {
                $(this).replaceWith($(this).text());
            });
            return this;
        };
    }
});