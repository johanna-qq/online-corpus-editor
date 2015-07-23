/**
 * Online Corpus Editor -- Error Handling
 * Created by zechy on 22/6/15.
 *
 * N.B.: This is not a module; it is called and run directly as part of the
 * loading process.
 */

// If something goes wrong with the loading, show notifications (which
// degrade gracefully back down to the basic version in main.js)
var basicError = requirejs.onError;

requirejs.onError = function (err) {
    // Start by logging any earlier errors (i.e., with jQuery)
    console.log(err);

    // Our MO here is to keep redefining onError, since all the checks we
    // make will be asynchronous (so we can't use naive try ... catch blocks)

    // Check if the view module is up (we're actually interested in view.alerts)
    requirejs.onError = function (err) {
        // No view. Round 2: Did jQuery load?

        requirejs.onError = function (err) {
            basicError();
        };

        var $ = requirejs("jquery");
        if (typeof $ !== "undefined") {
            // Check for the presence of #loading-div; repurpose it if we can.
            var loadingDiv = $('#loading-div');
            if (loadingDiv.length > 0) {
                loadingDiv.html('<div class="panel">' +
                    'Whoops, looks like something ' +
                    'broke :( Refreshing the page should help.' +
                    '</div>');

                console.log(err);
            } else {
                // Didn't find loadingDiv -- Throw a fit
                requirejs.onError();
            }
        }
    };

    var View = requirejs("app/view");
    if (typeof View !== "undefined") {
        View.alerts.showLoaderError(err);
    }
};