/**
 * Online Corpus Editor -- View Manager (submodule)
 * Alerts and Notifications
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
    require('noty.bootstrap');

    Log.debugLog("    [view.alerts]: Submodule ready.");

    return function (View) {

        View.alerts = {
            _alertSpeed: Config.alertSpeed || 400,
            _alertDuration: Config.alertDuration || 800,
            _alertContainer: $('#' + Config._alertContainerID),

            _searchNote: null,
            _saveNote: null,

            _connectingID: 'alert-init',
            _reconnectID: 'alert-reconnect',
            _errorID: 'alert-error',


            /**
             * 'Connecting' notification
             * @param complete - Function to call when the animation is done.
             */
            showConnecting: function (params) {
                if (typeof params === "undefined") {
                    params = {}
                }
                var complete = params.complete || null

                // Prepare alert
                var alertDiv = $("<div/>")
                    .addClass("alert-box info radius")
                    .attr({
                        'data-alert': '',
                        'id': this._connectingID
                    })
                    .text("Connecting to server...")
                    .hide();

                // Clear out alertContainer
                this.removeAlerts();

                alertDiv.prependTo(this._alertContainer);
                if (typeof complete === "function") {
                    alertDiv.slideDown(this._alertSpeed, complete);
                } else {
                    alertDiv.slideDown(this._alertSpeed);
                }
            },

            removeConnecting: function () {
                this.removeAlert(this._connectingID);
            },

            /**
             * Websocket closed/errored out - Show the reconnect button.
             * @param wasError - If true, the alert text will attribute the
             * disconnection to an error.
             */
            showReconnect: function (wasError) {
                // If the alert is already up, don't do anything
                if ($('#' + this._reconnectID).length) {
                    return;
                }

                var txt;
                if (wasError) {
                    txt = "WebSocket connection error ";
                } else {
                    txt = "WebSocket connection closed ";
                }

                var wsParams = WS.getParams();
                txt += "(ws://" + wsParams.host + ":" + wsParams.port + ") - Changes will <strong>not</strong> be saved. ";

                // Show the info alert
                var alertDiv = $("<div/>")
                    .addClass("alert-box info radius hidden")
                    .attr({
                        'data-alert': '',
                        'id': this._reconnectID
                    })
                    .html(txt)
                    .hide();

                var alertButton = $("<a/>").text('Reconnect');
                alertDiv.append(alertButton);

                // Clear out alertContainer
                this.removeAlerts();

                alertDiv.prependTo(this._alertContainer);
                alertDiv.slideDown(this._alertSpeed);
                View.scrollToTop();

                // Also remove all notifications
                $.noty.closeAll();

                // On click, remove alert and attempt reconnect
                var Alerts = this;
                alertButton.click(function (event) {
                    // Context change -- 'this' is the alertButton.
                    event.preventDefault();
                    alertDiv.slideUp(Alerts._alertSpeed, function () {
                        this.remove();
                    });

                    // Let the user know we're attempting the reconnection.
                    Alerts.showConnecting({
                        // The callback needs to be bound, since we use 'this'
                        // in WS.reInitSocket()
                        complete: WS.reInitSocket.bind(WS)
                    });
                });
            },

            removeReconnect: function () {
                this.removeAlert(this._reconnectID);
            },

            /**
             * Our loader broke :(
             */
            showLoaderError: function (err) {

                Log.debugLog(err);

                var alertDiv = $("<div/>")
                    .addClass("alert-box info radius hidden")
                    .attr({
                        'data-alert': '',
                        'id': this._errorID
                    })
                    .html("Whoops, looks like something important broke :(" +
                    " &nbsp;")
                    .hide();

                var alertButton = $("<a/>").text('Click to try reloading the' +
                    ' page.');
                alertDiv.append(alertButton);

                // Clear out alertContainer
                this.removeAlerts();

                alertDiv.prependTo(this._alertContainer);
                alertDiv.slideDown(this._alertSpeed);
                View.scrollToTop();

                // On click, remove alert and attempt reconnect
                var Alerts = this;
                alertButton.click(function (event) {
                    // Context change -- 'this' is the alertButton.
                    event.preventDefault();
                    alertDiv.slideUp(Alerts._alertSpeed, function () {
                        this.remove();
                    });

                    // Let's try that one again
                    location.reload(true);
                });
            },

            /**
             * Shows arbitrary error messages in the alert area
             * @param msg
             */
            showError: function (msg) {
                var alertDiv = $("<div/>")
                    .addClass("alert-box error radius")
                    .attr({
                        'data-alert': '',
                        'id': 'alert-custom-error'
                    })
                    .html(msg)
                    .hide();

                // Clear out alertContainer
                this.removeAlerts();

                alertDiv.prependTo(this._alertContainer);
                alertDiv.slideDown(this._alertSpeed);
            },

            removeError: function () {
                this.removeAlert('alert-custom-error');
            },

            /**
             * Shows arbitrary info messages in the alert area
             */
            showInfo: function (msg) {
                var alertDiv = $("<div/>")
                    .addClass("alert-box info radius")
                    .attr({
                        'data-alert': '',
                        'id': 'alert-custom-info'
                    })
                    .html(msg)
                    .hide();

                // Clear out alertContainer
                this.removeAlerts();

                alertDiv.prependTo(this._alertContainer);
                alertDiv.slideDown(this._alertSpeed);
            },

            /**
             * Removes a specific alert by ID
             * @param alertID
             */
            removeAlert: function (alertID) {
                this._alertContainer.find('#' + alertID)
                    .slideUp(this._alertSpeed, function () {
                        this.remove();
                    });
            },
            /**
             * Removes all <div>s from the alert container
             */
            removeAlerts: function () {
                this._alertContainer.find("div")
                    .slideUp(this._alertSpeed, function () {
                        this.remove();
                    });
            },

            /**
             * Hide a given alert div (by slidingUp)
             */
            hideByID: function (alertID) {
                var checkAlert = $('#' + alertID);
                if (checkAlert.length) {
                    checkAlert.slideUp(this._alertSpeed, function () {
                        this.remove();
                    });
                }
            },

            /**
             * Controls the save pop-up notification
             * @param wasSuccess
             */
            notifySave: function (wasSuccess) {
                // Set the notification text
                var type, text, timeout;

                if (typeof wasSuccess === "undefined") {
                    type = 'notification';
                    text = 'Saving...';
                    timeout = false;    // No auto timeout
                } else if (wasSuccess === true) {
                    type = 'success';
                    text = 'Saved.';
                    timeout = this._alertDuration;
                } else if (wasSuccess === false) {
                    type = 'error';
                    text = "There was a problem saving your changes to the" +
                        " server; please try again later.";
                    timeout = this._alertDuration * 2;
                }

                // Create the notification if it doesn't exist
                if (this._saveNote === null) {
                    var Alerts = this;
                    this._saveNote = noty({
                        layout: 'topLeft',
                        theme: 'relax',
                        type: type,
                        text: text,
                        timeout: timeout,
                        animation: {
                            open: {height: 'toggle'},
                            close: {height: 'toggle'},
                            easing: 'swing',
                            speed: this._alertSpeed
                        },
                        callback: {
                            onClose: function () {
                                // Context change -- Use variable instead of 'this' (which is now noty).
                                Alerts._saveNote = null;
                            }
                        }
                    });
                } else {
                    this._saveNote.setType(type);
                    this._saveNote.setText(text);
                    this._saveNote.setTimeout(timeout);
                }
            },

            /**
             * Controls the search pop-up notification
             * @param wasSuccess - If true, close the notification normally
             */
            notifySearch: function (wasSuccess, params) {
                if (typeof params == "undefined") {
                    params = {};
                }

                var type, text, timeout;
                if (typeof wasSuccess === "undefined" || wasSuccess === null) {
                    type = 'information';
                    text = "Searching...";
                    timeout = false;    // No auto timeout
                } else if (wasSuccess === true) {
                    // Close the notification and return
                    if (this._searchNote !== null) {
                        console.log('Closing search notification');
                        this._searchNote.close();
                    }
                    return
                } else if (wasSuccess === false) {
                    // Whoops
                    type = 'error';
                    text = "There was a problem with the search query;" +
                        " please edit it and try again.";
                    timeout = this._alertDuration * 2;
                }

                if (this._searchNote === null) {
                    var Alert = this;
                    var notyOptions = {
                        layout: 'topLeft',
                        theme: 'relax',
                        type: type,
                        text: text,
                        timeout: timeout,
                        animation: {
                            open: {height: 'toggle'},
                            close: {height: 'toggle'},
                            easing: 'swing',
                            speed: this._alertSpeed
                        },
                        callback: {
                            onClose: function () {
                                // Context change -- 'this' is now noty.
                                Alert._searchNote = null;
                            }
                        }
                    };
                    if (typeof params.afterShow === "function") {
                        notyOptions.callback.afterShow = params.afterShow;
                    }

                    this._searchNote = noty(notyOptions);
                } else {
                    this._searchNote.setType(type);
                    this._searchNote.setText(text);
                    if (timeout) {
                        this._searchNote.setTimeout(timeout);
                    }
                    // Since it *is* showing, just execute the function
                    if (typeof params.afterShow === "function") {
                        params.afterShow();
                    }
                }
            }
        };
    }
});