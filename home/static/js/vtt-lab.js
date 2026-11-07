const root = document.querySelector('#vtt-lab');
const $ = (id) => document.getElementById(id);
let active = null;
let selected = null;
let board = null;
let busy = false;
let moveArmed = false;
let rendererPromise = null;
let walkArmed = false;
let walkPlan = null;
const teamChoices = new Map();
function encounter() { return active?.state.combat; }
function fighting() { return Boolean(encounter()?.active); }

function status(message, error = false) {
  $('lab-status').textContent = message;
  $('lab-status').dataset.error = String(error);
}
function token() { return active?.state.tokens.find((entry) => entry.id === selected); }
function controls() {
  for (const form of [$('import-character'), $('import-creature'), $('set-hp'), $('move-token'), $('set-resource'), $('paint-terrain'), $('configure-map')]) {
    for (const input of form.elements) input.disabled = busy || !active || fighting();
  }
  $('create-session').querySelector('button').disabled = busy;
  for (const id of ['next-turn', 'refresh-session', 'frame-board', 'zoom-in', 'zoom-out']) $(id).disabled = busy || !active;
  $('move-on-board').disabled = busy || !token() || fighting();
  $('move-on-board').setAttribute('aria-pressed', String(moveArmed));
  board?.setMoveArmed(moveArmed || walkArmed);
  $('next-turn').disabled = busy || !active || fighting();
  const combat = encounter();
  const view = combat?.view;
  for (const input of $('start-combat').elements) input.disabled = busy || !active || fighting();
  $('start-combat').querySelector('button').disabled = busy || fighting() || !active || active.state.tokens.length < 2;
  $('combat-actor').disabled = busy || !fighting() || Boolean(view?.current_actor);
  $('start-combat-turn').disabled = busy || !fighting() || Boolean(view?.current_actor) || view?.finished;
  $('end-combat-turn').disabled = busy || !fighting() || !view?.current_actor || view?.finished;
  $('end-combat').disabled = busy || !fighting();
  const canAct = fighting() && view?.current_actor && !view.action_used && !view.finished;
  for (const form of [$('combat-attack'), $('combat-heal')]) for (const input of form.elements) input.disabled = busy || !canAct;
  $('combat-target').disabled = busy || !canAct;
  for (const input of $('measure-distance').elements) input.disabled = busy || !token() || active.state.tokens.length < 2;
  const walking = view?.movement?.[view?.current_actor];
  const canWalk = fighting() && view?.current_actor && !view.finished && walking?.available;
  for (const input of $('walk-form').elements) input.disabled = busy || !canWalk;
  $('confirm-walk').disabled = busy || !canWalk || !walkPlan;
  $('point-walk').setAttribute('aria-pressed', String(walkArmed));
}
async function request(url, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 20000);
  try {
    const response = await fetch(url, {credentials: 'same-origin', signal: controller.signal,
      ...options, headers: {'Accept': 'application/json', 'Content-Type': 'application/json',
        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value, ...options.headers}});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = new Error(data.message || data.error || `Falha na requisicao (${response.status})`);
      error.status = response.status;
      error.code = data.error;
      throw error;
    }
    return data;
  } finally { clearTimeout(timeout); }
}
async function operation(work) {
  if (busy) return;
  busy = true; controls();
  try { await work(); }
  catch (error) {
    status(error.name === 'AbortError' ? 'Resposta nao confirmada. Atualize a sessao antes de repetir.' : error.message, true);
  } finally { busy = false; controls(); }
}
function itemButton(text, action, chosen = false) {
  const button = document.createElement('button');
  button.type = 'button'; button.textContent = text;
  button.dataset.selected = String(chosen);
  button.addEventListener('click', action);
  return button;
}
async function sessions() {
  const data = await request(root.dataset.api);
  $('sessions-list').replaceChildren(...data.sessions.map((session) =>
    itemButton(session.nome, () => operation(() => load(session.id)), session.id === active?.id)));
  return data.sessions;
}
async function ensureBoard() {
  if (board) return board;
  if (!rendererPromise) rendererPromise = import(root.dataset.renderer).then(({mountBoard}) => {
    board = mountBoard($('board-viewport'), (id, cell) => {
      if (busy) return;
      if (id) { selected = id; moveArmed = false; walkArmed = false; inspect(); showTokenSelection(); controls(); }
      else if (cell && walkArmed) {
        for (const axis of ['x', 'y', 'z']) $(`walk-${axis}`).value = cell[axis];
        operation(() => previewWalk(cell));
      }
      else if (cell && moveArmed && token()) {
        operation(() => command('move_token', {token_id: selected, ...cell}));
      }
    }, (message, error) => {
      $('map-image-status').textContent = message;
      $('map-image-status').dataset.error = String(error);
    });
    return board;
  }).catch((error) => { rendererPromise = null; throw error; });
  return rendererPromise;
}
function inspect() {
  const entry = token();
  $('token-inspector').hidden = !entry;
  if (!entry) return;
  $('token-name').textContent = entry.nome;
  $('token-hp').value = entry.hp;
  $('token-hp').max = entry.max_hp;
  for (const axis of ['x', 'y', 'z']) $(`token-${axis}`).value = entry[axis];
  $('token-x').max = active.state.board.width - 1;
  $('token-y').max = active.state.board.height - 1;
  const facts = [['PV', `${entry.hp} / ${entry.max_hp}`], ['Origem', entry.source?.criatura_id ? `Criatura ${entry.source.criatura_id}` : `Personagem ${entry.source?.personagem_id ?? '-'}`],
    ['CA', entry.snapshot?.derive?.ca ?? '-'], ['Revisao da copia', entry.source?.export_hash?.slice(0, 12) ?? '-']];
  const conditions = encounter()?.view?.conditions?.[entry.id];
  if (conditions?.length) facts.push(['Condicoes', conditions.join(', ')]);
  $('token-facts').replaceChildren(...facts.flatMap(([label, value]) => {
    const dt = document.createElement('dt'); dt.textContent = label;
    const dd = document.createElement('dd'); dd.textContent = String(value);
    return [dt, dd];
  }));
  const pools = Object.entries(entry.resources || {});
  $('token-resources').hidden = pools.length === 0;
  $('resource-facts').replaceChildren(...pools.flatMap(([id, pool]) => {
    const dt = document.createElement('dt'); dt.textContent = pool.nome || id;
    const dd = document.createElement('dd'); dd.textContent = `${pool.current} / ${pool.max}`;
    return [dt, dd];
  }));
  options($('resource-id'), pools.map(([id, pool]) => [id, pool.nome || id]));
  resourceBalance();
  options($('measure-target'), active.state.tokens.filter((other) => other.id !== entry.id).map((other) => [other.id, other.nome]));
  $('measure-result').textContent = '';
  $('token-warnings').replaceChildren(...(entry.rules?.warnings || ['Reimporte a ficha para obter as fontes de tags de combate.']).map((warning) => {
    const li = document.createElement('li'); li.textContent = warning; return li;
  }));
  const access = entry.snapshot?.acesso_magias;
  $('spell-access').hidden = access?.schema !== 1;
  const spells = Array.isArray(access?.magias) ? access.magias : [];
  $('spell-access-summary').textContent = `Magias da copia (${spells.length})`;
  $('spell-access-list').replaceChildren(...spells.map((spell) => {
    const li = document.createElement('li');
    const name = document.createElement('strong'); name.textContent = spell.nome;
    const status = spell.sempre_preparada === true ? 'Sempre preparada'
      : spell.preparada === true ? 'Preparada' : spell.preparada === false ? 'Nao preparada' : 'Preparo a confirmar';
    const metadata = document.createElement('div');
    metadata.textContent = `${spell.circulo === 0 ? 'Truque' : `Circulo ${spell.circulo}`} · ${status}`;
    const sources = document.createElement('small');
    sources.textContent = (spell.fontes || []).map((source) => source.fonte || source.origem || source.id_fonte).filter(Boolean).join(' · ');
    li.append(name, metadata, sources); return li;
  }));
  $('spell-access-warnings').replaceChildren(...(access?.avisos || []).map((warning) => {
    const li = document.createElement('li'); li.textContent = warning; return li;
  }));
  $('token-snapshot').textContent = JSON.stringify({snapshot: entry.snapshot, rules: entry.rules}, null, 2);
}
function resourceBalance() {
  const pool = token()?.resources?.[$('resource-id').value];
  $('resource-current').value = pool?.current ?? 0;
  $('resource-current').max = pool?.max ?? 0;
}
function options(select, entries, chosen) {
  const previous = chosen ?? select.value;
  select.replaceChildren(...entries.map(([value, label]) => {
    const option = document.createElement('option'); option.value = value; option.textContent = label;
    return option;
  }));
  if (entries.some(([value]) => value === previous)) select.value = previous;
}
function combatPanel() {
  const combat = encounter();
  const view = combat?.view;
  const tokens = active?.state.tokens || [];
  const byId = new Map(tokens.map((entry) => [entry.id, entry]));
  $('combat-status').textContent = view?.finished ? 'Combate finalizado' : fighting()
    ? (view?.current_actor ? `Vez de ${byId.get(view.current_actor)?.nome || '-'}${view.action_used ? ' · acao utilizada' : ''}` : 'Aguardando turno')
    : 'Sem combate ativo';
  $('start-combat').hidden = fighting();
  $('combat-controls').hidden = !fighting();
  $('combat-actions').hidden = !fighting();
  const walking = view?.movement?.[view?.current_actor];
  const scale = active?.state.board.movement?.cost_scale || 12;
  const movementReasons = {
    unknown_walk_speed: 'Deslocamento desconhecido: reimporte uma ficha com velocidade estruturada.',
    unsupported_flat_positions: 'Caminhada automatica exige tokens de uma celula no piso Z=0.',
    combat_finished: 'Combate finalizado.', not_current_actor: 'Aguarde o turno deste ator.',
    actor_not_living: 'Ator sem PV para caminhar.',
    active_condition: 'Condicao ativa: movimento exige adjudicacao manual nesta versao.',
    movement_exhausted: 'Deslocamento esgotado.',
    networkx_unavailable: 'Biblioteca de caminhos indisponivel no servidor.',
  };
  const balance = walking?.budget_units != null
    ? `${walking.remaining_units / scale} celulas restantes de ${walking.budget_units / scale}` : '';
  $('walk-balance').textContent = [balance, walking?.available ? '' : movementReasons[walking?.reason]
    || 'Sem turno ou deslocamento estruturado disponivel'].filter(Boolean).join(' · ');
  const actorPosition = byId.get(view?.current_actor);
  for (const axis of ['x', 'y', 'z']) $(`walk-${axis}`).value = actorPosition?.[axis] ?? 0;
  $('walk-x').max = (active?.state.board.width || 1) - 1;
  $('walk-y').max = (active?.state.board.height || 1) - 1;
  $('combat-engine-events').textContent = JSON.stringify(view?.events || [], null, 2);
  $('teams-list').replaceChildren(...tokens.map((entry) => {
    if (!teamChoices.has(entry.id)) teamChoices.set(entry.id, {included: entry.hp > 0 && Boolean(entry.rules), team: entry.source?.criatura_id ? 'B' : 'A'});
    const choice = teamChoices.get(entry.id);
    const row = document.createElement('div'); row.className = 'lab-team-row';
    const label = document.createElement('label'); label.className = 'lab-check';
    const included = document.createElement('input'); included.type = 'checkbox'; included.checked = choice.included;
    included.addEventListener('change', () => { choice.included = included.checked; });
    label.append(included, document.createTextNode(entry.nome));
    const select = document.createElement('select'); select.setAttribute('aria-label', `Equipe de ${entry.nome}`);
    options(select, [['A', 'Equipe A'], ['B', 'Equipe B']], choice.team);
    select.addEventListener('change', () => { choice.team = select.value; });
    row.append(label, select); return row;
  }));
  const participants = tokens.filter((entry) => entry.id in (view?.combatants || {}));
  const living = participants.filter((entry) => entry.hp > 0);
  options($('combat-actor'), living.map((entry) => [entry.id, entry.nome]), view?.current_actor || undefined);
  options($('combat-target'), living.map((entry) => [entry.id, entry.nome]));
  const actor = byId.get(view?.current_actor);
  options($('combat-action'), (actor?.rules?.actions || []).map((action) => [action.id, action.nome]));
  options($('attack-type'), (view?.damage_types || []).map((value) => [value, value]));
}
async function show(data) {
  active = data;
  if (!token()) selected = data.state.tokens[0]?.id ?? null;
  moveArmed = false;
  walkArmed = false; walkPlan = null;
  $('walk-preview').textContent = '';
  $('table-name').textContent = data.nome;
  $('table-revision').textContent = `r${data.revision}`;
  $('turn-number').textContent = `Turno ${data.state.turn}`;
  const presentation = data.state.presentation;
  const background = presentation?.background;
  $('map-url').value = background?.url || '';
  $('map-cell-px').value = background?.cell_px ?? 64;
  $('map-origin-x').value = background?.origin_x ?? 0;
  $('map-origin-y').value = background?.origin_y ?? 0;
  $('map-opacity').value = background?.opacity ?? 1;
  $('map-grid-opacity').value = presentation?.grid_opacity ?? 0.25;
  $('token-list').replaceChildren(...data.state.tokens.map((entry) => {
    const button = itemButton(entry.nome, () => { selected = entry.id; inspect(); showTokenSelection(); controls(); }, entry.id === selected);
    button.dataset.tokenId = entry.id;
    const hp = document.createElement('small'); hp.textContent = `${entry.hp} / ${entry.max_hp} PV`;
    button.append(hp); return button;
  }));
  $('event-list').replaceChildren(...data.state.events.slice(-20).reverse().map((event) => {
    const li = document.createElement('li');
    const labels = {import_character: 'Ficha importada', move_token: `Token movido para ${event.x}, ${event.y}, ${event.z}`,
      set_hp: `PV ajustados para ${event.hp}`, next_turn: 'Turno avancado', import_creature: 'Criatura importada',
      combat_start: 'Combate iniciado', combat_start_turn: 'Turno de combate iniciado', combat_end_turn: 'Turno de combate encerrado',
      combat_attack: `Ataque declarado · dano bruto ${event.damage}`, combat_heal: `Cura declarada ${event.amount}`, combat_end: 'Combate encerrado',
      configure_board: 'Terreno de teste atualizado', configure_presentation: 'Imagem e grade atualizadas', combat_move: `Caminhada para ${event.x}, ${event.y}, ${event.z}`};
    li.textContent = `r${event.revision ?? '-'} · ${labels[event.type] || event.message || event.type || 'Operacao registrada'}`;
    return li;
  }));
  inspect(); combatPanel(); controls();
  try {
    (await ensureBoard()).update(data.state, data.revision);
    $('board-empty').hidden = true;
  } catch (error) {
    $('board-empty').hidden = false;
    $('board-empty').textContent = 'Tabuleiro indisponivel';
    throw new Error(`Falha no visual 2D: ${error.message}`);
  }
  status('Sessao salva no laboratorio');
}
async function previewWalk(destination) {
  walkPlan = null; board?.clearPath(); $('walk-preview').textContent = ''; controls();
  const params = new URLSearchParams(destination);
  const data = await request(`${root.dataset.api}${active.id}/caminho/?${params}`);
  if (data.revision !== active.revision) {
    await load(active.id); throw new Error('A mesa mudou. Confira o destino novamente.');
  }
  walkPlan = {destination, path: data.path};
  board?.showPath(data.path);
  const scale = active.state.board.movement?.cost_scale || 12;
  $('walk-preview').textContent = `Custo: ${data.cost_units / scale} celulas`;
  status('Caminho calculado pelo servidor');
}
function showTokenSelection() {
  for (const button of $('token-list').children) button.dataset.selected = String(button.dataset.tokenId === selected);
}
async function load(id) {
  await show(await request(`${root.dataset.api}${id}/`));
  await sessions();
}
async function command(type, payload) {
  const id = active.id;
  try {
    const data = await request(`${root.dataset.api}${id}/comandos/`, {method: 'POST', body: JSON.stringify({
      command_id: crypto.randomUUID(), expected_revision: active.revision, type, ...payload,
    })});
    await show(data);
  } catch (error) {
    if (error.status === 409) {
      await load(id);
      throw new Error(error.code === 'revision_conflict' ? 'A sessao mudou em outra aba. Estado atualizado; confira antes de repetir.' : error.message);
    }
    throw error;
  }
}
$('create-session').addEventListener('submit', (event) => {
  event.preventDefault();
  operation(async () => {
    const data = await request(root.dataset.api, {method: 'POST', body: JSON.stringify({nome: $('session-name').value})});
    await show(data); await sessions();
  });
});
$('import-character').addEventListener('submit', (event) => {
  event.preventDefault();
  operation(() => command('import_character', {personagem_id: Number($('character-id').value)}));
});
$('import-creature').addEventListener('submit', (event) => {
  event.preventDefault(); operation(() => command('import_creature', {criatura_id: Number($('creature-id').value)}));
});
$('start-combat').addEventListener('submit', (event) => {
  event.preventDefault();
  const teams = Object.fromEntries((active?.state.tokens || []).filter((entry) => teamChoices.get(entry.id)?.included)
    .map((entry) => [entry.id, teamChoices.get(entry.id).team]));
  operation(() => command('combat_start', {teams}));
});
$('start-combat-turn').addEventListener('click', () => operation(() => command('combat_start_turn', {actor_id: $('combat-actor').value})));
$('end-combat-turn').addEventListener('click', () => operation(() => command('combat_end_turn', {})));
$('end-combat').addEventListener('click', () => operation(() => command('combat_end', {})));
$('walk-form').addEventListener('submit', (event) => {
  event.preventDefault(); operation(() => previewWalk(Object.fromEntries(['x','y','z'].map((axis) => [axis, Number($(`walk-${axis}`).value)]))));
});
$('point-walk').addEventListener('click', () => { walkArmed = !walkArmed; moveArmed = false; controls(); });
$('confirm-walk').addEventListener('click', () => { if (walkPlan) operation(() => command('combat_move', walkPlan.destination)); });
for (const axis of ['x','y','z']) $(`walk-${axis}`).addEventListener('input', () => {
  walkPlan = null; board?.clearPath(); $('walk-preview').textContent = ''; controls();
});
$('paint-terrain').addEventListener('submit', (event) => {
  event.preventDefault();
  const x = Number($('terrain-x').value), y = Number($('terrain-y').value), kind = $('terrain-kind').value;
  const blocked = (active.state.board.blocked_cells || []).filter((cell) => cell.x !== x || cell.y !== y);
  const terrain = {...active.state.board.terrain_cells};
  delete terrain[`${x},${y}`];
  if (kind === 'blocked') blocked.push({x,y});
  if (kind === 'difficult') terrain[`${x},${y}`] = kind;
  operation(() => command('configure_board', {blocked_cells: blocked, terrain_cells: terrain}));
});
$('combat-attack').addEventListener('submit', (event) => {
  event.preventDefault(); operation(() => command('combat_attack', {target_id: $('combat-target').value,
    action_id: $('combat-action').value, hit: $('attack-hit').checked,
    damage: Number($('attack-damage').value), damage_type: $('attack-type').value.trim()}));
});
$('attack-hit').addEventListener('change', () => { if (!$('attack-hit').checked) $('attack-damage').value = '0'; });
$('combat-heal').addEventListener('submit', (event) => {
  event.preventDefault(); operation(() => command('combat_heal', {target_id: $('combat-target').value, amount: Number($('heal-amount').value)}));
});
$('set-hp').addEventListener('submit', (event) => {
  event.preventDefault();
  operation(() => command('set_hp', {token_id: selected, hp: Number($('token-hp').value)}));
});
$('resource-id').addEventListener('change', resourceBalance);
$('configure-map').addEventListener('submit', (event) => {
  event.preventDefault();
  const url = $('map-url').value.trim();
  operation(() => command('configure_presentation', {presentation: {
    background: url ? {url, cell_px:Number($('map-cell-px').value),
      origin_x:Number($('map-origin-x').value), origin_y:Number($('map-origin-y').value),
      opacity:Number($('map-opacity').value)} : null,
    grid_opacity:Number($('map-grid-opacity').value),
  }}));
});
$('clear-map').addEventListener('click', () => operation(() => command('configure_presentation', {
  presentation:{background:null,grid_opacity:Number($('map-grid-opacity').value)},
})));
$('set-resource').addEventListener('submit', (event) => {
  event.preventDefault(); operation(() => command('set_resource', {token_id: selected,
    resource_id: $('resource-id').value, current: Number($('resource-current').value)}));
});
$('measure-distance').addEventListener('submit', (event) => {
  event.preventDefault(); operation(async () => {
    const params = new URLSearchParams({origin_id: selected, target_id: $('measure-target').value});
    const data = await request(`${root.dataset.api}${active.id}/medir/?${params}`);
    const format = new Intl.NumberFormat('pt-BR', {maximumFractionDigits: 3});
    $('measure-result').textContent = `${format.format(data.meters)} m · ${format.format(data.cells)} celulas · ${data.metric}`;
    status('Distancia medida entre tokens; caminho e visibilidade nao avaliados');
  });
});
$('move-token').addEventListener('submit', (event) => {
  event.preventDefault();
  operation(() => command('move_token', {token_id: selected, ...Object.fromEntries(['x', 'y', 'z'].map((axis) => [axis, Number($(`token-${axis}`).value)]))}));
});
$('move-on-board').addEventListener('click', () => { moveArmed = !moveArmed; controls(); });
$('next-turn').addEventListener('click', () => operation(() => command('next_turn', {})));
$('refresh-session').addEventListener('click', () => operation(() => load(active.id)));
$('frame-board').addEventListener('click', () => board?.frame());
$('zoom-in').addEventListener('click', () => board?.zoom(1 / 1.25));
$('zoom-out').addEventListener('click', () => board?.zoom(1.25));
window.addEventListener('keydown', (event) => { if (event.key === 'Escape') { moveArmed = false; walkArmed = false; controls(); } });
window.addEventListener('pagehide', (event) => { if (!event.persisted) board?.dispose(); });
operation(async () => {
  const list = await sessions();
  if (list.length) await load(list[0].id);
  else status('Nenhuma sessao criada');
});
