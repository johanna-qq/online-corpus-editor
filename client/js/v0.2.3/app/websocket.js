/**
 * Online Corpus Editor -- WebSocket Interface
 * Zechy Wong
 * Last modified: 24 June 2015
 */

define(function (require) {
    "use strict";

    var Config = require('app/config'),
        Log = require('app/log'),
        Util = require('app/util'),

        Pako = require('pako/pako');

    Log.debugLog("  [websocket]: Module ready.");

    return {
        _socket: null,
        _host: null,
        _port: null,
        _up: false,

        /**
         * Message handlers
         */
        _onClose: null,
        _onError: null,
        _onMessage: null,
        _onOpen: null,

        /**
         * Connects to the specified WebSocket server and sets up messaging
         * handlers.
         */
        initSocket: function (params) {
            if (typeof params == "undefined") {
                params = {};
            }
            var host = params.host || this._host || Config.host;
            var port = params.port || this._port || Config.port;
            var onClose = params.onClose || this._onClose;
            var onError = params.onError || this._onError;
            var onMessage = params.onMessage || this._onMessage;
            var onOpen = params.onOpen || this._onOpen;

            var socket = new WebSocket("ws://" + host + ":" + port);

            // Context change in the following anonymous functions
            var WS = this;
            socket.onclose = function () {
                WS._up = false;
                onClose();
            };

            socket.onerror = function () {
                WS._up = false;
                onError();
            };

            socket.onopen = function () {
                WS._up = true;
                onOpen();
            };

            socket.onmessage = function (msg) {
                // Handle zlib compression + base64 encoding
                // http://stackoverflow.com/questions/4507316/zlib-decompression-client-side
                var strData = atob(msg.data);
                var charData = strData.split('').map(function (x) {
                    return x.charCodeAt(0);
                });
                var binData = new Uint8Array(charData);
                var data = Pako.inflate(binData);

                // Recreate message event-like object; Other attributes can
                // be handled here in the future.
                msg = {};
                msg.data = String.fromCharCode.apply(null, new Uint16Array(data));

                msg = JSON.parse(msg.data);

                onMessage(msg);
            };


            this._host = host;
            this._port = port;
            this._onClose = onClose;
            this._onError = onError;
            this._onMessage = onMessage;
            this._onOpen = onOpen;
            this._socket = socket;
        },

        /**
         * Sends a request array (prepared by the controller.requests module)
         * to the server as a JSON string.  Clears the global timer queue as
         * well.
         * @param requestArray
         */
        sendRequest: function (requestArray) {
            Log.debugLog({
                module: 'websocket',
                message: "Sending request to server:"
            });
            Log.debugLog(requestArray);
            // If the socket is down, just ask for a re-init (which should
            // reload the currently requested view.)
            if (!this.isUp()) {
                this.reInitSocket();
                return;
            }

            this._socket.send(JSON.stringify(requestArray));
        },

        /**
         * For clarity; calling initSocket without params will use the
         * stored ones by default.
         */
        reInitSocket: function () {
            Log.debugLog({
                module: 'websocket',
                message: 'Reinitialising websocket.'
            });
            this._socket = null;
            this.initSocket();
        },

        getParams: function () {
            return {
                host: this._host,
                port: this._port
            }
        },

        isUp: function () {
            return this._up;
        }
    }
});