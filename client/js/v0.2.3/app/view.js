/**
 * Online Corpus Editor -- View Manager
 * Handles formatted content
 * Zechy Wong
 */

define(function (require) {
    "use strict";

    var $ = require('jquery'),
        Config = require('app/config'),
        Log = require('app/log'),
        Util = require('app/util'),

        Format = require('app/view.format'),
        Alerts = require('app/view.alerts');

    var View = {
        _viewport: $('#' + Config.viewportID),
        _viewportInner: $('#' + Config._viewportInnerID),
        _currentView: null,

        _headerID: Config.headerID,
        _footerID: Config.footerID,
        _scrollOffset: Config.scrollOffset,
        _scrollSpeed: Config.scrollSpeed,
        /**
         * Adds the given html to the top of the current viewport child.
         * @param html
         */
        prepend: function (html) {
            this.getCurrentView().prepend(html);
        },
        /**
         * Adds the given html to the bottom of the current viewport child.
         * @param html
         */
        append: function (html) {
            this.getCurrentView().append(html);
        },
        /**
         * Creates a new viewport child with the given html and marks the old
         * one for deletion.
         * @param html
         */
        replace: function (html, animate) {
            // Clear the yield queue, in case we're still waiting on any
            // functions (mainly controller.edit.initHandlers) we deferred.
            Util.clearGlobalQueue();

            var viewport = this._viewport,
                viewportInner = this._viewportInner;

            var viewOld = this.getCurrentView()
                .removeAttr("id")
                .addClass("view-gc");

            var viewNew = $("<div/>")
                .attr("id", Config._viewID)
                .addClass("view")
                .html(html)
                .appendTo(viewportInner);

            this.setCurrentView(viewNew);
            this.resizeCurrentView();

            if (animate) {

                viewportInner.stop();
                var View = this,
                    toTheLeft = viewNew.position().left;
                viewportInner.animate({
                        left: "-" + toTheLeft
                    },
                    700,
                    function () {
                        viewportInner.css('left', 0);
                        viewportInner.outerWidth(viewNew.outerWidth());

                        $('.view-gc').hide();
                        View.GCByClass('view-gc');
                    });
                /*console.log(viewOld.zIndex(), viewNew.zIndex());
                 var View = this,
                 toTheLeft = viewOld.outerWidth();
                 viewport.css('overflow-x', 'hidden');
                 viewOld.stop(true, true);
                 viewNew.animate(
                 {
                 left: "-" + toTheLeft
                 },
                 {
                 duration: 5000,
                 queue: false,
                 complete: function () {
                 viewOld
                 .hide()
                 .attr("id", Config._viewOldID);
                 viewNew.css('left',0);
                 View.GCByID(viewOld.attr('id'));
                 viewport.css('overflow-x', 'auto');
                 }
                 });*/
            } else {
                viewOld.hide();
                viewNew.show();
                this.GCByClass('view-gc');
            }
        },

        /**
         * Deferred garbage collection on old viewport children -- Done
         * because removing the tag widgets all at one shot incurs a
         * significant performance cost.
         * Currently only targets individual <tr>s within the views.
         * @param cls
         */
        GCByClass: function (cls) {
            this._GC($('.' + cls).get());
        },

        /**
         * Helper function -- GCs <tr>s recursively from an array of DOM
         * elements.
         * In order to allow the tag handlers to be run as quickly as
         * possible, we yield (i.e., stick the next function at the end of
         * the global queue) at every step.
         * @private
         */
        _GC: function (elemArray) {
            if (elemArray.length === 0) {
                return;
            }

            var View = this,
                t0,
                elem = elemArray.shift();

            Util.addToGlobalQueue(function () {
                t0 = performance.now();
                var $target = $(elem);

                var _GCRow = function (rowArray) {
                    if (rowArray.length === 0) {
                        Util.addToGlobalQueue(function () {
                            $target.remove();
                            Log.debugLog({
                                module: 'view',
                                message: "GC took: "
                                + (performance.now() - t0).toFixed(3) + 'ms.'
                            });
                            View._GC(elemArray);
                        });
                        return;
                    }

                    var row = rowArray.shift();

                    Util.addToGlobalQueue(function () {
                        $(row).remove();
                        _GCRow(rowArray);
                    });
                };

                var rowArray = $target.find("tr").get();
                _GCRow(rowArray);
            });
        },

        /**
         * Retrieves the cached $(<div>) with the currently active content
         * (i.e., #[Config._viewID])
         */
        getCurrentView: function () {
            if (this._currentView === null) {
                this._currentView = $('#' + Config._viewID);
            }
            return this._currentView;
        }
        ,

        /**
         * Caches a pointer to the currently active view
         * @param $elem
         */
        setCurrentView: function ($elem) {
            this._currentView = $elem;
            return $elem;
        }
        ,

        /**
         * Resizes the current view to match the current size of the viewport.
         */
        resizeCurrentView: function () {
            var view = this.getCurrentView(),
                viewportWidth = this._viewport.outerWidth();
            view.outerWidth(viewportWidth);
        },

        /**
         * Scrolls a given element into view.
         *   scrollOffset: The target final position for the element (e.g., 0.4 -> 40% of the way down)
         * @param params
         */
        scrollTo: function (params) {
            var element = $(params.element);
            var scrollOffset = params.scrollOffset || this._scrollOffset;
            var scrollSpeed = params.scrollSpeed || Config.scrollSpeed;

            var elementTop = element.offset().top;
            var elementBottom = elementTop + element.height();
            var viewCurrent = $(window).scrollTop();
            var viewTop = viewCurrent + $('#' + this._headerID).height();
            var viewBottom = viewCurrent + $(window).innerHeight() - $('#' + this._footerID).height();

            var scrollTarget = elementTop - (viewBottom - viewTop) * scrollOffset;

            $('html, body').animate(
                {
                    scrollTop: scrollTarget
                },
                scrollSpeed
            );
        },
        /**
         * Convenience function -- Scrolls to the top of the page.
         */
        scrollToTop: function () {
            $("html, body").animate({
                scrollTop: 0
            }, Config.scrollSpeed);
        }
    };

// Load submodules
    Format(View);
    Alerts(View);

    Log.debugLog("  [view]: Module ready.");

    return View;
})
;