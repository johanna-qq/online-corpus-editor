/**
 * Online Corpus Editor -- Main Controller
 */

(function () {
    "use strict";

    angular.module("oce").controller("mainController", function ($scope, wsHandler) {
        $scope.wsHandler = wsHandler;
    });
})();
