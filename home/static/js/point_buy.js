/* Point-buy nativo dos atributos-base.
   Regras (de window.POINT_BUY, fornecido pela view / home/point_buy.py):
   - cada atributo começa em 8, máximo 15; custo cumulativo em POINT_BUY.custo;
   - os POINT_BUY.maxPontos (27) devem ser distribuídos por completo.
   Expõe scores(), state(), isComplete() e onChange(cb). */
(function () {
    'use strict';

    var listeners = [];

    function init() {
        var root = document.querySelector('[data-point-buy]');
        if (!root || !window.POINT_BUY) return;
        var PB = window.POINT_BUY;
        var rows = Array.prototype.slice.call(root.querySelectorAll('tr[data-attr]'));

        function score(row) { return parseInt(row.querySelector('[data-score]').value, 10) || PB.min; }
        function setScore(row, v) { row.querySelector('[data-score]').value = v; }
        function custo(v) { return PB.custo[v] != null ? PB.custo[v] : 0; }
        function gasto() { return rows.reduce(function (a, row) { return a + custo(score(row)); }, 0); }
        function mod(total) { return Math.floor((total - 10) / 2); }

        function scores() {
            var out = {};
            rows.forEach(function (row) { out[row.getAttribute('data-attr')] = score(row); });
            return out;
        }

        function state() {
            var spent = gasto();
            return {
                spent: spent,
                remaining: PB.maxPontos - spent,
                complete: spent === PB.maxPontos
            };
        }

        function remainingLabel(remaining) {
            return remaining === 1 ? 'Falta 1 ponto' : 'Faltam ' + remaining + ' pontos';
        }

        function emit() {
            var currentScores = scores();
            var currentState = state();
            listeners.forEach(function (cb) {
                try { cb(currentScores, currentState); } catch (e) {}
            });
        }

        function render() {
            var total = gasto();
            rows.forEach(function (row) {
                var s = score(row);
                var m = mod(s);
                row.querySelector('[data-mod]').textContent = (m >= 0 ? '+' : '') + m;
                row.querySelector('[data-cost]').textContent = custo(s);
                var inc = row.querySelector('[data-inc]');
                var dec = row.querySelector('[data-dec]');
                var novoTotal = total - custo(s) + custo(s + 1);
                inc.disabled = s >= PB.max || novoTotal > PB.maxPontos;
                dec.disabled = s <= PB.min;
            });
            var pts = document.querySelector('[data-points]');
            if (pts) {
                pts.textContent = total;
                pts.classList.toggle('text-[var(--spark)]', total === PB.maxPontos);
            }
            var status = root.querySelector('[data-points-status]');
            var remaining = PB.maxPontos - total;
            if (status) {
                status.textContent = remaining === 0
                    ? 'Compra concluída'
                    : remainingLabel(remaining);
                status.classList.toggle('text-[var(--spark)]', remaining === 0);
                status.classList.toggle('text-[var(--flame)]', remaining !== 0);
            }
            root.setAttribute('aria-invalid', remaining === 0 ? 'false' : 'true');
            emit();
        }

        rows.forEach(function (row) {
            row.querySelector('[data-inc]').addEventListener('click', function () {
                var s = score(row);
                if (s >= PB.max) return;
                if (gasto() - custo(s) + custo(s + 1) > PB.maxPontos) return;
                setScore(row, s + 1);
                render();
            });
            row.querySelector('[data-dec]').addEventListener('click', function () {
                var s = score(row);
                if (s <= PB.min) return;
                setScore(row, s - 1);
                render();
            });
        });

        var reset = root.querySelector('[data-reset]');
        if (reset) reset.addEventListener('click', function () {
            rows.forEach(function (row) { setScore(row, PB.min); });
            render();
        });

        window.PointBuy = {
            scores: scores,
            state: state,
            isComplete: function () { return state().complete; },
            onChange: function (cb) { listeners.push(cb); cb(scores(), state()); }
        };

        render();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
