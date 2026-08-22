(function (root, factory) {
    const geometry = factory();

    if (typeof module === 'object' && module.exports) {
        module.exports = geometry;
    }
    if (root) {
        root.BonfireMapGeometry = geometry;
    }
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
    'use strict';

    function isCoordinatePoint(value) {
        if (!value) return false;
        if (Array.isArray(value)) {
            return value.length >= 2
                && typeof value[0] === 'number'
                && typeof value[1] === 'number';
        }
        return typeof value === 'object'
            && typeof value.lat === 'number'
            && typeof value.lng === 'number';
    }

    function splitPolygonParts(coords) {
        if (!Array.isArray(coords) || coords.length === 0) return [];

        const children = coords.filter(item => Array.isArray(item) && item.length > 0);
        if (children.length === 0) return [];

        // Ring -> one polygon with one outer ring.
        if (isCoordinatePoint(children[0])) {
            return [[children]];
        }

        // Polygon -> keep the outer ring and every hole in the same part.
        if (Array.isArray(children[0]) && isCoordinatePoint(children[0][0])) {
            return [children];
        }

        // MultiPolygon (including nested legacy wrappers) -> independent parts.
        return children.flatMap(splitPolygonParts);
    }

    function pointValues(point) {
        if (Array.isArray(point)) {
            return { lat: point[0], lng: point[1] };
        }
        return { lat: point.lat, lng: point.lng };
    }

    function ringSignedArea(ring) {
        if (!Array.isArray(ring) || ring.length < 3) return 0;

        let area = 0;
        for (let index = 0; index < ring.length; index += 1) {
            const current = pointValues(ring[index]);
            const next = pointValues(ring[(index + 1) % ring.length]);
            area += (current.lng * next.lat) - (next.lng * current.lat);
        }
        return area / 2;
    }

    function polygonArea(rings) {
        if (!Array.isArray(rings) || rings.length === 0) return 0;

        const outerArea = Math.abs(ringSignedArea(rings[0]));
        const holesArea = rings.slice(1).reduce(
            (total, ring) => total + Math.abs(ringSignedArea(ring)),
            0,
        );
        return Math.max(0, outerArea - holesArea);
    }

    return {
        isCoordinatePoint,
        splitPolygonParts,
        ringSignedArea,
        polygonArea,
    };
}));
