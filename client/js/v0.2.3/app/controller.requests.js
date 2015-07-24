/**
 * Online Corpus Editor -- Content Manager (submodule)
 * High-level requests for data from the server
 * Last modified: 23 June 2015
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
        View = require('app/view'),
        WS = require('app/websocket');

    Log.debugLog("    [controller.requests]: Submodule ready.");

    return function (Controller) {

        Controller.requests = {
            /**
             * Fetches DB-wide metadata
             * Details in content.processor
             */
            fetchMeta: function () {
                var request = {
                    command: 'meta'
                };
                WS.sendRequest(request);
            },

            /**
             * Convenience function - Given the ID of a particular record, request the page that contains it.
             * @param recordID
             */
            fetchRecord: function (recordID) {
                // TODO: Make this account for staggered RowIDs. (i.e., this calculation should be done server-side)
                var start = recordID - ((recordID - 1) % Config.recordsPerPage);
                var end = start + Config.recordsPerPage - 1;
                this._fetchRecords(start, end, recordID);
            },

            /**
             * Makes the actual request to the database server.
             * @param start     - First record to fetch
             * @param end       - Last record to fetch
             * @param recordID  - Echo the requested record
             * @private
             */
            _fetchRecords: function (start, end, recordID) {
                var request = {
                    command: 'view',
                    start: start,
                    end: end,
                    record: recordID
                };
                WS.sendRequest(request);
            },

            /**
             * Requests an FTS search from the DB server.
             * @param query
             * @param page
             */
            execSearch: function (query, page) {
                // Sent as a URL string because the DB server can decode it using urllib.parse
                // TODO: Send all hashes without pre-processing; let the server handle it
                query = 's=' + encodeURIComponent(query) + '&p=' + page;

                var request = {
                    command: 'search',
                    query: query,
                    perpage: Config.recordsPerPage
                };

                // How very vista-esque
                View.alerts.notifySearch(null, {
                    afterShow: function () {
                        WS.sendRequest(request);
                    }
                });
            },

            /**
             * Requests an update on the specified record.
             * @param rowid - ID of the record to change
             * @param field - Name of the field to change
             * @param value - New value of the field
             */
            requestUpdate: function (rowid, field, value) {
                var request = {
                    command: 'update',
                    rowid: rowid,
                    field: field,
                    value: value
                };
                WS.sendRequest(request);
                Controller.nav.saveHash({
                    record: rowid,
                    noLoad: true
                });
                View.alerts.notifySave();
            },

            /**
             * Sends the given record ID to the server to initialise
             * language identification
             * @param rowid
             */
            execLangID: function (rowid) {
                var request = {
                    command: 'langid',
                    rowid: rowid
                };
                WS.sendRequest(request);
                Controller.nav.saveHash({
                    record: rowid,
                    noLoad: true
                })
            },

            /**
             * Calls for the server's language ID module to be retrained on
             * all available data
             */
            execRetrain: function (command) {
                var request = {
                    command: 'retrain'
                };
                WS.sendRequest(request);
                Controller.nav.saveHash({
                    noLoad: true
                })
            },

            /**
             * Calls for a server restart
             */
            execRestart: function () {
                var request = {
                    command: 'restart'
                };
                WS.sendRequest(request);
                Controller.nav.saveHash({
                    noLoad: true
                })
            },

            /**
             * Calls for a server shutdown
             */
            execShutdown: function () {
                var request = {
                    command: 'shutdown'
                };
                WS.sendRequest(request);
                Controller.nav.saveHash({
                    noLoad: true
                })
            },

            execDebug: function () {
                var request = {
                    command: 'debug'
                };
                WS.sendRequest(request);
                Controller.nav.saveHash({
                    noLoad: true
                })
            }
        };
    }
});