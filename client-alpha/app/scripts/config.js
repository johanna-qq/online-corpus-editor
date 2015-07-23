/**
 * Online Corpus Editor -- Configuration
 */

(function () {
    "use strict";

    var appConfig = {};

    // === User Configurable ===

    // Websocket server details
    appConfig.wsHost = location.hostname || "localhost";
    appConfig.wsPort = 8081;

    angular.module("oce").value("appConfig", appConfig);

})();