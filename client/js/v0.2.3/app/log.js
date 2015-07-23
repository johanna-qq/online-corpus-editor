/**
 * Online Corpus Editor -- Logging
 * Zechy Wong
 * Last Modified: 22 June 2015
 */

define(["app/config"], function (Config) {
    "use strict";

    return {
        _logTarget: 'console',
        _moduleColour: 'blue',

        /**
         * Logs the given message if 'debug' is set in Config
         * @param params
         */
        debugLog: function (params) {
            if (Config.debug) {
                this.writeLog(params);
            }
        },

        /**
         * Writes a given message to the current log
         * @param params
         */
        writeLog: function (params) {
            if (this._logTarget === 'console') {
                if (typeof params === "object" && typeof params.module !== "undefined") {
                    console.log("[%c%s%c]: %s",
                        "color:" + this._moduleColour,
                        params.module,
                        "color:inherit",
                        params.message
                    );
                } else {
                    console.log(params);
                }
            }
        }
    };
});
