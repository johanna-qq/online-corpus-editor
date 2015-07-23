/**
 * Online Corpus Editor -- Content Manager (submodule)
 * Processing of data received from server
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

        View = require('app/view'),
        Controller = require('app/controller'),
        Meta = require('app/meta');

    Log.debugLog("    [content.processor]: Submodule ready.");

    return function (Content) {

        Content.processor = {
            processMessage: function (msg) {
                // msg looks like:
                // { command: <request type>, data: <results of request> }

                // If we were reconnecting, we're not anymore
                View.alerts.removeReconnect();


                // Catch general errors here.
                if (msg.data.error === true) {
                    View.alerts.showError(
                        Util.escapeHTML(Util.nl2br(msg.data.message), true)
                    );
                    return;
                } else {
                    View.alerts.removeError();
                }

                // Delegate to handlers based on the command specified in the
                // message
                var functionName = 'command' + msg.command.charAt(0).toUpperCase()
                    + msg.command.slice(1).toLowerCase();

                var fn = this[functionName];
                if (typeof fn === "function") {
                    fn.call(this, msg);
                } else {
                    console.log('Error: ' + functionName + ' needs to be defined.');
                }
            },

            commandMeta: function (msg) {
                Meta.totalRecords = msg.data.total;
                Meta.tagsAvailable = msg.data.tags;
            },

            commandView: function (msg) {
                View.replace(
                    View.format.formatTotalView(Meta.totalRecords) +
                    View.format.formatAsTable(msg.data.results)
                );
                View.format.renderEmoji();
                View.alerts.removeConnecting();

                // If the target row is not the first one on the page,
                // highlight it and scroll to it.  If it is, scroll to the
                // top of the page.
                var targetRow = msg.data.record;
                // Pick out the row from the current view (there might be
                // other views with the same IDs waiting to be GC-ed)
                var $targetRow = View.getCurrentView().find('#row-' + targetRow);

                if (targetRow !== msg.data.results[0].rowid) {
                    $targetRow.addClass('row-highlight');
                    Util.addToGlobalQueue(function () {
                        View.scrollTo({
                            element: $targetRow
                        });
                    })
                } else {
                    Util.addToGlobalQueue(function () {
                        View.scrollToTop();
                    });
                }

                // Edit Update Handlers
                Controller.edit.initHandlers();

                // Update Pager
                Controller.pager.pagerUpdate({
                    mode: 'view',
                    totalRecords: Meta.totalRecords,
                    numPages: Math.ceil(Meta.totalRecords / Config.recordsPerPage),
                    currentPage: Math.floor(msg.data.results[0].rowid / Config.recordsPerPage) + 1
                });
            },

            commandSearch: function (msg) {
                // Did the search fail?
                if (msg.data.results === "error") {
                    View.alerts.notifySearch(false);
                    // Reset the hash but don't kick the user back to the
                    // homepage.
                    Controller.nav.saveHash({
                        noLoad: true
                    });
                    return;
                }
                // The number of results, the time elapsed, any
                // modifications to the search string, and the offset are
                // passed along with the actual data.
                Meta.totalSearch = msg.data.total;
                var query = msg.data.query,
                    elapsed = msg.data.elapsed,
                    page = Math.floor(msg.data.offset / Config.recordsPerPage) + 1;

                // Save the new search string to the hash and input box, suppressing the hash change handler
                // Encode the query before saving it to the hash -- Prevents problems with queries that contain % signs.
                Controller.nav.saveHash({
                    query: query,
                    page: page,
                    noLoad: true
                });
                $('#' + Config.searchID).val(query);

                // Format and display results
                var first = msg.data.offset + 1,
                    last = msg.data.offset + Config.recordsPerPage;
                if (last > Meta.totalSearch) {
                    last = Meta.totalSearch;
                }

                View.replace(
                    View.format.formatTotalSearch({
                        first: first,
                        last: last,
                        total: Meta.totalSearch,
                        query: query,
                        elapsed: elapsed
                    }) +
                    View.format.formatAsTable(msg.data.results)
                );
                View.format.renderEmoji();
                View.alerts.removeConnecting();

                View.scrollToTop();

                // Edit handlers
                Controller.edit.initHandlers();

                // Pager update
                Controller.pager.pagerUpdate({
                    mode: 'search',
                    query: query,
                    numPages: Math.ceil(Meta.totalSearch / Config.recordsPerPage),
                    currentPage: Math.floor(msg.data.offset / Config.recordsPerPage) + 1
                });

                // Close the search notification
                View.alerts.notifySearch(true);
            },

            commandUpdate: function (msg) {
                // We're expecting the server to reply with a success
                // acknowledgement to our update request
                if (msg.data === "success") {
                    View.alerts.notifySave(true);
                    // Call for a metadata update (which should include new tags)
                    Controller.requests.fetchMeta();
                } else {
                    View.alerts.notifySave(false);
                }
            },

            commandLangid: function (msg) {
                var txt = msg.data[0] + "<br>" + msg.data[1];
                View.alerts.showInfo(txt);
                View.scrollToTop();
            },

            commandRetrain: function (msg) {
                if (msg.data === true) {
                    var txt = "Language ID classifier retrained" +
                        " successfully.";
                    View.alerts.showInfo(txt);
                    View.scrollToTop();
                }
            }
        };
    }
});