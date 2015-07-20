/**
 * Online Corpus Editor -- Main Controller
 */

(function () {
    "use strict";

    angular.module("oce").controller("mainController",
        ['$scope', '$window', function ($scope, $window) {

            var test = '';
            var pako = $window.pako;
            // Handle zlib compression + base64 encoding
            // http://stackoverflow.com/questions/4507316/zlib-decompression-client-side
            var strData = atob(test);
            var charData = strData.split('').map(function (x) {
                return x.charCodeAt(0);
            });
            var binData = new Uint8Array(charData);
            var data = pako.inflate(binData);

            // Recreate message event-like object; Other attributes can
            // be handled here in the future.
            $scope.testdata = String.fromCharCode.apply(null, new Uint16Array(data));
        }]);
})();
