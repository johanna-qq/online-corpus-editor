/**
 * Online Corpus Editor -- Angular-grid controller
 */

(function () {
    "use strict";

    angular.module("oce").controller("gridController", function ($window, $scope, wsHandler) {
        // Column definitions
        function flagRender(params) {
            var flag = '';
            if (params.value === true) {
                flag = " checked";
            }
            return "<input type='checkbox'" + flag + ">";
        }

        var columnDefs = [
            {headerName: "#", field: "rowid", width: 50},
            {
                headerName: "Flag",
                field: "flag",
                width: 50,
                cellRenderer: flagRender
            },
            {headerName: "Content", field: "content", width: 500},
            {headerName: "Language(s)", field: "language", width: 100},
            {headerName: "Category", field: "category", width: 50},
            {headerName: "Tag(s)", field: "tag", width: 100},
            {headerName: "Comment", field: "comment", width: 300}
        ];

        // Virtual pagination
        function getRows(params) {
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
            getRows: getRows
        };

        $scope.gridOptions = {
            columnDefs: columnDefs,
            enableColResize: true,
            rowHeight: 75,
            virtualPaging: true,
            ready: function () {
                $scope.gridOptions.api.setDatasource(dataSource);
            }
        };
    });
})();
