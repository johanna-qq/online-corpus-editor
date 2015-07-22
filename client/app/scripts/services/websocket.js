/**
 * Online Corpus Editor -- WebSockets
 * (using angular-websocket: https://github.com/gdi2290/angular-websocket)
 */

(function () {
    "use strict";

    angular.module("oce").factory('$ocewebsocket', function (appConfig, pako, $websocket, $q) {

        /**
         * Handle zlib compression + base64 decoding
         * http://stackoverflow.com/questions/4507316/zlib-decompression-client-side
         */
        function b64Inflate(b64Input) {
            var strData = atob(b64Input);
            var charData = strData.split('').map(function (x) {
                return x.charCodeAt(0);
            });
            var binData = new Uint8Array(charData);
            var data = pako.inflate(binData);
            return String.fromCharCode.apply(null, new Uint16Array(data));
        }

        // Open the websocket connection
        var socket = $websocket("ws://" + appConfig.wsHost + ":" + appConfig.wsPort);
        var promiseQueue = [];

        // DEBUG: Raw message logs
        var rawInputQueue = [];
        var rawResolvedQueue = [];

        socket.onMessage(function (message) {
            var incomingData = JSON.parse(b64Inflate(message.data));

            // DEBUG: Push pretty-printed version to rawInputQueue
            rawInputQueue.push(JSON.stringify(incomingData, null, 2));

            // Search through the promise queue and resolve the first one
            // that matches
            var promise = null;
            for (var i = 0; i < promiseQueue.length; i++) {
                if (incomingData.command === promiseQueue[i][0]) {
                    promise = promiseQueue[i][1];
                    promiseQueue.splice(i, 1);
                    break;
                }
            }
            if (promise !== null) {
                rawResolvedQueue.push(JSON.stringify(incomingData, null, 2));
                promise.resolve(incomingData);
            }

            // TODO: Else -- There was no associated promise (i.e., the message was
            // unsolicited).  Do something about it.
        });

        function rejectPromises(reason) {
            for (var i = 0; i < promiseQueue.length; i++) {
                promiseQueue[i][1].reject(reason);
            }
            promiseQueue = [];
        }

        socket.onError(function () {
            rejectPromises('WebSocket error.');
        });

        socket.onClose(function () {
            rejectPromises('WebSocket closed.');
        });

        // 'requestOb' should at least have its command specified.
        function request(requestObj) {
            var deferred = $q.defer();
            var command = requestObj.command;
            promiseQueue.push([command, deferred]);
            socket.send(JSON.stringify(requestObj));
            return deferred.promise;
        }

        var methods = {
            rawInputQueue: rawInputQueue,
            rawResolvedQueue: rawResolvedQueue,
            request: request
        };

        return methods;
    });
})();