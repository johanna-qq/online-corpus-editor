/**
 * Online Corpus Editor -- Loader
 * Loads the various system components, popping notifications along the way.
 * Zechy Wong
 */

requirejs(["jquery", "app/config", "app/log"], function ($, Config, Log) {
    "use strict";

    var t0 = performance.now();

    Log.debugLog("[init]: Initialising main UI...");

    // === jQuery Options ===
    // Lower the effect timer interval so we don't hit the CPU so hard.
    $.fx.interval = 20;

    // === Initialise Data Containers ===
    var viewport = $('#' + Config.viewportID)
            .addClass('viewport'),

        titleContainer = $("<div/>")
            .attr("id", Config._titleContainerID)
            .appendTo(viewport),

        alertContainer = $("<div/>")
            .attr("id", Config._alertContainerID)
            .appendTo(viewport),

        viewportInner = $("<div/>")
            .attr("id", Config._viewportInnerID)
            .addClass('viewportInner')
            .appendTo(viewport),

        view = $("<div/>")
            .attr('id', Config._viewID)
            .addClass('left')
            .css('width', '100%')
            .appendTo(viewportInner);

    // $(document) is going to own our loader animation queue.
    // All the animations run in sequence; dequeuing only happens after the
    // current animation is done.
    var loadQueue = $(document);

    // === Load Corpus Title ===
    var title = $("<h2/>")
        .text(Config.title)
        .hide()
        .appendTo(titleContainer);
    document.title = Config.title;
    loadQueue.queue(function () {
        title.slideDown(Config.alertSpeed, function () {
            loadQueue.dequeue();
        });
    });

    // === 'Loading' Notification in viewportChild ===
    var loadingDiv = $("<div/>")
        .attr('id', 'loading-div')
        .hide()
        .appendTo(view);
    $("<p/>").text("Loading interface...").appendTo(loadingDiv);
    loadQueue.queue(function () {
        loadingDiv.slideDown(Config.alertSpeed, function () {
            loadQueue.dequeue();
        });
    });

    // === Load Foundation and Topbar (modded) ===
    // Foundation.js modded to defer adding class 'f-topbar-fixed' to body; we
    // should add it when we're done animating the topbar.
    loadQueue.queue(function () {
        requirejs(["foundation_mod", "jquery-ui"], function () {
            $(document).foundation();

            var topbar = $('#' + Config.headerID);
            $('body').addClass('f-topbar-fixed',
                Config.alertSpeed,
                function () {
                    loadQueue.dequeue();
                }
            );
            topbar.parent().slideDown(Config.alertSpeed);
        });
    });

    // === Load view/alerts handler, 'Connecting' alert ===
    loadQueue.queue(function () {
        requirejs(["app/view"], function (View) {
            // Module sub-dependencies: util, websocket

            // Build the alert and put it in the alert container
            View.alerts.showConnecting({
                complete: function () {
                    loadQueue.dequeue();
                }
            });

            // And get rid of loadingDiv at the same time
            // (It should still be in scope here)
            loadingDiv.slideUp(Config.alertSpeed, function () {
                this.remove();
            });
        });
    });

    // === UI handlers ===
    loadQueue.queue(function () {
        requirejs(["app/controller", "app/view", "foundation_mod"], function (Controller, View) {

            Log.debugLog('[init]: Initialising UI handlers...');

            Controller.nav.initHandlers();

            /*$(window).resize(
                // Don't fire this too often
                Foundation.utils.throttle(function () {
                    Log.debugLog("Fired resize func.");
                    // TODO: Move this under View.
                    View.resizeCurrentView();
                    //$('body').css('padding-top', Util.getApproxHeight($('#' +
                    // Config.headerID).parent()));
                }, 2000)
            );*/

            loadQueue.dequeue();
            // TODO: Also, have View do regular GC-ing
        });
    });

    // === Open the WS connection and handoff to the main app ===
    loadQueue.queue(function () {
        requirejs(
            ["app/websocket", "app/view", "app/content", "app/controller"],
            function (WS, View, Content, Controller) {

                Log.debugLog("[init]: Initialising WebSocket connection" +
                    " (in background)...");

                // Initialise WebSocket connection (asynchronously)
                WS.initSocket({
                    host: Config.host,
                    port: Config.port,
                    onClose: function () {
                        View.alerts.showReconnect();
                    },
                    onError: function () {
                        View.alerts.showReconnect(true);
                    },
                    onMessage: function (msg) {
                        Content.processor.processMessage(msg);
                    },
                    onOpen: function () {
                        Controller.requests.fetchMeta();
                        Controller.nav.hashRequest();
                    }
                });

                var elapsed = ((performance.now() - t0) / 1000).toFixed(3);

                Log.debugLog("[init]: Initialisation complete. Took " +
                    elapsed + "s.");
                Log.debugLog('====================');

                loadQueue.dequeue();
            }
        );
    });
});