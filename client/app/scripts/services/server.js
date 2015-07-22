/**
 * Online Corpus Editor -- Server Controller
 */

(function () {
    "use strict";

    // Server requests
    // request[Something]: Gets data from the server
    // exec[Something]: Executes some command server-side
    angular.module("oce").factory("serverManager", function ($ocewebsocket) {

        var methods = {};

        methods.requestMeta = function () {
            var request = {command: 'meta'};
            return $ocewebsocket.request(request);
        };

        methods.requestRecords = function (start, end, record) {
            if (typeof record !== "number") {
                record = start;
            }
            var request = {
                command: 'view',
                start: start,
                end: end,
                record: record
            };
            return $ocewebsocket.request(request);
        };

        return methods;
    });
})();
