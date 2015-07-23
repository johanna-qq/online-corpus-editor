/**
 * Online Corpus Editor -- User Interaction (submodule)
 * Pager
 * Zechy Wong
 * Last Modified: 24 June 2015
 *
 * N.B. Submodules return a function that accept the main module as a
 * parameter for initialisation; the function will extend the main module
 * when called.
 */

define(function (require) {
    "use strict";

    var $ = require('jquery'),
        Config = require('app/config'),
        Log = require('app/log'),
        Util = require('app/util');

    Log.debugLog("    [controller.pager]: Submodule ready.");

    return function (Controller) {
        Controller.pager = {

            /**
             * Legacy
             * @param params
             */
            pagerUpdate: function (params) {
                var pager = $('#pager');

                var mode = params.mode,
                    numPages = params.numPages,
                    currentPage = params.currentPage,
                    totalRecords = params.totalRecords, // Should be deprecated
                    query = params.query;

                var pagesToShow = this.pageList(1, currentPage, numPages);

                // Pre-processing for top-bar buttons
                var prevLink, nextLink;
                if (mode === 'view') {
                    prevLink = (currentPage - 2) * Config.recordsPerPage + 1;
                    if (prevLink < 1) {
                        prevLink = 1;
                    }
                    prevLink = Controller.nav.createHash({
                        record: prevLink
                    });

                    nextLink = (currentPage) * Config.recordsPerPage + 1;

                    if (nextLink > totalRecords) {
                        nextLink = totalRecords;
                    }
                    nextLink = Controller.nav.createHash({
                        record: nextLink
                    });
                } else if (mode === 'search') {
                    prevLink = currentPage - 1;
                    if (prevLink < 1) {
                        prevLink = 1;
                    }
                    prevLink = Controller.nav.createHash({
                        query: query,
                        page: prevLink
                    });

                    nextLink = currentPage + 1;
                    if (nextLink > numPages) {
                        nextLink = numPages;
                    }
                    nextLink = Controller.nav.createHash({
                        query: query,
                        page: nextLink
                    });
                }

                // ============
                // Create pager
                // ============
                var newPager = $("<ul/>")
                    .attr('id', 'pagerbuttons')
                    .addClass('pagination');

                var prevButton = $("<a>&laquo;</a>");
                var prevButtonLi = $('<li class="arrow"></li>')
                    .append(prevButton)
                    .appendTo(newPager);

                if (currentPage === pagesToShow[0]) {
                    prevButtonLi.addClass('unavailable');
                } else {
                    prevButton.attr('href', prevLink);
                }


                for (var i = 0; i < pagesToShow.length; i++) {
                    var page = pagesToShow[i];

                    // Separator
                    if (page === 0) {
                        $('<li class="unavailable"></li>')
                            .append($("<a>&hellip;</a>"))
                            .appendTo(newPager);
                        continue;
                    }

                    var pageLink;
                    if (mode === 'view') {
                        pageLink = Controller.nav.createHash({
                            record: (page - 1) * Config.recordsPerPage + 1
                        });
                    } else if (mode === 'search') {
                        pageLink = Controller.nav.createHash({
                            query: query,
                            page: page
                        });
                    }

                    var pageLi = $("<li/>");
                    if (page === currentPage) {
                        pageLi.addClass('current');
                    }

                    pageLi.append(
                        $("<a/>").attr('href', pageLink).html(page)
                    ).appendTo(newPager);
                }

                if (currentPage === pagesToShow[pagesToShow.length - 1]) {
                    newPager.append("<li class='arrow" +
                        " unavailable'><a>&raquo;</a></li>");
                } else {
                    newPager.append("<li class='arrow'><a href='" + nextLink +
                        "'>&raquo;</a></li>");
                }

                // ============

                // Update top-bar prev/next buttons
                $('#btntop_prev').prop('href', prevLink);
                $('#btntop_next').prop('href', nextLink);

                // Used to control the width of the pager
                var pagerParent = pager.parent();

                // Show it if hidden
                if (pager.css('display') === 'none') {
                    pagerParent.css("width", this.pagerWidth(pagesToShow));
                    pager.empty().append(newPager);

                    // Also give the main container enough margin-bottom to
                    // prevent overlapping
                    $('#' + Config.mainID).css({
                        'margin-bottom': Util.getApproxHeight(pager) + 15
                    });

                    pager.slideDown(Config.alertSpeed);
                } else {
                    // Animate paginator; update content before/after depending on new width
                    var newWidth = this.pagerWidth(pagesToShow);
                    if (parseInt(pagerParent.css("width")) < newWidth) {
                        pagerParent.animate({
                                width: newWidth
                            },
                            Config.alertSpeed,
                            function () {
                                pager.empty().append(newPager);
                            });
                    } else {
                        pager.empty().append(newPager);
                        pagerParent.animate({
                                width: newWidth
                            },
                            Config.alertSpeed);
                    }
                }
            },

            /**
             * Returns an array of page numbers to show.  Separators are
             * marked by a value of 0
             * @param first
             * @param current
             * @param last
             */
            pageList: function (first, current, last) {
                var pagesToShow = [];

                // Always show the link to page one
                pagesToShow.push(1);

                if (first == last) {
                    // Our job is done
                    return pagesToShow;
                }

                if (current >= 5) {
                    // Also show the separator, since the next button after 1 is 3
                    pagesToShow.push(0);
                }

                // Put buttons to pages near the current one
                for (var i = current - Config.pageBuffer; i <= current + Config.pageBuffer; i++) {
                    if (i <= 1 || i >= last) {
                        continue;
                    }
                    pagesToShow.push(i);
                }

                // If the last page is further away, put in separators etc.
                if (last - current - Config.pageBuffer > 1) {
                    pagesToShow.push(0);
                }

                // Push last page
                pagesToShow.push(last);

                return pagesToShow;
            },

            /**
             * Calculates an appropriate max-width for the pager bar based
             * on the number of digits in the page numbers to show.
             * @param pagesToShow
             */
            pagerWidth: function (pagesToShow) {
                var width = 0;
                for (var i = 0; i < pagesToShow.length; i++) {
                    if (pagesToShow[i] === 0) {
                        // Separator: Ellipsis mark is 34px, margins are 10px
                        width += 34 + 10;
                    } else {
                        // Actual number: Each digit is 8px, 20px padding, 10px margins
                        var digits = pagesToShow[i].toString().length;
                        width += 10 + 20 + digits * 8;
                    }
                }
                // Arrows: Arrows are 28px, margins 10px
                width += (28 + 10) * 2;
                // Padding
                width += 10;
                return width;
            }
        };
    }
});