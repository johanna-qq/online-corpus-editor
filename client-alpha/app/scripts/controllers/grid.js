/**
 * Online Corpus Editor -- Angular-grid controller
 */

(function () {
    "use strict";

    angular.module("oce").controller("gridController", function (jQuery, serverManager, util, $window) {
        var $ = jQuery;
        var gridCtrl = this;
        // === Cell Renderers ===

        // --- Centring ---
        // By default, all cell renderers should be set to this function
        // for vertical centring (assuming they don't implement it separately)
        function centreVertical(innerContent) {
            if (typeof innerContent === "object") {
                // This was called directly from the column definitions;
                // extract params.value
                innerContent = innerContent.value;
                if (typeof innerContent === "undefined") {
                    innerContent = "...";
                }
            }
            return "<div class='oce-grid-content--centre-vertical-parent'>" +
                "<div class='oce-grid-content--centre-vertical-child'>" + innerContent + "</div></div>";
        }

        function centreHorizontal(innerContent) {
            if (typeof innerContent === "object") {
                innerContent = innerContent.value;
                if (typeof innerContent === "undefined") {
                    innerContent = "...";
                }
            }
            return "<div class='oce-grid-content--centre-horizontal'>" + innerContent + "</div>";
        }

        function centreBoth(innerContent) {
            if (typeof innerContent === "object") {
                innerContent = innerContent.value;
                if (typeof innerContent === "undefined") {
                    innerContent = "...";
                }
            }
            return centreVertical(centreHorizontal(innerContent));
        }

        function overflowEllipsis(innerContent) {
            if (typeof innerContent === "object") {
                innerContent = innerContent.value;
                if (typeof innerContent === "undefined") {
                    innerContent = "...";
                }
            }
            return "<div class='oce-grid-content--overflow-ellipsis'>" + innerContent + "</div>";
        }

        // --- Per-field Settings ---
        function idRender(params) {
            return centreBoth(overflowEllipsis(params));
        }

        function flagRender(params) {
            var flag = '';
            if (params.value === true) {
                flag = " checked";
            }
            return centreBoth("<input type='checkbox'" + flag + ">");
        }

        function contentRender(params) {
            if (typeof params.value === "undefined") {
                params.value = "Loading...";
            }
            return centreVertical(params);
        }

        function commentRender(params) {
            if (typeof params.value === "undefined") {
                params.value = "Loading...";
            }

            var $placeholder = $("<div class='oce-grid-content--editable-placeholder'>Click to add...</div>");

            var editing = false;

            var $eCell = $("<div/>")
                .addClass("oce-grid-content--editable-parent");
            var $eLabel = $("<div/>");
            if (params.value === '') {
                $eLabel.append($placeholder);
            } else {
                $eLabel.html(params.value);
            }
            $eCell.append($eLabel);

            var $eTextarea = $("<textarea/>")
                .addClass("oce-grid-content--editable-textarea");

            $eCell.on('click', function () {
                if (!editing) {
                    var currentValue;
                    if ($eLabel.find($placeholder).length > 0) {
                        $placeholder.detach();
                        currentValue = '';
                    } else {
                        currentValue = $eLabel.html().trim();
                        currentValue = util.unescapeHTML(currentValue);
                        currentValue = util.br2nl(currentValue);
                    }
                    $eTextarea.val(currentValue);
                    $eLabel.detach();
                    $eCell.append($eTextarea);
                    $eTextarea.focus();

                    $eCell.closest(".ag-cell").addClass("oce-grid-content--editable-cell");
                    editing = true;
                }
            });

            $eTextarea.on('blur', function () {
                if (editing) {
                    $eCell.closest(".ag-cell").removeClass("oce-grid-content--editable-cell");
                    editing = false;

                    var newValue = $eTextarea.val().trim();
                    newValue = util.escapeHTML(newValue, true);
                    newValue = util.br2nl(newValue);
                    params.data[params.colDef.field] = newValue;
                    if (newValue === '') {
                        $eLabel.html('');
                        $eLabel.append($placeholder);
                    } else {
                        $eLabel.html(util.nl2br(newValue));
                    }
                    $eTextarea.detach();
                    $eCell.append($eLabel);
                }
            });

            var $centred = $(centreVertical(''));
            $centred.find(".oce-grid-content--centre-vertical-child").append($eCell);
            return $centred.get(0);
        }

        // We will be calling sizeColumnsToFit() when the table is ready;
        // the widths below should be treated (more or less) as ratios.
        var columnDefs = [
            {
                headerName: "Flag", field: "flag", width: 50,
                cellRenderer: flagRender
            },
            {
                headerName: "ID", field: "rowid", width: 50,
                cellRenderer: idRender
            },
            {
                headerName: "Content", field: "content", width: 500,
                cellRenderer: contentRender
            },
            {
                headerName: "Language(s)", field: "language", width: 100,
                cellRenderer: centreVertical
            },
            {
                headerName: "Category", field: "category", width: 50,
                cellRenderer: centreBoth
            },
            {
                headerName: "Tag(s)", field: "tag", width: 100,
                cellRenderer: centreVertical
            },
            {
                headerName: "Comment(s)", field: "comment", width: 200,
                cellRenderer: commentRender
            }
        ];

        // Virtual pagination
        function getRows(params) {
            console.log('asking for ' + params.startRow + ' to ' + params.endRow);

            serverManager.requestRecords(params.startRow, params.endRow).then(
                // Success
                function (results) {
                    params.successCallback(results.data.results);
                    gridCtrl.gridOptions.api.sizeColumnsToFit();
                },
                // Error
                function () {
                    params.failCallback();
                }
            );
        }

        var dataSource = {
            pageSize: 200,
            getRows: getRows
        };

        function initGrid() {
            // Get the rowCount from the server, then set our data source
            serverManager.requestMeta().then(
                function (results) {
                    var meta = results.data;
                    dataSource.rowCount = meta.total;
                    gridCtrl.gridOptions.api.setDatasource(dataSource);

                    // Column Resizing (called in getRows above, and when the window is resized)
                    var lazyColumnResize = util.debounce(gridCtrl.gridOptions.api.sizeColumnsToFit.bind(gridCtrl.gridOptions.api), 200);
                    $($window).on('resize', lazyColumnResize);
                }
            );
        }

        gridCtrl.gridOptions = {
            columnDefs: columnDefs,
            enableColResize: true,
            enableSorting: true,
            headerHeight: 30,
            rowHeight: 80,
            //virtualPaging: true,
            ready: initGrid
        };
    });
})();
