/**
 * Online Corpus Editor -- Utilities
 * Provides general utility functions for the app.
 * Zechy Wong
 */

define(["jquery", "app/config", "app/log"], function ($, Config, Log) {
    "use strict";

    Log.debugLog("  [util]: Module ready.");


    return {

        // === Global task queue ===
        // Uses the jQuery queue api to queue intensive stuff up
        _queue: $(document),

        // Generic queueing functions
        addToElementQueue: function (element, fn, context, time) {
            var taskQueue = element;
            taskQueue
                .delay(time || 0)
                .queue(function () {
                    fn.call(context || window);
                    taskQueue.dequeue();
                });
        },

        clearElementQueue: function (element) {
            element.clearQueue();
        },

        // Convenience function to queue things up on this._queue
        addToGlobalQueue: function (fn, context, time) {
            /*Log.debugLog({
                module: 'util',
                message: "Function added to global queue."
            });*/
            this.addToElementQueue(this._queue, fn, context, time);
        },

        clearGlobalQueue: function () {
            var length = this._queue.queue().length;
            this._queue.clearQueue();
            Log.debugLog({
                module: 'util',
                message: "Global queue cleared. Queue length was: " + length + "."
            });
        },

        /**
         * Use the (global) timer queue to stagger execution of some function
         * over a set of jQuery elements.
         * @param fn - The function to run over the elements. Each (jQuery) element will be bound as 'this' in turn.
         * @param elems - The elements to iterate over.
         * @param perRun - How many function calls to execute per run.
         * @param whenDone - Run when all the elements have been iterated over. Will *not* have anything bound to it.
         */
        staggerExec: function (fn, elems, perRun, whenDone) {
            var self = this,
                thisRun = elems.slice(0, perRun);
            elems = elems.slice(perRun);
            thisRun.each(function () {
                fn.call($(this));
            });
            if (elems.length) {
                this.addToGlobalQueue(function () {
                    self.staggerExec(fn, elems, perRun, whenDone);
                });
            } else if (typeof whenDone == "function") {
                whenDone();
            }
        },

        // === Formatting ===
        /**
         * Gets the approximate height of a hidden jQuery element (since
         * getting an accurate height value requires that the element be
         * displayed)
         */
        getApproxHeight: function ($elem) {
            var clone = $elem.clone().css({
                'position': 'absolute',
                'left': '-' + $elem.width() + 'px'
            }).hide();
            var height = clone.appendTo('body').show().outerHeight();
            clone.remove();

            return height;
        },

        /**
         * Converts <br>s to newlines in the given string.
         * @param str
         * @returns {string}
         */
        br2nl: function (str) {
            return str.replace(/<br>/g, '\n');
        },

        /**
         * Converts newlines to <br>s in the given string.
         * @param str
         * @returns {string}
         */
        nl2br: function (str) {
            return str.replace(/\n/g, '<br>');
        },

        /**
         * Escapes html tags in a given string.
         * @param str
         * @param keepBR - If true, leaves <br>s intact.
         */
        escapeHTML: function (str, keepBR) {
            if (keepBR) {
                str = str
                    .replace(/<(?!br>)/g, '&lt;')
                    .replace(/(?!<br)(.{3})>/g, '$1&gt;');
            } else {
                str = str
                    .replace(/</g, '&lt;')
                    .replace(/>/g, '$1&gt;');
            }
            return str;
        }
    }
});