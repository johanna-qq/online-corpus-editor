/**
 * Online Corpus Editor -- Angular-grid controller
 */

(function () {
    "use strict";

    angular.module("oce").controller("gridController", function (wsHandler) {
        // === Cell Renderers ===

        // --- Centring ---
        // By default, all cell renderers should be set to this function
        // for vertical centring (assuming they don't implement it separately)
        function centreVertical(innerContent) {
            if (typeof innerContent === "object") {
                // This was called directly from the column definitions;
                // extract params.value
                innerContent = innerContent.value;
            }
            return "<div class='oce-grid-content--centre-vertical-parent'>" +
                "<div class='oce-grid-content--centre-vertical-child'>" + innerContent + "</div></div>";
        }

        function centreHorizontal(innerContent) {
            if (typeof innerContent === "object") {
                innerContent = innerContent.value;
            }
            return "<div class='oce-grid-content--centre-horizontal'>" + innerContent + "</div>";
        }

        function centreBoth(innerContent) {
            if (typeof innerContent === "object") {
                innerContent = innerContent.value;
            }
            return centreVertical(centreHorizontal(innerContent));
        }

        // --- Per-field Settings ---
        function idRender(params){
            return centreBoth("<div>" + params.value + "</div>");
        }

        function flagRender(params) {
            var flag = '';
            if (params.value === true) {
                flag = " checked";
            }
            return centreBoth("<input type='checkbox'" + flag + ">");
        }

        // We will be calling sizeColumnsToFit() when the table is ready;
        // the widths below should be treated (more or less) as ratios.
        var columnDefs = [
            {
                headerName: "ID", field: "rowid", width: 50,
                cellRenderer: idRender
            },
            {
                headerName: "Flag", field: "flag", width: 50,
                cellRenderer: flagRender
            },
            {
                headerName: "Content", field: "content", width: 500,
                cellRenderer: centreVertical
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
                cellRenderer: centreVertical
            }
        ];

        // Virtual pagination
        function getRows(params) {
            console.log('asking for ' + params.startRow + ' to ' + params.endRow);

            wsHandler.getFirst().then(
                // Success
                function (results) {
                    params.successCallback(results.data.results);
                },
                // Error
                function () {
                    params.failCallback();
                }
            );
        }

        var dataSource = {
            pageSize: 100,
            overflowSize: 100,
            maxPagesInCache: 3,
            rowCount: 50000,
            getRows: getRows
        };

        var gridCtrl = this;
        gridCtrl.gridOptions = {
            columnDefs: columnDefs,
            enableColResize: true,
            rowHeight: 100,
            virtualPaging: true,
            ready: function () {
                gridCtrl.gridOptions.api.setDatasource(dataSource);
            }
        };
    });
})();
