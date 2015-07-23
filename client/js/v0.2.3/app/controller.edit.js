/**
 * Online Corpus Editor -- User Interaction (submodule)
 * Dynamic editing
 * Zechy Wong
 * Last Modified: 23 June 2015
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
        Util = require('app/util'),

        View = require('app/view'),
        Meta = require('app/meta');
    require('tag-it_mod');
    require('foundation_mod');

    Log.debugLog("    [controller.edit]: Submodule ready.");

    return function (Controller) {

        Controller.edit = {
            /**
             * Prepares the event handlers for all editable elements in the
             * current view.
             * (Non-debounced version)
             */
            _initHandlers: function () {
                Log.debugLog({
                    module: 'controller.edit',
                    message: 'Initialising edit handlers.'
                });

                var currentView = View.getCurrentView(),
                    Edit = this;

                /*******************
                 * Flag (checkbox) *
                 *******************/
                currentView.on("change", "input[type='checkbox']", function () {
                    // For flags, the ID is in the input element itself
                    // (Because we don't [currently?] want the value to
                    // change when the user clicks anywhere else in the <td>
                    var recordID = /([0-9]+)/.exec(this.id)[1];
                    Controller.requests.requestUpdate(recordID, 'flag', this.checked);
                });

                /**********************
                 * Category (textbox) *
                 **********************/
                currentView.on("mousedown", "[id^='cat-']", function (evt) {
                    if (evt.which !== 1) {
                        // Not a LMB click; nothing to do here
                        return;
                    }

                    var currentTD = $(this).closest('td'),
                        dynamicID = Config._categoryDynamicID,
                        emptyValue = '0',
                        field = 'category';

                    // See if the user clicked within the <td> again.  If the
                    // user wasn't clicking directly on the input, save the
                    // value + close the input element.
                    // evt.target --> innermost target
                    var existingInput = currentTD.find('#' + dynamicID);
                    if (existingInput.length) {
                        if ($(evt.target).attr('id') !== dynamicID) {
                            evt.preventDefault();
                            existingInput.triggerHandler('focusout');
                            return;
                        } else {
                            return;
                        }
                    }

                    // currentValue check
                    var currentValue = parseInt(currentTD.text()).toString();

                    var newInput = $("<input/>")
                        .attr({
                            id: dynamicID,
                            type: 'text',
                            value: currentValue
                        })
                        .focusout(function () {
                            // -[ Update currentTD ]-
                            var $input = $(this);
                            var newValue = $input.val().trim();
                            if (newValue === '') {
                                newValue = emptyValue;
                            }
                            var newDisplayValue = newValue;

                            // Escape html tags (except newlines)
                            // No lookbehind....
                            newValue = newValue
                                .replace(/<(?!br>)/g, '&lt;')
                                .replace(/(?!<br)(.{3})>/g, '$1&gt;');

                            currentTD.empty().html(newDisplayValue);

                            // -[ Update Server ]-
                            if (newValue !== currentValue) {
                                var recordID =
                                    /([0-9]+)/.exec(currentTD.attr('id'))[1];
                                Controller.requests
                                    .requestUpdate(recordID, field, newValue);
                            }
                        });

                    currentTD.empty().append(newInput);
                    // We're going to focus the input element; make sure it
                    // doesn't immediately lose that focus.
                    evt.preventDefault();
                    newInput.focus().select();
                });

                /*********************
                 * Comment (textbox) *
                 *********************/
                currentView.on("mousedown", "[id^='cmt-']", function (evt) {
                    if (evt.which !== 1) {
                        // Not a LMB click; nothing to do here
                        return;
                    }

                    var currentTD = $(this).closest('td'),
                        dynamicID = Config._commentDynamicID,
                        emptyValue = '',
                        field = 'comment';

                    // See if the user clicked within the <td> again.  If the
                    // user wasn't clicking directly on the input, save the
                    // value + close the input element.
                    // evt.target --> innermost target
                    var existingInput = currentTD.find('#' + dynamicID);
                    if (existingInput.length) {
                        if ($(evt.target).attr('id') !== dynamicID) {
                            evt.preventDefault();
                            existingInput.triggerHandler('focusout');
                            return;
                        } else {
                            return;
                        }
                    }

                    // ===================
                    // Current Value check
                    // ===================
                    var currentValue = '',
                        valueChild = currentTD.find('.static-comment');
                    if (!valueChild.hasClass('empty-comment')) {
                        currentValue = Util.br2nl(valueChild.html());
                    }

                    var newInput = $("<textarea/>")
                        .attr({
                            id: dynamicID
                        })
                        .html(currentValue)
                        .focusout(function () {
                            // -[ Update currentTD ]-
                            var $input = $(this);
                            var newValue = $input.val().trim();
                            var newDisplayValue =
                                "<span class='static-comment'>" +
                                Util.nl2br(newValue) +
                                "</span>";

                            if (newValue === '') {
                                newValue = emptyValue;
                                newDisplayValue =
                                    "<span class='static-comment empty-comment'>" +
                                    "Click to add" +
                                    "</span>";
                            }

                            // Escape html tags (except newlines)
                            // No lookbehind....
                            newValue = newValue
                                .replace(/<(?!br>)/g, '&lt;')
                                .replace(/(?!<br)(.{3})>/g, '$1&gt;');

                            currentTD.empty().html(newDisplayValue);

                            // -[ Update Server ]-
                            if (newValue !== currentValue) {
                                var recordID =
                                    /([0-9]+)/.exec(currentTD.attr('id'))[1];
                                Controller.requests
                                    .requestUpdate(recordID, field, newValue);
                            }
                        });

                    currentTD.empty().append(newInput);
                    // We're going to focus the input element; make sure it
                    // doesn't immediately lose that focus.
                    evt.preventDefault();
                    newInput.focus();
                });

                /*********************************
                 * Languages contained (textbox) *
                 *********************************/
                currentView.on("mousedown", "[id^='lang-']", function (evt) {
                    if (evt.which !== 1) {
                        // Not a LMB click; nothing to do here
                        return;
                    }

                    var currentSpan = $(this).closest('span'),
                        dynamicID = Config._languageDynamicID,
                        emptyValue = 'None',
                        field = 'language';

                    // See if the user clicked within the <td> again.  If the
                    // user wasn't clicking directly on the input, save the
                    // value + close the input element.
                    // evt.target --> innermost target
                    var existingInput = currentSpan.find('#' + dynamicID);
                    if (existingInput.length) {
                        if ($(evt.target).attr('id') !== dynamicID) {
                            evt.preventDefault();
                            existingInput.triggerHandler('focusout');
                            return;
                        } else {
                            return;
                        }
                    }

                    // currentValue check
                    var currentValue = currentSpan.text().trim();

                    var newInput = $("<input/>")
                        .attr({
                            id: dynamicID,
                            type: 'text',
                            value: currentValue
                        })
                        .focusout(function () {
                            // -[ Update currentTD ]-
                            var $input = $(this);
                            var newValue = $input.val().trim();
                            if (newValue === '') {
                                newValue = emptyValue;
                            }
                            var newDisplayValue = newValue;

                            // Escape html tags (except newlines)
                            // No lookbehind....
                            newValue = Util.escapeHTML(newValue, true);

                            currentSpan.empty().html(newDisplayValue);

                            // -[ Update Server ]-
                            if (newValue !== currentValue) {
                                var recordID =
                                    /([0-9]+)/.exec(currentSpan.attr('id'))[1];
                                Controller.requests
                                    .requestUpdate(recordID, field, newValue);
                            }
                        });

                    currentSpan.empty().append(newInput);
                    // We're going to focus the input element; make sure it
                    // doesn't immediately lose that focus.
                    evt.preventDefault();
                    newInput.focus().select();
                });

                // ************************
                // * Tags (jQuery Tag-it) *
                // ************************

                // Start by initialising the tag widget on all applicable
                // fields; we'll bind the handlers on the view, like with
                // the other kinds of input elements
                var t0 = performance.now();

                // Initialise the widgets in sequence using the global queue
                // -- Takes a little longer, but helps make sure the CPU
                // doesn't choke on this function.
                // N.B.: This also blocks the global queue for as long as
                // tag-it needs; we want to get those tags displayed asap.
                View.getCurrentView().find('.tagit-hidden-field').each(
                    function () {
                        var $tagIt = $(this);
                        Util.addToGlobalQueue(function () {
                            $tagIt.tagit({
                                autocomplete: {
                                    // Modded version of autocomplete.source from tag-it
                                    // Meta.tagsAvailable needs to be a pointer, since
                                    // it can change even after this handler is bound
                                    source: function (search, showChoices) {
                                        var filter = search.term.toLowerCase();
                                        var choices = $.grep(Meta.tagsAvailable, function (element) {
                                            // Only match autocomplete options that begin with the search term.
                                            // (Case insensitive.)
                                            return (element.toLowerCase().indexOf(filter) === 0);
                                        });
                                        if (!this.options.allowDuplicates) {
                                            choices = this._subtractArray(choices, this.assignedTags());
                                        }
                                        showChoices(choices);
                                    }
                                },
                                showAutocompleteOnFocus: true,
                                removeConfirmation: true,
                                afterTagAdded: Edit.saveTags,
                                afterTagRemoved: Edit.saveTags
                            });
                        })
                    }
                );

                Util.addToGlobalQueue(function () {
                    Log.debugLog({
                        module: 'controller.edit',
                        message: 'Initialising tag-it took ' + (performance.now() - t0).toFixed(3) + 'ms.'
                    });

                    currentView.on("mousedown", "[id^='tags-']", function (evt) {
                        if (evt.which !== 1) {
                            // Not a LMB click; nothing to do here
                            return;
                        }

                        var currentTD = $(this).closest('td');
                        var tagIt = currentTD.find('.tagit-hidden-field');
                        var tagInput = tagIt.data('ui-tagit').tagInput;

                        // === Label clicks ===
                        var $target = $(evt.target).closest('a');
                        if ($target.hasClass('tagit-label')) {
                            evt.preventDefault();
                            Controller.nav.search('tag:' + $target.text(), 1);
                            return;
                        }

                        if ($target.hasClass('tagit-close')) {
                            // The plugin will handle it (via its click handler,
                            // which we are not overriding here)
                            return;
                        }

                        // === Show tagInput textbox and attach focusout handler ===
                        currentTD.find(".empty-comment").remove();
                        tagInput.off("focusout.oce");
                        tagInput.on("focusout.oce", function () {
                            if (tagInput.val() !== '') {
                                // If the autocomplete dialog is up, the new tag may
                                // be left in the input field.  Jury-rig around the
                                // autocompletion feature and get that tag saved!
                                var newTag = $.trim(tagInput.val().replace(/^"(.*)"$/, '$1'));
                                tagInput.val('');
                                tagIt.tagit("option", "showAutocompleteOnFocus", false);
                                tagIt.tagit("createTag", newTag);
                                tagIt.tagit("option", "showAutocompleteOnFocus", true);
                            }

                            // Pop the placeholder if there was a focusout on an
                            // empty tagIt/tagInput (i.e., saveTags not called)
                            if (tagIt.val() === '' && !currentTD.find('.empty-comment').length) {
                                currentTD.append("<span class='empty-comment'>Click to add</span>");
                            }

                            tagInput.hide();
                        });

                        evt.preventDefault();
                        tagInput.show().focus();
                    });
                });
            },

            /**
             * Helper function for saving changes to a record's taglist.
             * @param evt - Passed by the plugin; unused
             * @param ui - Passed by the plugin
             */
            saveTags: function (evt, ui) {
                // Tag created by the system, not the user
                if (ui.duringInitialization) {
                    return
                }

                var tagIt = $(this);
                var currentTD = tagIt.parent();
                var tagInput = tagIt.data('ui-tagit').tagInput;
                var recordID = /-([0-9]+)/.exec(currentTD.prop('id'))[1];
                Controller.requests.requestUpdate(recordID, "tag",
                    tagIt.val());

                // Pop the placeholder if the last tag in the list was
                // removed by clicking on the 'x' (i.e., no focusout event
                // on tagInput)
                if (tagIt.val() === '' && !tagInput.data('autocomplete-open')) {
                    currentTD.append("<span class='empty-comment'>Click to add</span>");
                }
            }
        };

        //Controller.edit.initHandlers =
        //    Foundation.utils.debounce(Controller.edit._initHandlers, 500);

        Controller.edit.initHandlers = Controller.edit._initHandlers;
    };
});