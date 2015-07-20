/**
 * Online Corpus Editor -- WebSockets
 * (using angular-websocket: https://github.com/gdi2290/angular-websocket)
 */

(function () {
    "use strict";

    angular.module("oce").factory('wsHandler', function (appConfig, $websocket, $window, $q) {

        /**
         * Handle zlib compression + base64 decoding
         * http://stackoverflow.com/questions/4507316/zlib-decompression-client-side
         */
        function b64Inflate(b64Input) {
            //var test = 'eJxNT01PwzAM/StVzhwAwQ67TXRik4BVqwQHxMFNrC4sjSvHmaim/XeSlrGdbD/7ffioNHUdeKPmhepQQN0UykCq8+KohARc6u4fbmePs7u0EmhDAj7VE/XRQYkOxZLPrIqpZOpzu+A2duilFo5aImMGJ8Y78pCnZdegMWjqxXpkmG/UYg82wFnvbbnNJREacFf4KzgYJZ5JKgoBQ7AHPANwPS1/bJCUw6YvLgk3Tfb6P+mR7eVm43GLLplNIqshrTUx53R//sT9jhy1Q/GS7DNU2qApcsAKWKx2I/Vjt/a1lTjK0H6fTKb43gBbr75Op1/NZX1W';
            var pako = $window.pako;
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

        // DEBUG
        var rawInputQueue = [];
        var resolvedQueue = [];

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
                setTimeout(function () {
                    var result = JSON.stringify(incomingData, null, 2);
                    resolvedQueue.push(result);
                    promise.resolve(incomingData);
                }, 1);
            }

            // Else: There was no associated promise (i.e., the message was
            // unsolicited).  Do something about it.
        });

        function getMeta() {
            var deferred = $q.defer();
            promiseQueue.push(['meta', deferred]);
            socket.send(JSON.stringify({command: 'meta'}));
            return deferred.promise;
        }

        function getFirst() {
            var deferred = $q.defer();
            promiseQueue.push(['view', deferred]);
            socket.send(JSON.stringify({
                command: 'view',
                start: 1,
                end: 100,
                record: 1
            }));
            return deferred.promise;
        }

        var methods = {
            rawInputQueue: rawInputQueue,
            resolvedQueue: resolvedQueue,
            getMeta: getMeta,
            getFirst: getFirst
        };

        return methods;
    });
})();