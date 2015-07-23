/**
 * Online Corpus Editor -- User Interaction (submodule)
 * Hash-based navigation
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
        WS = require('app/websocket');

    Log.debugLog("    [controller.nav]: Submodule ready.");

    return function (Controller) {

        Controller.nav = {
            _lastLoadedHash: null,
            _recordsPerPage: Config.recordsPerPage,
            _recordJumpID: Config.recordJumpID,
            _pageJumpID: Config.pageJumpID,
            _searchID: Config.searchID,
            /**
             * Gets current hash in the URL, including leading '#'.
             * Uses location.href to deal with FF's automatic URI decoding.
             * @returns {string}
             */
            getHash: function () {
                var hash = '';
                // THANKS, Firefox.
                var indexOfHash = location.href.indexOf("#");
                if (indexOfHash > -1) {
                    hash = location.href.substring(indexOfHash);
                }
                return hash;
            },
            /**
             * Changes the hash in the URL to reflect a request for data, and calls navHashRequest to perform the actual request.
             * Search queries in the new hash should be URI encoded.
             * Used as window onhashchange handler.
             * @param {string} newHash - The new hash, including leading '#'.
             * @param {boolean} noLoad - If true, the actual request for data is not performed.
             * @param {boolean} forceLoad - If true, perform the data request even if the new hash is the same as the current one.
             */
            _setHash: function (params) {
                var newHash = params.newHash;
                if (typeof newHash === 'undefined') {
                    // Probably triggered by a user-initiated hash change -- Use the current (i.e., new) hash.
                    newHash = this.getHash();
                }
                var noLoad = params.noLoad;
                var forceLoad = params.forceLoad;
                if (newHash === this._lastLoadedHash) {
                    // Nothing to do here, unless forceLoad is true.
                    if (forceLoad) {
                        this.hashRequest();
                    }
                } else {
                    // This *will* retrigger the function via window's
                    // hashchange handler, but the page won't be reloaded since
                    // this._lastLoadedHash is the same (and the handler
                    // does not pass forceLoad)
                    location.hash = newHash;
                    this._lastLoadedHash = newHash;
                    if (!noLoad) {
                        this.hashRequest();
                    } else {
                        // noLoad passed, but let's still change the title to
                        // avoid confusion
                        this.updateTitle();
                    }
                }
            },

            /**
             * Convenience function -- Assembles a hash from the components
             * given.
             * @param params
             */
            createHash: function (params) {
                var record = params.record,
                    query = params.query,
                    page = params.page;

                var hash = '#';

                if (typeof query !== "undefined") {
                    if (hash.length > 1) {
                        hash = hash + '&';
                    }
                    // Encode the query before saving it to the hash --
                    // Prevents problems with queries that contain % signs.
                    hash = hash + 'query=' + encodeURIComponent(query);
                }

                if (typeof page !== "undefined") {
                    if (hash.length > 1) {
                        hash = hash + '&';
                    }
                    hash = hash + 'page=' + page;
                }

                if (typeof record !== "undefined") {
                    if (hash.length > 1) {
                        hash = hash + '&';
                    }
                    hash = hash + 'id=' + record;
                }

                return hash;
            },

            /**
             * Convenience function -- Prepares the hash and calls _setHash
             * with the parameters given.
             * If record, query and page are all undefined, the hash is reset.
             * @param params
             */
            saveHash: function (params) {
                var noLoad = params.noLoad,
                    forceLoad = params.forceLoad;

                var hash = this.createHash(params);

                this._setHash({
                    newHash: hash,
                    noLoad: noLoad,
                    forceLoad: forceLoad
                });
            },
            /**
             * Parses the current URL hash and returns an object describing the request it encodes.
             * @returns {string} request.operation - 'init', 'search' or 'view'
             * @returns {string} request.query - Any search query encoded in the hash. (Search mode)
             * @returns {number} request.page - Any page number encoded in the hash. (Search mode)
             * @returns {number} request.id - Any record ID in the hash. (View mode)
             * @returns {Object} request
             */
            parseHash: function () {
                var hash = this.getHash();
                var request = {};

                // If there is no extra info in the hash, we can stop here
                if (hash === '' || hash === '#') {
                    request.operation = 'init';
                    return request;
                }

                // Query string parsing (after removing the leading '#')
                if (hash.indexOf('#') === 0) {
                    hash = hash.substr(1);
                }
                var queryObj = this.parseQuery(hash);

                // Record by ID
                if (typeof queryObj.id !== "undefined") {
                    // By default, assume 'view' until we see evidence in
                    // favour of 'search'
                    request.operation = 'view';
                    request.id = parseInt(queryObj.id);
                }

                // Search string
                if (typeof queryObj.query !== "undefined") {
                    request.operation = 'search';
                    request.query = queryObj.query;

                    if (typeof queryObj.page === "undefined") {
                        // If page no. was not specified in the hash,
                        // default to 1.
                        request.page = 1;
                    }
                }

                // Page number
                if (typeof queryObj.page !== "undefined") {
                    request.page = queryObj.page;
                }

                // Lang ID
                if (typeof queryObj.langid !== "undefined") {
                    request.operation = 'langid';
                }

                // ===============
                // Server commands
                // ===============
                if (typeof queryObj.retrain !== "undefined") {
                    // Retrain language ID model
                    request.operation = 'retrain';
                } else if (typeof queryObj.restart !== "undefined") {
                    request.operation = 'restart';
                } else if (typeof queryObj.shutdown !== "undefined") {
                    request.operation = 'shutdown';
                }


                return request;
            },

            /**
             * Takes a query string, returns a javascript object
             * corresponding to its parameters.
             * If an argument is specified with no value, it is given a
             * default value of 'null'
             * @param str
             */
            parseQuery: function (str) {
                var paramArray = str.split("&");
                var queryObj = {},
                    length = paramArray.length;

                for (var i = 0; i < length; i++) {
                    var param = paramArray[i];

                    // If there was no '=' for this param
                    if (param.indexOf("=") === -1) {
                        queryObj[param] = null;
                        continue;
                    }

                    param = param.split("=");

                    var name = decodeURIComponent(param[0]),
                        value = decodeURIComponent(param[1]);

                    // Name is empty (e.g., = right after an &)
                    if (name === "") {
                        continue;
                    } else {
                        queryObj[name] = value;
                    }
                }

                return queryObj;
            },

            /**
             * Does the big job of actually executing the request specified
             * by the current hash
             */
            hashRequest: function () {
                this.updateTitle();
                var request = this.parseHash();
                if (request.operation === 'init') {
                    Controller.requests.fetchRecord(1);
                } else if (request.operation === 'view') {
                    if (request.id) {
                        Controller.requests.fetchRecord(request.id);
                    }
                    // If the requested record is not the same as the one
                    // specified in the jumpbox, we (probably) changed pages
                    // rather than jumped.  Clear the box.
                    var recordJumpBox = $('#' + this._recordJumpID);
                    if (request.id !== parseInt(recordJumpBox.val())) {
                        recordJumpBox.val('');
                    }
                } else if (request.operation === 'search') {
                    Controller.requests.execSearch(request.query, request.page);
                } else if (request.operation === 'langid') {
                    Controller.requests.execLangID(request.id);
                } else if (request.operation === 'retrain') {
                    Controller.requests.execRetrain();
                } else if (request.operation === 'restart') {
                    Controller.requests.execRestart();
                } else if (request.operation === 'shutdown') {
                    Controller.requests.execShutdown();
                }
            },

            /**
             * Sets the title of the webpage according to the current hash
             * @param request
             */
            updateTitle: function () {
                var request = this.parseHash();
                var prefix = Config.title + " | ";
                if (request.operation === 'init') {
                    document.title = Config.title
                } else if (request.operation === 'view') {
                    document.title = prefix +
                        "#" + request.id
                } else if (request.operation === 'search') {
                    document.title = prefix +
                        '"' + request.query + '", ' +
                        "page " + request.page;
                } else if (request.operation === 'langid') {
                    document.title = prefix +
                        "Language ID: #" + request.id;
                } else if (request.operation === 'retrain') {
                    document.title = prefix +
                        "Retrain";
                } else if (request.operation === 'restart') {
                    document.title = prefix +
                        "Restart";
                } else if (request.operation === 'shutdown') {
                    document.title = prefix +
                        "Shutdown";
                }
            },

            /**
             * Changes the hash to reflect a request for the record with the specified ID.
             * If the new hash is not the same as the previous one, the request will be picked up and executed by the
             * hash change handler.
             * @param recordID
             */
            jumpRecord: function (recordID) {
                recordID = parseInt(recordID);
                if (recordID) {
                    this.saveHash({record: recordID});
                }
            },
            /**
             * Changes the hash to reflect a request for a given search query.
             * If the new hash is not the same as the previous one, the request will be picked up and executed by the
             * hash change handler.
             * @param query
             * @param page - The page number within the search results to fetch
             */
            search: function (query, page) {
                if (typeof page === "undefined") {
                    page = 1;
                }
                if (query !== '') {
                    this.saveHash({
                        query: query,
                        page: page,
                        forceLoad: true     // Always refresh search results.
                    });
                }
            },
            /**
             * Changes the hash to reflect a request for the specified page within the current view.
             * If the new hash is not the same as the previous one, the request will be picked up and executed by the
             * hash change handler.
             * @param pageID
             */
            jumpPage: function (pageID) {
                pageID = parseInt(pageID);
                if (pageID) {
                    var request = this.parseHash();
                    if (request.operation === 'view') {
                        // We are in display mode. Pick out the first record on the requested page and call navJumpRecord.
                        var recordID = (pageID - 1) * this._recordsPerPage + 1;
                        this.jumpRecord(recordID);
                    } else if (request.operation === 'search') {
                        // We are in search mode. Request the new page number using navSearch.
                        this.search(request.query, pageID);
                    }
                }
            },
            /**
             * Binds user input boxes to a given function on submit
             * @param boxID
             * @param submitFunction
             */
            bindBox: function (boxID, submitFunction) {
                var Box = $('#' + boxID);
                var BoxForm = Box.closest("form");
                var BoxButton = BoxForm.find("a.button");
                BoxForm.submit(function (event) {
                    event.preventDefault();
                    submitFunction(Box.val());
                });
                BoxButton.click(function () {
                    BoxForm.submit();
                });
            },
            /**
             * Called on $.ready() by app/init to bind all event handlers on the interface
             */
            initHandlers: function () {
                // Bind handlers:
                //      - Window's hashchange event
                //      - Submit events on the forms containing the input boxes for jumping and searching

                // Also, we use 'this' in _setHash, so all the callbacks need to
                // be bound.

                // Bind the hashchange handler to handle all system navigation
                // We don't call hashRequest directly; _setHash does some extra
                // sanity checks.
                $(window).bind('hashchange', this._setHash.bind(this));

                this.bindBox(this._recordJumpID, this.jumpRecord.bind(this));
                this.bindBox(this._pageJumpID, this.jumpPage.bind(this));
                this.bindBox(this._searchID, this.search.bind(this));
            }
        };
    };
});