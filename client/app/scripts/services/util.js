/**
 * Online Corpus Editor -- Utilities
 */

(function () {
    "use strict";

    angular.module("oce").factory("util", function () {

        var methods = {};

        methods.br2nl = function (str) {
            return str.replace(/<br>/g, '\n');
        };

        methods.nl2br = function (str) {
            return str.replace(/\n/g, '<br>');
        };

        methods.escapeHTML = function (str, keepBR) {
            if (keepBR) {
                str = str
                    .replace(/<(?!br>)/g, '&lt;')
                    .replace(/(?!<br)(.{3})>/g, '$1&gt;');
            } else {
                str = str
                    .replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;');
            }
            return str;
        };

        methods.unescapeHTML = function (str) {
            str = str
                .replace(/&lt;/g, '<')
                .replace(/&gt;/g, '>');
            return str;
        };

        // From Foundation 5:
        // Description:
        //    Executes a function when it stops being invoked for n seconds
        //    Modified version of _.debounce() http://underscorejs.org
        //
        // Arguments:
        //    Func (Function): Function to be debounced.
        //
        //    Delay (Integer): Function execution threshold in milliseconds.
        //
        //    Immediate (Bool): Whether the function should be called at the beginning
        //    of the delay instead of the end. Default is false.
        //
        // Returns:
        //    Lazy_function (Function): Function with debouncing applied.
        methods.debounce = function (func, delay, immediate) {
            var timeout, result;
            return function () {
                var context = this, args = arguments;
                var later = function () {
                    timeout = null;
                    if (!immediate) {
                        result = func.apply(context, args);
                    }
                };
                var callNow = immediate && !timeout;
                clearTimeout(timeout);
                timeout = setTimeout(later, delay);
                if (callNow) {
                    result = func.apply(context, args);
                }
                return result;
            };
        };

        return methods;
    });
})();
