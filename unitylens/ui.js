(function () {
  'use strict';
  const CORE = window.UnityLensCore;
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const TONE_KO = { data: '데이터', system: '시스템', action: '액션', ui: 'UI', plain: '일반' };

  const NOTES = {
    BulletMove: '총알 프리팹에 붙는 최소 구성입니다. `Start`에서 `Destroy(gameObject, destroyTime)`으로 수명을 예약하고, `Update`마다 `transform.Translate(speed * Time.deltaTime * Vector3.up)`로 **로컬 +Y 방향**으로 이동합니다. `speed`는 Inspector에서 조절하는 직렬화 값(기본 10)이고, `destroyTime`은 기본값이 없어 Inspector에서 반드시 채워야 합니다(0이면 스폰 즉시 소멸). Translate는 오브젝트의 회전을 반영하므로, 총알을 발사 방향으로 회전시켜 스폰하면 그 방향으로 날아갑니다.',
    HomingBullet: '매 프레임 `target`을 검사해 없으면 `FindNearestEnemy()`로 **"Enemy" 태그 전체를 다시 검색**합니다. 타겟이 있으면 정규화한 방향을 `transform.position`에 직접 더하고(관성 없음), 없으면 위로 직진합니다. 구조는 단순하지만 적이 없을 때 `Update`마다 `FindGameObjectsWithTag`가 호출되어 GC·CPU 부담이 커집니다. 재탐색 쿨다운(0.2초)이나 적 등록 리스트로 바꾸는 편이 좋습니다. `target`이 파괴되면 Unity의 fake-null 덕분에 `target == null`이 참이 되어 재탐색으로 이어집니다.',
    IntroButton: 'EventTrigger 없이 `IPointerEnterHandler`/`IPointerExitHandler`를 직접 구현한 버튼입니다. DOTween으로 1.2배 ↔ 1.0배 스케일 트윈을 걸고, `DOComplete()`로 이전 트윈을 즉시 끝내 중첩을 막습니다. `originalX`에 시작 X 좌표를 저장하지만 **이후 읽는 곳이 없어 죽은 코드**입니다. `EditScene` 토글, `LoadingSceneManager.LoadScene("1_SlectScene")` 씬 이동, `Application.Quit()` + 에디터에서는 `isPlaying = false`로 재생 정지까지 처리합니다.',
    KeyManager: 'Input System의 `Key` 열거형으로 **리바인딩 가능한 키맵**을 만드는 싱글턴입니다. 정적 `Instance` 프로퍼티가 없으면 `FindFirstObjectByType`으로 찾고, 그래도 없으면 `KeyManager` 오브젝트를 만들어 `DontDestroyOnLoad`로 유지합니다. `Awake`에서는 중복 인스턴스를 파괴합니다. `ChangeKey`는 코루틴을 띄워 `anyKey.wasPressedThisFrame`을 기다린 뒤 `Enum.GetValues(typeof(Key))`를 순회해 눌린 키를 찾아 `keys`에 덮어쓰고 콜백을 호출합니다. `keys`가 public이라 `PlayerMove`/`PlayerShooting`이 `TryGetValue`로 읽고, 없으면 기본 키로 폴백합니다.',
    LoadingSceneManager: '정적 `nextSceneName`에 목표 씬을 저장하고 **"0.5_Loading" 씬으로 먼저 이동**합니다. 그 씬의 `Start`에서 `LoadSceneAsync`를 시작하고 `allowSceneActivation = false`로 90%에서 멈춰 둡니다. `op.progress / 0.9`를 Slider와 TMP 텍스트에 반영하고, 90% 이후에는 `fadeOrMinDelay` 동안 `Mathf.Lerp`로 게이지를 1까지 채운 뒤에야 씬 활성화를 허용합니다. 로딩이 너무 빨라 화면이 튀는 것을 막는 연출 장치입니다. `nextSceneName`이 비어 있으면 LogError 후 return합니다.',
    PlayerData: '`ScriptableObject` 데이터 컨테이너입니다. `CreateAssetMenu`로 Project 창에서 `.asset` 파일을 만들 수 있습니다. 이름·ID·체력·속도·아이콘·애니메이션 스프라이트·설명을 담고, `PlayerMove`가 `SelectScene.SelectedData`를 통해 이 값을 읽습니다. `chddkf`는 `GameObject` 필드인데 이름이 오타로 보이고 코드 어디에서도 참조되지 않습니다.',
    PlayerMove: '`SelectScene.SelectedData`(외부 정적 참조)에서 `playerSpeed`를 읽어 `speed = playerSpeed * 5`로 만들고, `playerIcon`을 `SpriteRenderer.sprite`에 적용합니다. `Update`에서는 키보드(`KeyManager`의 바인딩, 기본 WASD)와 게임패드 스틱·DPad를 합산해 방향을 만들고, 대각선일 때 정규화한 뒤 이동합니다. 마지막에 카메라 뷰포트 좌표로 위치를 Clamp해 화면 밖으로 나가지 못하게 합니다. **선택 데이터가 없으면 `speed = 0`이라 캐릭터가 움직이지 않습니다** — 기본 속도 폴백이 필요합니다.',
    PlayerShooting: '매 프레임 `KeyManager`에서 Attack/Ultimate 키를 조회하고(없으면 Z/X) 공격을 처리합니다. 기본 공격은 `isPressed` + `nextFireTime` 쿨다운으로 연사하고, 필살기는 `wasPressedThisFrame`으로 단발 발사합니다. 스폰 위치는 `firePoint`가 있으면 그곳, 없으면 자기 위치입니다. `homingbulletPrefab`이 비어 있으면 일반 총알로 대체하고 경고를 남기는 방어 코드가 들어 있습니다.',
    TmiReader: '`tmiText` 배열에서 `Random.Range(0, Length)`로 한 항목을 골라 TMP에 `TMI : ...` 형식으로 출력합니다. 배열이 비어 있으면 `Random.Range(0, 0)`이 0을 반환해 `[0]` 접근에서 **IndexOutOfRangeException**이 납니다. `Start`에서 한 번만 실행되므로 씬마다 한 줄이 랜덤으로 보입니다.',
    TmiText: 'TMI 한 줄을 담는 `ScriptableObject`입니다. 다만 `CreateAssetMenu`의 `fileName`이 **"PlayerData"로 PlayerData와 중복**입니다. 에셋을 만들 때 파일명이 겹치므로 `TmiData` 등으로 바꾸는 편이 안전합니다.'
  };

  const state = { data: null, sources: [], selected: null, tab: 'overview', varSel: null, varScope: 'class', q: '', vq: '' };

  /* ---------- helpers ---------- */
  function primaryRole(t) { return (t.roles && t.roles[0]) || { name: t.kind, tone: 'plain', evidence: [] }; }
  function readCount(f) { return f.usages.filter(u => u.rw !== 'write').length; }
  function writeCount(f) { return f.usages.filter(u => u.rw !== 'read').length; }
  function getType(name) { return state.data.byName.get(name); }
  function selType() { return state.selected ? getType(state.selected) : null; }
  function allVars() {
    const out = [];
    state.data.types.forEach(t => {
      t.fields.forEach(f => out.push({ key: t.name + '.' + f.name, owner: t, v: f, kind: 'field' }));
      t.props.forEach(p => out.push({ key: t.name + '.' + p.name, owner: t, v: p, kind: 'property' }));
    });
    return out;
  }
  function findVar(key) { return allVars().find(x => x.key === key) || null; }
  function ensureVar() {
    const t = selType();
    if (!t) { state.varSel = null; return; }
    if (state.varSel) {
      const f = findVar(state.varSel);
      if (f && (state.varScope === 'all' || f.owner.name === t.name)) return;
    }
    const first = t.fields[0] || t.props[0];
    state.varSel = first ? t.name + '.' + first.name : null;
  }
  function allIssues() {
    const out = [];
    state.data.types.forEach(t => t.issues.forEach(i => out.push(Object.assign({ type: t.name, file: t.file }, i))));
    const rank = { high: 0, medium: 1, low: 2 };
    return out.sort((a, b) => rank[a.sev] - rank[b.sev]);
  }
  function sigOf(t) {
    const mods = t.modifiers.length ? t.modifiers.join(' ') + ' ' : '';
    const bases = t.bases.length ? ' : ' + t.bases.join(', ') : '';
    return esc(mods) + '<span class="kw">' + esc(t.kind) + '</span> <span class="nm">' + esc(t.name) + '</span>' + esc(bases);
  }
  function toast(msg) {
    const el = $('#toast');
    el.textContent = msg;
    el.classList.add('on');
    clearTimeout(el._t);
    el._t = setTimeout(() => el.classList.remove('on'), 2400);
  }

  /* ---------- boot ---------- */
  function boot() {
    const raw = JSON.parse($('#samples').textContent);
    state.sources = raw.sources.slice();
    if (window.__START_TAB__) state.tab = window.__START_TAB__;
    if (window.__START_TYPE__) state.selected = window.__START_TYPE__;
    const hash = decodeURIComponent((location.hash || '').replace(/^#/, ''));
    if (hash) {
      const parts = hash.split('/');
      if (['overview', 'class', 'vars', 'graph', 'source'].includes(parts[0])) state.tab = parts[0];
      if (parts[1]) state.selected = parts[1];
    }
    reanalyze();
    bindChrome();
    window.__exportMd = buildMd;
    window.addEventListener('hashchange', () => {
      const h = decodeURIComponent((location.hash || '').replace(/^#/, '')).split('/');
      if (h[1] && state.data.byName.has(h[1]) && h[1] !== state.selected) selectType(h[1]);
      if (h[0] && h[0] !== state.tab) setTab(h[0]);
    });
  }
  function syncHash() {
    try { history.replaceState(null, '', '#' + state.tab + '/' + (state.selected || '')); } catch (e) {}
  }
  function reanalyze() {
    state.data = CORE.analyzeSources(state.sources);
    if (!state.selected || !state.data.byName.has(state.selected)) {
      state.selected = state.data.types.length ? state.data.types[0].name : null;
    }
    ensureVar();
    renderAll();
  }
  function renderAll() {
    renderMeta();
    renderRail();
    renderOverview();
    renderClass();
    renderVars();
    renderGraph();
    renderSource();
    setTab(state.tab, true);
    window.__UL = { data: state.data, state };
  }

  function bindChrome() {
    $('#tabs').addEventListener('click', e => {
      const b = e.target.closest('button[data-tab]');
      if (b) setTab(b.dataset.tab);
    });
    $('#search').addEventListener('input', e => { state.q = e.target.value.toLowerCase(); renderRail(); });
    $('#btnExport').addEventListener('click', exportMd);
    $('#btnAdd').addEventListener('click', () => { $('#modal').hidden = false; $('#codeInput').focus(); });
    $('#mClose').addEventListener('click', () => { $('#modal').hidden = true; });
    $('#modal').addEventListener('click', e => { if (e.target.id === 'modal') $('#modal').hidden = true; });
    $('#mRun').addEventListener('click', () => {
      const code = $('#codeInput').value;
      if (!code.trim()) { toast('코드를 붙여넣어 주세요.'); return; }
      let name = ($('#nameInput').value || '').trim();
      if (!name) name = guessName(code);
      state.sources.push({ name, code });
      $('#modal').hidden = true; $('#codeInput').value = ''; $('#nameInput').value = '';
      reanalyze();
      toast(name + ' 분석 완료');
    });
    $('#mFile').addEventListener('change', e => {
      const files = Array.from(e.target.files || []);
      if (!files.length) return;
      let left = files.length;
      files.forEach(f => {
        const r = new FileReader();
        r.onload = () => {
          state.sources.push({ name: f.name, code: String(r.result || '') });
          if (--left === 0) { $('#modal').hidden = true; reanalyze(); toast(files.length + '개 파일 추가'); }
        };
        r.readAsText(f);
      });
      e.target.value = '';
    });
    document.addEventListener('click', e => {
      const t = e.target.closest('[data-type]');
      if (t) { selectType(t.dataset.type); return; }
      const v = e.target.closest('[data-var]');
      if (v) { state.varSel = v.dataset.var; state.varScope = v.dataset.scope || state.varScope; renderVars(); return; }
      const j = e.target.closest('[data-goto]');
      if (j) { selectType(j.dataset.goto); return; }
    });
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape') $('#modal').hidden = true;
      if (e.key === '/' && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') { e.preventDefault(); $('#search').focus(); }
    });
  }
  function guessName(code) {
    const m = code.match(/\b(?:class|struct|interface|enum)\s+([A-Za-z_][A-Za-z0-9_]*)/);
    return (m ? m[1] : 'Custom') + '.cs';
  }
  function setTab(tab, silent) {
    state.tab = tab;
    $$('#tabs button').forEach(b => b.classList.toggle('on', b.dataset.tab === tab));
    $$('.view').forEach(v => v.classList.toggle('on', v.id === 'v-' + tab));
    if (!silent) $('.views').scrollTop = 0;
    syncHash();
  }
  function selectType(name, tab) {
    if (!state.data.byName.has(name)) return;
    state.selected = name;
    if (state.varScope === 'class') state.varSel = null;
    ensureVar();
    renderMeta(); renderRail(); renderClass(); renderVars(); renderSource(); renderGraph();
    syncHash();
    if (tab) setTab(tab);
  }

  /* ---------- chrome ---------- */
  function renderMeta() {
    const d = state.data;
    const comps = d.types.filter(t => t.base === 'MonoBehaviour' || (t.base && d.byName.has(t.base))).length;
    const assets = d.types.filter(t => t.base === 'ScriptableObject').length;
    const tracked = allVars().filter(x => x.v.usages.length).length;
    $('#headerMeta').innerHTML =
      '<div class="hm"><b>' + d.files.length + '</b><span>scripts</span></div>' +
      '<div class="hm"><b>' + d.types.length + '</b><span>types</span></div>' +
      '<div class="hm"><b>' + tracked + '</b><span>vars traced</span></div>' +
      '<div class="hm"><b>' + allIssues().length + '</b><span>findings</span></div>';
    // rail foot
    const foot = $('.rail-foot');
    if (foot) foot.innerHTML = '<span class="dot"></span>규칙 기반 정적 분석 · 브라우저에서만 실행';
  }

  function renderRail() {
    const q = state.q;
    const items = state.data.types.filter(t => !q || (t.name + ' ' + t.file + ' ' + primaryRole(t).name).toLowerCase().includes(q));
    if (!items.length) {
      $('#railList').innerHTML = '<div class="empty">일치하는 타입이 없습니다.</div>';
      return;
    }
    $('#railList').innerHTML = items.map(t => {
      const role = primaryRole(t);
      return '<button class="ritem' + (t.name === state.selected ? ' on' : '') + '" data-type="' + esc(t.name) + '">' +
        '<span class="rn">' + esc(t.name) + '</span>' +
        '<span class="rb">' + esc(t.kind) + '</span>' +
        '<span class="rr"><i class="tick"></i>' + esc(role.name) + '<span class="cnt">' + t.fields.length + 'v</span></span>' +
        '</button>';
    }).join('');
  }

  /* ---------- overview ---------- */
  function renderOverview() {
    const d = state.data;
    const comps = d.types.filter(t => t.base === 'MonoBehaviour' || (t.base && d.byName.has(t.base))).length;
    const assets = d.types.filter(t => t.base === 'ScriptableObject').length;
    const tracked = allVars().filter(x => x.v.usages.length).length;
    const issues = allIssues();
    const high = issues.filter(i => i.sev === 'high').length;
    const inputs = d.types.filter(t => t.methods.some(m => /Keyboard|Gamepad/.test(m.usages.map(u => u.code).join('')))).length;

    let html = '';
    html += '<div class="hero"><svg class="rings" viewBox="0 0 420 420" aria-hidden="true">' +
      '<circle cx="210" cy="210" r="198"></circle><circle cx="210" cy="210" r="150"></circle><circle cx="210" cy="210" r="104"></circle><circle cx="210" cy="210" r="58"></circle>' +
      '<line class="beam" x1="210" y1="0" x2="210" y2="420"></line><line class="beam" x1="0" y1="210" x2="420" y2="210"></line></svg>' +
      '<div><div class="hero-num"><span class="n">' + d.types.length + '</span><span class="u">types decoded</span></div>' +
      '<h2>코드를 읽고, <em>상속과 변수의 흐름</em>을 그립니다.</h2>' +
      '<p class="lede">' + d.files.length + '개 스크립트에서 ' + d.types.length + '개 타입을 찾아 베이스 타입·인터페이스·역할을 판정하고, 필드가 어느 메서드에서 읽히고 쓰이는지 줄 번호까지 추적했습니다. 왼쪽에서 타입을 고르면 해설과 추적 결과가 바뀝니다.</p></div>' +
      '<div class="hero-side">' +
      '<div class="hstat gold"><b>' + comps + '</b><span>components</span></div>' +
      '<div class="hstat violet"><b>' + assets + '</b><span>data assets</span></div>' +
      '<div class="hstat teal"><b>' + tracked + '</b><span>vars traced</span></div>' +
      '<div class="hstat rust"><b>' + high + '</b><span>high findings</span></div>' +
      '</div></div>';

    html += '<div class="section-head"><h3>타입 지도</h3><span class="hint">행을 클릭하면 상세 해설로 이동</span></div>';
    html += '<div class="grid2"><div class="card"><div class="card-h"><h3>상속 · 역할</h3><span class="eyebrow">' + d.types.length + ' types</span></div><table class="t"><thead><tr><th>타입</th><th>상속 / 구현</th><th>역할</th><th>변수</th><th>이슈</th></tr></thead><tbody>' +
      d.types.map(t => {
        const r = primaryRole(t);
        return '<tr class="click" data-type="' + esc(t.name) + '"><td class="name">' + esc(t.name) + '</td><td><span class="ty">' + esc(t.base || '—') + '</span>' + (t.interfaces.length ? ' <span class="muted">+' + t.interfaces.length + ' I/F</span>' : '') + '</td><td><span class="chip tone-' + r.tone + '">' + esc(r.name) + '</span></td><td class="tiny">' + (t.fields.length + t.props.length) + '</td><td class="tiny">' + (t.issues.length ? '<span style="color:var(--write)">' + t.issues.length + '</span>' : '—') + '</td></tr>';
      }).join('') + '</tbody></table></div>';

    html += '<div class="stack"><div class="card"><div class="card-h"><h3>발견된 이슈</h3><span class="eyebrow">' + issues.length + ' findings</span></div>' +
      (issues.length ? issues.slice(0, 6).map(i => issueHtml(i, true)).join('') : '<p class="muted-line">발견된 이상 징후가 없습니다.</p>') +
      (issues.length > 6 ? '<p class="muted-line" style="margin-top:10px"><span class="jump" data-type="' + esc(issues[6].type) + '">나머지 ' + (issues.length - 6) + '건은 각 클래스 상세에…</span></p>' : '') +
      '</div>';
    html += '<div class="card"><div class="card-h"><h3>기준 타입 분포</h3><span class="eyebrow">inheritance</span></div>' + baseBars() + '</div></div></div>';

    html += '<div class="section-head"><h3>해석 커버리지</h3><span class="hint">파일 · 직렬화 · 입력</span></div>';
    html += '<div class="grid2b"><div class="card"><div class="card-h"><h3>파이프라인</h3><span class="eyebrow">scan</span></div>' +
      '<div class="kv"><span>스크립트</span><b>' + d.files.length + '개</b></div>' +
      '<div class="kv"><span>파일명</span><b style="font-weight:400;font-size:11px;color:var(--dim)">' + d.files.slice(0, 4).map(f => esc(f.name)).join(' · ') + (d.files.length > 4 ? ' 외 ' + (d.files.length - 4) : '') + '</b></div>' +
      '<div class="kv"><span>직렬화 필드</span><b>' + d.types.reduce((a, t) => a + t.fields.filter(f => f.isSerialized).length, 0) + '개</b></div>' +
      '<div class="kv"><span>입력 사용</span><b>' + inputs + '개 타입</b></div>' +
      '<div class="kv"><span>추적된 변수</span><b>' + tracked + ' / ' + allVars().length + '</b></div>' +
      '</div>';
    html += '<div class="card"><div class="card-h"><h3>파일 밖 참조</h3><span class="eyebrow">unresolved</span></div>' +
      (d.unresolved.length ? d.unresolved.map(u => '<div class="kv"><span>미해석</span><b>' + esc(u.name) + '</b><span style="margin-left:auto">' + esc(u.usedBy) + ' · L' + u.line + '</span></div>').join('') + '<p class="muted-line" style="margin-top:10px;font-size:11px">스캔한 파일에 정의가 없어 흐름을 끝까지 따라갈 수 없는 타입입니다. 파일을 추가하면 연결됩니다.</p>' : '<p class="muted-line">모든 외부 참조가 해석되었습니다.</p>') +
      '</div></div>';

    $('#v-overview').innerHTML = html;
  }

  function baseBars() {
    const counts = {};
    state.data.types.forEach(t => {
      const k = t.base || (t.kind === 'enum' ? 'enum' : '없음');
      counts[k] = (counts[k] || 0) + 1;
    });
    const max = Math.max.apply(null, Object.values(counts).concat([1]));
    return Object.keys(counts).sort((a, b) => counts[b] - counts[a]).map(k =>
      '<div class="bar-row"><span class="lbl">' + esc(k) + '</span><div class="bar"><i style="width:' + Math.round(counts[k] / max * 100) + '%"></i></div><span class="v">' + counts[k] + '</span></div>'
    ).join('');
  }

  function issueHtml(i, withType) {
    return '<div class="issue ' + i.sev + '"><div class="sev"></div><div><h4>' + esc(i.title) + '</h4><p>' + esc(i.detail) + '</p>' +
      '<div class="where">' + (withType ? '<span class="jump" data-type="' + esc(i.type) + '">' + esc(i.type) + '</span> · ' : '') + esc(i.file) + (i.evidence ? ' · ' + esc(i.evidence) : '') + '</div></div></div>';
  }

  /* ---------- class view ---------- */
  function renderClass() {
    const t = selType();
    if (!t) { $('#v-class').innerHTML = '<div class="empty">분석된 타입이 없습니다.</div>'; return; }
    const role = primaryRole(t);
    const note = NOTES[t.name];
    const lifeOrder = ['Awake', 'OnEnable', 'Start', 'FixedUpdate', 'Update', 'LateUpdate', 'OnDisable', 'OnDestroy', 'OnApplicationQuit'];
    const life = t.methods.filter(m => m.isLifecycle).sort((a, b) => {
      const ia = lifeOrder.indexOf(a.name), ib = lifeOrder.indexOf(b.name);
      return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
    });
    const locals = t.methods.filter(m => m.locals.length);

    let html = '<div class="class-head"><div class="ttl"><h2>' + esc(t.name) + ' <span class="chip tone-' + role.tone + '">' + esc(role.name) + '</span></h2>' +
      '<div class="sub"><span class="filetag">' + esc(t.file) + ' · L' + t.startLine + '–' + t.endLine + ' · ' + t.loc + ' lines</span>' +
      (t.base ? '<span class="chip base">' + esc(t.base) + '</span>' : '') +
      t.interfaces.map(i => '<span class="chip iface">' + esc(i) + '</span>').join('') +
      t.attrs.map(a => '<span class="chip attr">[' + esc(a) + ']</span>').join('') +
      '</div><div class="sig">' + sigOf(t) + '</div></div></div>';

    html += '<div class="grid2"><div class="stack">';
    html += '<div class="card"><div class="card-h"><h3>AI 해설</h3><span class="eyebrow">' + (note ? 'curated · 이 샘플 전용' : 'generated from structure') + '</span></div>';
    if (note) {
      html += note.split('\n').map(p => '<p class="muted-line" style="margin-bottom:10px">' + mdInline(p) + '</p>').join('');
    } else {
      html += t.narrative.map(p => '<p class="muted-line" style="margin-bottom:10px">' + mdInline(p) + '</p>').join('');
    }
    html += '<hr class="sep"><p class="faint" style="font-size:10.5px">해설은 파싱 결과(상속·메서드·변수 사용)를 근거로 작성됩니다. 괄호 안 수치는 실제 사용 횟수입니다.</p></div>';

    if (life.length) {
      html += '<div class="card"><div class="card-h"><h3>생명주기</h3><span class="eyebrow">unity messages</span></div><div class="timeline">' +
        life.map(m => '<div class="tl"><h4>' + esc(m.name) + '() <span class="ln">L' + m.line + ' · ' + esc(m.modifiers.join(' ') || 'private') + '</span></h4><p>' + (m.usages.length ? '이 안에서 ' + m.usages.map(u => '<code>' + esc(u.member) + '</code> ' + (u.rw === 'write' ? '쓰기' : u.rw === 'readwrite' ? '읽기+쓰기' : '읽기')).join(', ') + ' · ' + m.locals.length + '개 지역 변수' : '멤버 사용 없음 · ' + m.locals.length + '개 지역 변수') + '</p></div>').join('') +
        '</div></div>';
    }

    if (t.fields.length) {
      html += '<div class="card"><div class="card-h"><h3>필드</h3><span class="eyebrow">' + t.fields.length + ' fields · ' + t.stats.serialized + ' serialized</span></div>' +
        t.fields.map(f => '<div class="field-line rowlink" data-var="' + esc(t.name + '.' + f.name) + '" data-scope="class"><div><div class="fl-name">' + esc(f.name) + '<span class="fl-ty">' + esc(f.type) + '</span>' +
          (f.isSerialized ? '<span class="chip serialized">serialized</span>' : '') + (f.isStatic ? '<span class="chip">static</span>' : '') + '</div>' +
          '<div class="fl-ty" style="margin-top:2px">L' + f.line + (f.init ? ' · = ' + esc(f.init.length > 60 ? f.init.slice(0, 60) + '…' : f.init) : ' · Inspector 값') + '</div></div>' +
          '<div class="fl-meta"><span class="pill read">r ' + readCount(f) + '</span><span class="pill write">w ' + writeCount(f) + '</span></div></div>').join('') +
        '</div>';
    }

    if (t.props.length) {
      html += '<div class="card"><div class="card-h"><h3>프로퍼티</h3><span class="eyebrow">' + t.props.length + '</span></div>' +
        t.props.map(p => '<div class="field-line rowlink" data-var="' + esc(t.name + '.' + p.name) + '" data-scope="class"><div><div class="fl-name">' + esc(p.name) + '<span class="fl-ty">' + esc(p.type) + '</span></div><div class="fl-ty" style="margin-top:2px">L' + p.line + ' · ' + esc(p.modifiers.join(' ')) + '</div></div><div class="fl-meta"><span class="pill read">r ' + readCount(p) + '</span></div></div>').join('') +
        '</div>';
    }

    if (t.methods.length) {
      html += '<div class="card"><div class="card-h"><h3>메서드</h3><span class="eyebrow">' + t.methods.length + '</span></div><table class="t"><thead><tr><th>이름</th><th>매개변수</th><th>사용</th><th>라인</th></tr></thead><tbody>' +
        t.methods.map(m => '<tr><td class="name">' + esc(m.name) + (m.isLifecycle ? ' <span class="pill">unity</span>' : '') + '</td><td><span class="ty">' + (m.params.length ? esc(m.params.map(p => p.type + ' ' + p.name).join(', ')) : '—') + '</span></td><td class="tiny">' + m.usages.length + '</td><td class="tiny">' + m.line + '</td></tr>').join('') +
        '</tbody></table></div>';
    }

    if (locals.length) {
      html += '<div class="card"><div class="card-h"><h3>지역 변수</h3><span class="eyebrow">method scope</span></div>' +
        locals.map(m => '<div class="kv" style="align-items:flex-start"><span style="min-width:70px">' + esc(m.name) + '</span><b style="font-weight:400">' + m.locals.map(l => '<span class="chip">' + esc(l.type) + ' ' + esc(l.name) + '</span>').join(' ') + '</b></div>').join('') +
        '</div>';
    }
    html += '</div><div class="stack">';

    html += '<div class="card"><div class="card-h"><h3>판정된 역할</h3><span class="eyebrow">' + t.roles.length + ' signals</span></div>' +
      t.roles.map((r, idx) => '<div class="role-card"><div class="rc-badge">' + (idx + 1) + '</div><div><h4>' + esc(r.name) + ' <span class="pill">' + TONE_KO[r.tone] + '</span></h4><ul>' + r.evidence.map(e => '<li>' + mdInline(e) + '</li>').join('') + '</ul></div></div>').join('') +
      '</div>';

    html += '<div class="card"><div class="card-h"><h3>구조 수치</h3><span class="eyebrow">metrics</span></div>' +
      '<div class="kv"><span>베이스</span><b>' + esc(t.base || '—') + '</b></div>' +
      '<div class="kv"><span>필드</span><b>' + t.fields.length + '개 (직렬화 ' + t.stats.serialized + ')</b></div>' +
      '<div class="kv"><span>메서드</span><b>' + t.methods.length + '개</b></div>' +
      '<div class="kv"><span>읽기 / 쓰기</span><b style="color:var(--read)">' + t.stats.reads + '</b> <span style="min-width:0;color:var(--faint)">/</span> <b style="color:var(--write)">' + t.stats.writes + '</b></div>' +
      '<div class="kv"><span>외부 참조</span><b>' + t.externals.length + '건</b></div>' +
      '</div>';

    html += '<div class="card"><div class="card-h"><h3>이 클래스의 이슈</h3><span class="eyebrow">' + t.issues.length + '</span></div>' +
      (t.issues.length ? t.issues.map(i => issueHtml(i, false)).join('') : '<p class="muted-line">규칙에 걸린 항목이 없습니다.</p>') + '</div>';

    if (t.externals.length) {
      html += '<div class="card"><div class="card-h"><h3>외부 참조</h3><span class="eyebrow">cross-file</span></div>' +
        t.externals.map(e => '<div class="kv"><span>' + esc(e.method) + '</span><b>' + esc(e.target) + '.' + esc(e.member) + '</b><span style="margin-left:auto;min-width:0">L' + e.line + '</span></div>').join('') +
        '</div>';
    }
    if (t.kind === 'enum') {
      html += '<div class="card"><div class="card-h"><h3>상수</h3><span class="eyebrow">members</span></div>' +
        t.enumNames.map(n => '<span class="chip" style="margin:0 4px 4px 0">' + esc(n) + '</span>').join('') + '</div>';
    }

    html += '</div></div>';
    $('#v-class').innerHTML = html;
  }

  /* ---------- variables ---------- */
  function renderVars() {
    const t = selType();
    let pool;
    if (state.varScope === 'all') pool = allVars();
    else pool = allVars().filter(x => x.owner.name === (t && t.name));
    if (state.vq) pool = pool.filter(x => (x.owner.name + '.' + x.v.name + ' ' + x.v.type).toLowerCase().includes(state.vq));
    if (!state.varSel || !findVar(state.varSel)) {
      state.varSel = pool.length ? pool[0].key : null;
    }
    const sel = findVar(state.varSel);

    let html = '<div class="section-head" style="margin-top:0"><h3>변수 추적</h3><span class="hint">선언 → 읽기 / 쓰기 / 외부 참조</span></div>';
    html += '<div class="vars-wrap"><div class="card" style="padding:14px"><div class="search" style="margin-bottom:10px"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/></svg><input id="vsearch" placeholder="변수 검색"></div>';
    html += '<div style="display:flex;gap:6px;margin-bottom:10px"><button class="btn" id="scopeClass" style="flex:1;justify-content:center;' + (state.varScope === 'class' ? 'border-color:var(--gold);color:var(--gold)' : '') + '">이 클래스</button><button class="btn" id="scopeAll" style="flex:1;justify-content:center;' + (state.varScope === 'all' ? 'border-color:var(--gold);color:var(--gold)' : '') + '">전체</button></div>';
    html += '<div class="varlist" id="varlist">' + (pool.length ? pool.map(x => {
      const r = x.v.usages.filter(u => u.rw !== 'write').length;
      const w = x.v.usages.filter(u => u.rw !== 'read').length;
      return '<button class="vitem' + (x.key === state.varSel ? ' on' : '') + '" data-var="' + esc(x.key) + '"><div class="vn">' + esc(x.v.name) + (x.v.isSerialized ? ' <span class="chip serialized" style="font-size:8px;padding:0 4px">S</span>' : '') + '</div><div class="vt">' + esc(x.v.type || '—') + (state.varScope === 'all' ? ' · ' + esc(x.owner.name) : '') + '</div><div class="vm"><span class="pill read">r ' + r + '</span><span class="pill write">w ' + w + '</span></div></button>';
    }).join('') : '<div class="empty">필드가 없습니다.</div>') + '</div></div>';

    html += '<div id="tracePanel">' + (sel ? traceHtml(sel) : '<div class="empty">추적할 변수를 선택하세요.</div>') + '</div></div>';
    $('#v-vars').innerHTML = html;

    const vs = $('#vsearch');
    if (vs) {
      vs.value = state.vq;
      vs.addEventListener('input', e => { state.vq = e.target.value.toLowerCase(); renderVars(); });
      if (state.vq) { vs.focus(); vs.setSelectionRange(vs.value.length, vs.value.length); }
    }
    const sc = $('#scopeClass'), sa = $('#scopeAll');
    if (sc) sc.addEventListener('click', () => { state.varScope = 'class'; state.varSel = null; ensureVar(); renderVars(); });
    if (sa) sa.addEventListener('click', () => { state.varScope = 'all'; state.varSel = null; ensureVar(); renderVars(); });
  }

  function traceHtml(x) {
    const f = x.v, t = x.owner;
    const usages = (f.usages || []).slice().sort((a, b) => (a.line - b.line) || (a.method > b.method ? 1 : -1));
    const reads = usages.filter(u => u.rw !== 'write').length;
    const writes = usages.filter(u => u.rw !== 'read').length;
    const extClasses = Array.from(new Set(usages.filter(u => u.external).map(u => u.owner)));
    const decl = (x.kind === 'field' ? (f.attrs.indexOf('SerializeField') >= 0 ? '[SerializeField] ' : '') + (f.modifiers.join(' ') + ' ') : '') + (f.type || '') + ' ' + f.name + (f.init ? ' = ' + f.init : '') + ';';
    const writeMethods = Array.from(new Set(usages.filter(u => u.rw !== 'read').map(u => u.method)));
    const readMethods = Array.from(new Set(usages.filter(u => u.rw !== 'write').map(u => u.method)));

    let h = '<div class="trace-decl"><div class="td-top"><span class="td-name">' + esc(f.name) + '</span><span class="td-type">' + esc(f.type || '') + '</span>' +
      (f.isSerialized ? '<span class="chip serialized">serialized</span>' : '') +
      '<span class="td-line">' + esc(t.name) + ' · ' + esc(t.file) + ' L' + f.line + '</span></div>' +
      '<div class="td-code">' + esc(decl) + '</div>' +
      '<div class="trace-stats"><span class="tstat read">읽기<b>' + reads + '</b></span><span class="tstat write">쓰기<b>' + writes + '</b></span><span class="tstat ext">참조 클래스<b>' + extClasses.length + '</b></span><span class="tstat">사용 메서드<b>' + new Set(usages.map(u => u.method)).size + '</b></span></div>' +
      (writes && reads ? '<p class="muted-line" style="margin-top:10px;font-size:11px">쓰기: <b style="color:var(--write)">' + esc(writeMethods.join(', ')) + '</b> → 읽기: <b style="color:var(--read)">' + esc(readMethods.join(', ')) + '</b></p>' : '') +
      (extClasses.length ? '<p class="muted-line" style="margin-top:6px;font-size:11px">다른 파일에서도 접근됨: <b style="color:var(--violet)">' + esc(extClasses.join(', ')) + '</b></p>' : '') +
      '</div>';

    if (!usages.length) {
      return h + '<div class="empty">이 변수는 코드에서 한 번도 사용되지 않습니다.' + (f.isSerialized ? ' Inspector에서만 값을 받는 필드입니다.' : '') + '</div>';
    }
    h += '<div class="card"><div class="card-h"><h3>사용 지점</h3><span class="eyebrow">' + usages.length + ' hits</span></div><div class="trace">';
    h += usages.map(u => '<div class="tr ' + u.rw + (u.external ? ' ext' : '') + '"><span class="dot"></span><div class="tr-top"><span class="pill ' + u.rw + '">' + (u.rw === 'read' ? 'read' : u.rw === 'write' ? 'write' : 'rw') + '</span><span class="tr-m">' + esc(u.owner === t.name ? u.method + '()' : u.owner + ' · ' + u.method + '()') + '</span>' + (u.external ? '<span class="pill ext">외부</span>' : '') + '<span class="tr-l">' + esc(u.file) + ' : ' + u.line + '</span></div><div class="tr-c">' + esc(u.code) + '</div>' + (u.via ? '<div class="tr-via">↳ ' + esc(u.via) + '</div>' : '') + '</div>').join('');
    h += '</div></div>';
    return h;
  }

  /* ---------- graph ---------- */
  function renderGraph() {
    const d = state.data;
    if (!d.types.length) { $('#v-graph').innerHTML = '<div class="empty">타입이 없습니다.</div>'; return; }
    const cols = { data: [], system: [], plain: [], action: [], ui: [] };
    d.types.forEach(t => {
      const tone = primaryRole(t).tone;
      (cols[tone] || cols.plain).push(t);
    });
    const colIndex = { data: 0, system: 1, plain: 1, action: 2, ui: 3 };
    const W = 172, H = 54, GX = 64, GY = 22;
    const positions = new Map();
    const colCounts = {};
    Object.keys(cols).forEach(tone => {
      cols[tone].forEach(t => {
        const c = colIndex[tone];
        const i = colCounts[tone] = (colCounts[tone] || 0);
        colCounts[tone]++;
        positions.set(t.name, { x: 30 + c * (W + GX), y: 34 + i * (H + GY), c });
      });
    });
    let maxX = 0, maxY = 0;
    positions.forEach(p => { maxX = Math.max(maxX, p.x + W); maxY = Math.max(maxY, p.y + H); });
    const svgW = maxX + 30, svgH = maxY + 40;

    let edges = '';
    d.edges.forEach(e => {
      const a = positions.get(e.from), b = positions.get(e.to);
      if (!a || !b) return;
      const x1 = a.x + W, y1 = a.y + H / 2, x2 = b.x, y2 = b.y + H / 2;
      let path;
      if (Math.abs(a.c - b.c) < 0.5) {
        const cx = a.x + W / 2;
        path = 'M ' + cx + ' ' + (a.y + H) + ' V ' + (b.y - 8) + ' H ' + (b.x + W / 2) + ' V ' + b.y;
      } else if (x2 > x1) {
        const mx = (x1 + x2) / 2;
        path = 'M ' + x1 + ' ' + y1 + ' H ' + mx + ' V ' + y2 + ' H ' + x2;
      } else {
        const mx = x1 + 26;
        path = 'M ' + x1 + ' ' + y1 + ' H ' + mx + ' V ' + (b.y + H + 12) + ' H ' + (b.x + W / 2) + ' V ' + (b.y + H);
      }
      edges += '<path class="gedge' + (e.inherit ? ' inherit' : '') + '" marker-end="url(#arw)" d="' + path + '"><title>' + esc(e.from + ' → ' + e.to + (e.label ? ' · ' + e.label : '')) + '</title></path>';
    });

    let nodes = '';
    d.types.forEach(t => {
      const p = positions.get(t.name);
      if (!p) return;
      const r = primaryRole(t);
      nodes += '<g class="gnode' + (t.name === state.selected ? ' on' : '') + '" data-type="' + esc(t.name) + '" transform="translate(' + p.x + ',' + p.y + ')">' +
        '<rect width="' + W + '" height="' + H + '" rx="9"></rect>' +
        '<rect width="3" height="' + H + '" rx="1.5" fill="' + (r.tone === 'data' ? '#a99bf0' : r.tone === 'system' ? '#5ec8ac' : r.tone === 'action' ? '#d9a84e' : r.tone === 'ui' ? '#e2a1c7' : '#63796c') + '"></rect>' +
        '<text x="14" y="25">' + esc(t.name.length > 24 ? t.name.slice(0, 23) + '…' : t.name) + '</text>' +
        '<text class="gbase" x="14" y="42">' + esc((t.base || t.kind).toUpperCase()) + '</text>' +
        '</g>';
    });

    let html = '<div class="section-head" style="margin-top:0"><h3>배선도</h3><span class="hint">타입이 다른 타입의 멤버를 참조하는 방향</span></div>';
    html += '<div class="graph-wrap"><svg viewBox="0 0 ' + svgW + ' ' + svgH + '" width="100%" height="' + svgH + '" preserveAspectRatio="xMinYMin meet">' +
      '<defs><marker id="arw" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#3a5446"/></marker></defs>' +
      edges + nodes + '</svg></div>';
    html += '<div class="legend"><span class="li"><i></i>멤버 참조</span><span class="li v"><i></i>상속</span><span class="li g"><i style="background:#d9a84e"></i>데이터</span><span class="li"><i style="background:#5ec8ac"></i>시스템</span><span class="li"><i style="background:#a99bf0"></i>데이터 에셋</span></div>';
    html += '<p class="muted-line" style="margin-top:12px;font-size:11px">노드를 클릭하면 해당 타입으로 이동합니다. 화살표에 마우스를 올리면 실제 참조 식이 표시됩니다.</p>';
    $('#v-graph').innerHTML = html;
  }

  /* ---------- source ---------- */
  function renderSource() {
    const t = selType();
    if (!t) { $('#v-source').innerHTML = '<div class="empty">파일이 없습니다.</div>'; return; }
    const file = state.data.files.find(f => f.name === t.file);
    if (!file) { $('#v-source').innerHTML = '<div class="empty">소스를 찾을 수 없습니다.</div>'; return; }
    const sel = state.varSel ? findVar(state.varSel) : null;
    const hits = {};
    const own = sel && sel.owner.name === t.name ? [sel.v] : t.fields.concat(t.props);
    own.forEach(v => (v.usages || []).forEach(u => {
      if (u.owner === t.name || u.external) {
        const cur = hits[u.line] || (hits[u.line] = { write: false });
        if (u.rw !== 'read') cur.write = true;
      }
    }));
    let html = '<div class="section-head" style="margin-top:0"><h3>' + esc(t.file) + '</h3><span class="hint">' + (sel && sel.owner.name === t.name ? esc(sel.v.name) + ' 사용 줄 강조' : '강조 없음 · 변수 추적에서 선택') + '</span></div>';
    html += '<div class="code-wrap"><div class="code">' + file.lines.map((l, i) => {
      const ln = i + 1, hit = hits[ln];
      return '<div class="cl' + (hit ? ' hit' + (hit.write ? ' write' : '') : '') + '"><span class="ln">' + ln + '</span><span class="cd">' + (esc(l) || ' ') + '</span></div>';
    }).join('') + '</div></div>';
    $('#v-source').innerHTML = html;
  }

  /* ---------- markdown export ---------- */
  function buildMd() {
    const d = state.data;
    const L = [];
    L.push('# Unity 코드 해석 리포트', '');
    L.push('- 파일: ' + d.files.length + '개');
    L.push('- 타입: ' + d.types.length + '개');
    L.push('- 생성: ' + new Date().toISOString().slice(0, 16).replace('T', ' '));
    L.push('');
    L.push('## 요약', '');
    L.push('| 타입 | 베이스 | 역할 | 필드 | 읽기 | 쓰기 | 이슈 |');
    L.push('|---|---|---|---|---|---|---|');
    d.types.forEach(t => L.push('| ' + t.name + ' | ' + (t.base || '—') + ' | ' + primaryRole(t).name + ' | ' + t.fields.length + ' | ' + t.stats.reads + ' | ' + t.stats.writes + ' | ' + t.issues.length + ' |'));
    L.push('');
    d.types.forEach(t => {
      L.push('## ' + t.name, '');
      L.push('`' + t.file + '` L' + t.startLine + '–' + t.endLine + ' · `' + (t.modifiers.join(' ') + ' ' + t.kind + ' ' + t.name + (t.bases.length ? ' : ' + t.bases.join(', ') : '')).trim() + '`', '');
      L.push('**역할**: ' + t.roles.map(r => r.name).join(' / '), '');
      t.roles.forEach(r => { L.push('- ' + r.name + ' — ' + r.evidence.join('; ')); });
      L.push('');
      if (NOTES[t.name]) L.push(NOTES[t.name], '');
      if (t.fields.length) {
        L.push('### 필드', '', '| 이름 | 타입 | 직렬화 | 읽기 | 쓰기 | 사용 메서드 |', '|---|---|---|---|---|---|');
        t.fields.forEach(f => L.push('| ' + f.name + ' | ' + f.type + ' | ' + (f.isSerialized ? 'O' : '') + ' | ' + readCount(f) + ' | ' + writeCount(f) + ' | ' + Array.from(new Set(f.usages.map(u => u.method))).join(', ') + ' |'));
        L.push('');
      }
      if (t.methods.length) {
        L.push('### 메서드', '');
        t.methods.forEach(m => L.push('- `' + m.name + '(' + m.params.map(p => p.type + ' ' + p.name).join(', ') + ')` L' + m.line + (m.isLifecycle ? ' (Unity)' : '')));
        L.push('');
      }
      if (t.issues.length) {
        L.push('### 이슈', '');
        t.issues.forEach(i => L.push('- **[' + i.sev + ']** ' + i.title + ' — ' + i.detail + (i.evidence ? ' (`' + i.evidence + '`)' : '')));
        L.push('');
      }
    });
    if (d.unresolved.length) {
      L.push('## 미해석 외부 참조', '');
      d.unresolved.forEach(u => L.push('- `' + u.name + '` ← ' + u.usedBy + ' L' + u.line));
    }
    return L.join('\n');
  }

  function exportMd() {
    const blob = new Blob([buildMd()], { type: 'text/markdown;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'unitylens-report.md';
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 3000);
    toast('Markdown 리포트를 내려받았습니다.');
  }

  /* ---------- mini markdown ---------- */
  function mdInline(s) {
    return esc(s)
      .replace(/`([^`]+)`/g, '<code style="font-family:var(--mono);font-size:.92em;color:#e7d3a8;background:rgba(217,168,78,.08);padding:1px 4px;border-radius:3px">$1</code>')
      .replace(/\*\*([^*]+)\*\*/g, '<b style="color:var(--ink)">$1</b>');
  }

  document.addEventListener('DOMContentLoaded', boot);
})();
