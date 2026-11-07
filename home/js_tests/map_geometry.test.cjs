const test = require('node:test');
const assert = require('node:assert/strict');

const geometry = require('../static/js/map_geometry.js');

const outer = [[0, 0], [0, 10], [10, 10], [10, 0]];
const hole = [[2, 2], [2, 6], [6, 6], [6, 2]];
const secondOuter = [[20, 20], [20, 25], [25, 25], [25, 20]];

test('keeps polygon holes in the same Leaflet layer', () => {
    const parts = geometry.splitPolygonParts([outer, hole]);

    assert.equal(parts.length, 1);
    assert.deepEqual(parts[0], [outer, hole]);
});

test('splits multipolygons without turning holes into polygons', () => {
    const parts = geometry.splitPolygonParts([
        [outer, hole],
        [secondOuter],
    ]);

    assert.equal(parts.length, 2);
    assert.deepEqual(parts[0], [outer, hole]);
    assert.deepEqual(parts[1], [secondOuter]);
});

test('calculates net polygon area by subtracting holes', () => {
    assert.equal(geometry.polygonArea([outer, hole]), 84);
});
