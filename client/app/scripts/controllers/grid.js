/**
 * Online Corpus Editor -- Angular-grid controller
 */

(function () {
    "use strict";

    angular.module("oce").controller("gridController", ['$scope', function ($scope) {
        var columnDefs = [
            {headerName: "Make", field: "make"},
            {headerName: "Model", field: "model"},
            {headerName: "Price", field: "price"}
        ];

        var rowData = [
            {make: "Toyota", model: "Celica", price: 35000},
            {make: "Ford", model: "Mondeo", price: 32000},
            {make: "Porsche", model: "Boxter", price: 72000}
        ];

        $scope.gridOptions = {
            columnDefs: columnDefs,
            rowData: rowData,
            dontUseScrolls: true // because so little data, no need to use scroll bars
        };
    }]);
})();
