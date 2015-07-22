/**
 * Online Corpus Editor -- Main module
 */

(function () {
    "use strict";

    angular.module("oce", ["angularGrid", "angular-websocket"])
        // Allow libraries to be injected
        .factory('jQuery', function ($window) {
            return $window.jQuery;
        })
        .factory('pako', function ($window) {
            return $window.pako;
        });

    // Routes will go in here.
})();

