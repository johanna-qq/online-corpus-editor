/**
 * Online Corpus Editor -- Configuration
 * Zechy Wong
 * Last Modified: 26 June 2015
 *
 * N.B. Some of these options may be cached by modules (i.e., changes may
 * not be dynamically reflected by module behaviour)
 */

define({
    // === User Configurable ===
    // These settings should be updated if index.html is changed for some
    // reason.
    // Note: All IDs are specified without the leading '#'.

    /**
     * Corpus title
     */
    title: 'Singapore English Tweets',
    titleID: 'title-container',

    /**
     * WebSocket server details
     */
    host: location.hostname || "localhost",
    port: 8081,

    /**
     * Viewport
     */
    // The header and footer will be ignored when scrolling to an element.
    headerID: 'top-nav',
    footerID: 'pager',
    // The main container is at the same level as the header and footer,
    // and holds the viewport.
    mainID: 'main-container',
    viewportID: 'data-container',   // Cached by [view]
    // When scrolling to a specified element, determines the default final target position for that element.
    // e.g., 0.4 --> 40% of the way down the visible area.
    scrollOffset: 0.4,
    scrollSpeed: 750,

    /**
     * Content formatting
     */
    recordsPerPage: 100,
    // Any element with the following class will have its emoji rendered after formatting
    emojiClass: 'render-emoji',

    /**
     * Navigation
     */
    recordJumpID: "txt-jump-record",    // Input box for going to a specific
                                        // record
    pageJumpID: "txt-jump-page",        // Input box for going to a specific page
    searchID: "txt-search",             // Search box

    /**
     * Pager
     */
    pageBuffer: 3,      // Number of pages to the left/right of the current
                        // page to show on the pager

    /**
     * Alerts and Notifications
     */
    alertSpeed: 350,            // Effect transition speed for alerts
    alertDuration: 800,         // Duration for alerts/notifications that
                                // timeout automatically

    /**
     * Debug mode
     */
    debug: true,        // Enables (console) logging

    // === System Constants ===
    // These settings are used internally and should not need to be changed.

    /**
     * Viewport
     */
    _titleContainerID: 'title-container',
    _alertContainerID: 'alert-container',
    _viewportInnerID: 'data-inner',     // Cached by [view]
    _viewID: 'data-view',
    _viewOldID: 'data-view-old',

    /**
     * Dynamic editing input elements
     */
    _categoryDynamicID: 'dynamic-category',
    _commentDynamicID: 'dynamic-comment',
    _languageDynamicID: 'dynamic-language'
});