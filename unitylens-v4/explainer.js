/* UnityLens v4 — LLM explanation layer with identifier guard.
   Parser owns facts; the model may only narrate them. Every backticked identifier
   is verified against the class symbol table before it is shown as trusted. */
(function (root) {
  'use strict';

  const UNITY = new Set(('MonoBehaviour ScriptableObject Behaviour Component GameObject Transform RectTransform Vector2 Vector3 Quaternion Mathf Time Debug Camera Rigidbody2D Rigidbody Collider2D Slider TextMeshProUGUI TMP_Text SpriteRenderer Sprite AudioSource AudioClip Keyboard Gamepad SceneManager AsyncOperation Application Random Input Key KeyCode Instantiate Destroy GetComponent StartCoroutine SendMessage SetActive CompareTag FindFirstObjectByType FindGameObjectsWithTag AddComponent DontDestroyOnLoad transform gameObject position rotation localScale localPosition anchoredPosition Translate Rotate MovePosition enabled text value isPressed wasPressedThisFrame deltaTime fixedDeltaTime time main current clip loop volume SetFloat SetBool SetTrigger Quaternion identity Lerp Clamp Clamp01 MoveTowards Distance normalized sqrMagnitude magnitude zero one up forward right x y z w public private protected internal static readonly const void float int bool string class struct enum event Action Func List Dictionary Array Queue override virtual abstract sealed partial new this base return if else for foreach while switch case break continue try catch finally throw using namespace await yield null true false var out ref in params get set SerializeField Header TextArea CreateAssetMenu SerializeReference Range Tooltip ExecuteAlways RequireComponent').split(' '));

  const MODAL_ID = 'llmModal';
  const cfg = { endpoint: '', model: '', key: '' };
  const cache = new Map();
  const busy = new Set();

  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const keyFor = t => (t.file || '') + '|' + t.name;

  function addTypes(set, typeStr) {
    String(typeStr || '').split(/[^\w]+/).forEach(x => { if (x) set.add(x); });
  }

  let _global = null, _globalData = null;
  function globalSymbols() {
    const d = root.__UL && root.__UL.data;
    if (!d) return new Set();
    if (_globalData === d && _global) return _global;
    const s = new Set();
    d.types.forEach(t => {
      s.add(t.name);
      if (t.base) s.add(t.base);
      (t.interfaces || []).forEach(i => s.add(i));
      t.fields.forEach(f => { s.add(f.name); addTypes(s, f.type); });
      t.props.forEach(p => { s.add(p.name); addTypes(s, p.type); });
      t.methods.forEach(m => { s.add(m.name); m.params.forEach(p => { s.add(p.name); addTypes(s, p.type); }); });
    });
    _global = s; _globalData = d;
    return s;
  }

  function allowedSet(t) {
    const s = new Set([t.name, t.base, (t.file || '').replace(/\.cs$/, '')].filter(Boolean));
    (t.interfaces || []).forEach(i => s.add(i));
    (t.bases || []).forEach(b => s.add(b));
    t.fields.forEach(f => { s.add(f.name); addTypes(s, f.type); });
    t.props.forEach(p => { s.add(p.name); addTypes(s, p.type); });
    t.methods.forEach(m => { s.add(m.name); m.params.forEach(p => { s.add(p.name); addTypes(s, p.type); }); });
    UNITY.forEach(x => s.add(x));
    globalSymbols().forEach(x => s.add(x));
    return s;
  }

  function identifierLike(x) {
    return /^[A-Za-z_][A-Za-z0-9_.]*(<[^>]+>)?(\(\))?$/.test(String(x || '').trim());
  }

  function stateOf(raw, t, set) {
    let x = String(raw || '').trim().replace(/\(\)$/, '').replace(/<.*>$/, '');
    if (!x) return 'bad';
    x = x.replace(/^this\./, '');
    const first = x.split('.')[0];
    if (set.has(x) || set.has(first)) return 'ok';
    const un = (root.__UL && root.__UL.data && root.__UL.data.unresolved) || [];
    if (un.some(u => u.name === first || u.name === x)) return 'ext';
    return 'bad';
  }

  /* ---------- facts ---------- */
  function fieldLine(f) {
    const reads = f.usages.filter(u => u.rw !== 'write').length;
    const writes = f.usages.filter(u => u.rw !== 'read').length;
    const ms = Array.from(new Set(f.usages.map(u => u.method)));
    const bits = [f.type + (f.isSerialized ? ' (SerializeField)' : '')];
    if (reads) bits.push('읽기 ' + reads);
    if (writes) bits.push('쓰기 ' + writes);
    if (ms.length) bits.push('메서드: ' + ms.join(', '));
    if (!f.usages.length) bits.push('사용 없음');
    return '- ' + f.name + ': ' + bits.join(', ');
  }

  function facts(t) {
    const life = t.methods.filter(m => m.isLifecycle).map(m => m.name);
    return {
      name: t.name, file: t.file, base: t.base, interfaces: t.interfaces,
      roles: t.roles.map(r => r.name), fields: t.fields, methods: t.methods,
      life, externals: t.externals, issues: t.issues,
      loc: t.loc, tracked: t.fields.filter(f => f.usages.length).length
    };
  }

  function factText(t) {
    const f = facts(t);
    const L = [];
    L.push('클래스: ' + f.name + (f.base ? ' : ' + f.base : ''));
    L.push('파일: ' + f.file + ' (L' + t.startLine + '–' + t.endLine + ', ' + f.loc + '줄)');
    if (f.interfaces.length) L.push('인터페이스: ' + f.interfaces.join(', '));
    L.push('판정 역할: ' + f.roles.join(' / '));
    L.push('생명주기: ' + (f.life.length ? f.life.join(' → ') : '없음'));
    if (f.fields.length) {
      L.push('필드:');
      f.fields.forEach(x => L.push('  ' + fieldLine(x).slice(2)));
    }
    if (f.methods.length) L.push('메서드: ' + f.methods.map(m => m.name).join(', '));
    if (f.externals.length) L.push('외부 참조: ' + Array.from(new Set(f.externals.map(e => e.target + '.' + e.member))).join(', '));
    if (f.issues.length) L.push('탐지된 이슈: ' + f.issues.map(i => i.title).join(' / '));
    L.push('식별자 목록: ' + Array.from(allowedSet(t)).sort().join(', '));
    return L.join('\n');
  }

  /* ---------- offline (deterministic) narrative ---------- */
  function ruleNarrative(t) {
    const f = facts(t);
    const out = [];
    const role = f.roles[0] || t.kind;
    let s = '`' + t.name + '`은(는) ';
    s += f.base ? '`' + f.base + '`를 상속한 ' : '';
    if (f.interfaces.length) s += '`' + f.interfaces.join('`·`') + '`를 구현한 ';
    s += '**' + role + '**입니다.';
    out.push(s);

    if (f.life.length) out.push('생명주기는 ' + f.life.map(x => '`' + x + '`').join(' → ') + ' 순서로 호출됩니다.');

    const used = f.fields.filter(x => x.usages.length).slice(0, 3);
    if (used.length) {
      out.push('변수 흐름: ' + used.map(x => {
        const w = x.usages.filter(u => u.rw !== 'read').length;
        const r = x.usages.filter(u => u.rw !== 'write').length;
        const wm = Array.from(new Set(x.usages.filter(u => u.rw !== 'read').map(u => u.method)));
        const rm = Array.from(new Set(x.usages.filter(u => u.rw !== 'write').map(u => u.method)));
        let p = '`' + x.name + '`';
        if (w && wm.length) p += '는 `' + wm[0] + '`에서 ' + w + '회 기록';
        if (r && rm.length) p += '되고 `' + rm[0] + '`에서 ' + r + '회 읽힙';
        return p + '니다';
      }).join(', ') + '.');
    }

    if (f.externals.length) {
      const e = f.externals[0];
      out.push('`' + e.target + '.' + e.member + '`를 `' + e.method + '`에서 참조합니다.');
    }

    if (f.issues.length) out.push('확인할 점: **' + f.issues[0].title + '** — ' + f.issues[0].detail);
    out.push('전체 필드 ' + f.fields.length + '개 중 ' + f.tracked + '개가 코드에서 실제로 사용됩니다.');
    return out.join('\n\n');
  }

  function narrative(t) {
    const note = (root.UNITYLENS_NOTES || {})[t.name];
    if (note) return { text: note, source: 'curated', engine: 'curated' };
    return { text: ruleNarrative(t), source: 'rule', engine: 'offline' };
  }

  /* ---------- rendering / verification ---------- */
  function verify(t, text) {
    const set = allowedSet(t);
    const items = [];
    const re = /`([^`]+)`/g;
    let m;
    while ((m = re.exec(text || '')) !== null) {
      const raw = m[1].trim();
      if (!raw || !identifierLike(raw)) continue;
      items.push({ raw, state: stateOf(raw, t, set) });
    }
    const ok = items.filter(i => i.state === 'ok').length;
    const ext = items.filter(i => i.state === 'ext').length;
    const bad = items.filter(i => i.state === 'bad').length;
    return { items, total: items.length, ok, ext, bad };
  }

  function renderRich(text, t) {
    const parts = String(text || '').split('`');
    let out = '';
    parts.forEach((p, i) => {
      if (i % 2 === 1) {
        if (!identifierLike(p)) {
          out += '<code class="idcode expr">' + esc(p) + '</code>';
        } else {
          const st = stateOf(p, t, allowedSet(t));
          const title = st === 'ok' ? '심볼 테이블에서 검증됨'
            : st === 'ext' ? '스캔 범위 밖 클래스 — 파일을 추가하면 검증됩니다'
            : '심볼 테이블에 없는 이름 — 미검증';
          out += '<code class="idcode ' + st + '" title="' + title + '">' + esc(p) + '</code>';
        }
      } else {
        out += esc(p).replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>').replace(/\n/g, '<br>');
      }
    });
    return out;
  }

  /* ---------- structured schema ---------- */
  function uniq(a) { return Array.from(new Set(a)); }

  function ruleJson(t) {
    const note = (root.UNITYLENS_NOTES || {})[t.name];
    const flow = t.fields.filter(f => f.usages.length).slice(0, 5).map(f => ({
      field: f.name,
      writes: uniq(f.usages.filter(u => u.rw !== 'read').map(u => u.method)),
      reads: uniq(f.usages.filter(u => u.rw !== 'write').map(u => u.method)),
      note: f.isSerialized ? 'Inspector 주입' : (f.isStatic ? 'static' : '')
    }));
    const risks = t.issues.slice(0, 3).map(i => ({ severity: i.sev, title: i.title, detail: i.detail }));
    return { summary: note || ruleNarrative(t), flow, risks };
  }

  function normalizeObj(o) {
    const out = { summary: '', flow: [], risks: [] };
    if (o && typeof o.summary === 'string') out.summary = o.summary.trim();
    if (o && Array.isArray(o.flow)) {
      out.flow = o.flow.slice(0, 6).map(x => ({
        field: String((x && x.field) || '').trim(),
        writes: (x && Array.isArray(x.writes) ? x.writes : []).map(String).slice(0, 4),
        reads: (x && Array.isArray(x.reads) ? x.reads : []).map(String).slice(0, 4),
        note: String((x && x.note) || '')
      })).filter(x => x.field);
    }
    if (o && Array.isArray(o.risks)) {
      out.risks = o.risks.slice(0, 4).map(x => {
        const sev = String((x && x.severity) || 'low').toLowerCase();
        return {
          severity: ['high', 'medium', 'low'].includes(sev) ? sev : 'low',
          title: String((x && x.title) || ''),
          detail: String((x && x.detail) || '')
        };
      }).filter(x => x.title);
    }
    if (!out.summary && !out.flow.length && !out.risks.length) throw new Error('빈 스키마');
    return out;
  }

  function parseJson(text) {
    let x = String(text || '').trim();
    x = x.replace(/^```(?:json)?\s*/i, '').replace(/```\s*$/, '').trim();
    const a = x.indexOf('{'), b = x.lastIndexOf('}');
    if (a < 0 || b < a) throw new Error('JSON 객체 없음');
    return normalizeObj(JSON.parse(x.slice(a, b + 1)));
  }

  function renderStructured(t, o) {
    const own = new Set(t.fields.map(f => f.name).concat(t.props.map(p => p.name)));
    let h = '';
    h += '<div class="ai-section"><div class="ai-label">요약</div><p class="ai-summary">' + renderRich(o.summary, t) + '</p></div>';
    h += '<div class="ai-section"><div class="ai-label">변수 흐름</div>';
    if (o.flow.length) {
      h += '<div class="flow-list">';
      o.flow.forEach(x => {
        const ok = own.has(x.field);
        h += '<div class="flow-row' + (ok ? '' : ' bad') + '"><span class="flow-field" title="' + (ok ? '클래스 필드로 확인됨' : '이 클래스의 필드가 아님') + '">' + esc(x.field) + (ok ? '' : ' ⚠') + '</span>' +
          '<span class="flow-methods">' +
          x.writes.map(m => '<span class="pill write">w ' + esc(m) + '</span>').join('') +
          x.reads.map(m => '<span class="pill read">r ' + esc(m) + '</span>').join('') +
          '</span>' +
          (x.note ? '<span class="flow-note">' + renderRich(x.note, t) + '</span>' : '') + '</div>';
      });
      h += '</div>';
    } else {
      h += '<p class="ai-empty">추적된 필드가 없습니다.</p>';
    }
    h += '</div>';
    h += '<div class="ai-section"><div class="ai-label">리스크</div>';
    if (o.risks.length) {
      h += o.risks.map(r => '<div class="risk-item"><span class="chip sev-' + r.severity + '">' + r.severity.toUpperCase() + '</span><div><b>' + esc(r.title) + '</b><p>' + renderRich(r.detail, t) + '</p></div></div>').join('');
    } else {
      h += '<p class="ai-empty">탐지된 리스크가 없습니다.</p>';
    }
    h += '</div>';
    return h;
  }

  /* ---------- card ---------- */
  function card(t) {
    const key = keyFor(t);
    const note = (root.UNITYLENS_NOTES || {})[t.name];
    const c = cache.get(key) || { json: ruleJson(t), source: note ? 'curated' : 'rule' };
    const v = verify(t, [c.json.summary].concat(c.json.risks.map(r => r.detail)).concat(c.json.flow.map(f => f.note)).join('\n'));
    const own = new Set(t.fields.map(f => f.name).concat(t.props.map(p => p.name)));
    const flowBad = c.json.flow.filter(x => !own.has(x.field)).length;
    const srcLabel = c.source === 'llm' ? ('LLM · ' + c.engine) : c.source === 'curated' ? '큐레이션 (샘플)' : '파서 기반 규칙';
    let body;
    if (busy.has(key)) {
      body = '<p class="ai-busy">LLM이 JSON 해설을 생성하는 중… <span class="dotpulse"></span></p>';
    } else if (c.error) {
      body = '<p class="ai-err">LLM 호출 실패 — ' + esc(c.error) + ' <button class="linkbtn" data-ai="config">설정</button></p>' +
        (c.raw ? '<details class="factbox"><summary>원문 보기</summary><pre>' + esc(c.raw.slice(0, 1200)) + '</pre></details>' : '');
    } else {
      body = renderStructured(t, c.json);
    }
    const parts = [];
    if (v.total) parts.push('식별자 ' + v.ok + '/' + v.total + ' 검증');
    if (v.ext) parts.push('외부 ' + v.ext);
    if (v.bad) parts.push('미검증 ' + v.bad);
    if (flowBad) parts.push('필드 미검증 ' + flowBad);
    const badge = '<span class="idbadge ' + ((v.bad || flowBad) ? 'warn' : 'ok') + '">' + (parts.length ? parts.join(' · ') : '검증할 식별자 없음') + '</span>';
    return '<div class="card ai-card"><div class="card-h"><h3>AI 해설</h3><span class="eyebrow">' + srcLabel + '</span></div>' +
      body +
      '<div class="ai-foot">' + badge +
      '<span class="ai-actions"><button class="btn tiny" data-ai="gen">LLM으로 생성</button><button class="btn tiny ghost" data-ai="config">LLM 연결</button></span></div>' +
      '<details class="factbox"><summary>근거 팩트시트 <span>파서가 확정한 사실만 전달</span></summary><pre>' + esc(factText(t)) + '</pre></details>' +
      '</div>';
  }

  /* ---------- LLM call ---------- */
  function normalize(url) {
    let u = String(url || '').trim().replace(/\/+$/, '');
    if (!u) return '';
    if (/\/chat\/completions$/.test(u)) return u;
    if (/\/v1$/.test(u)) return u + '/chat/completions';
    if (/:\d+$/.test(u)) return u + '/v1/chat/completions';
    return u;
  }

  function promptFor(t) {
    const schema = '{"summary":"3~5문장 한국어 요약","flow":[{"field":"필드명","writes":["쓰는 메서드"],"reads":["읽는 메서드"],"note":"한 줄 메모"}],"risks":[{"severity":"high|medium|low","title":"제목","detail":"설명"}]}';
    return '다음은 Unity C# 클래스에 대해 파서가 확정한 사실이다.\n\n' + factText(t) +
      '\n\n위 사실만 근거로 분석을 작성해라. 출력은 아래 JSON 스키마 **하나만** 있어야 한다. 코드블록·설명문·머리말 금지.\n' +
      schema + '\n\n규칙:\n' +
      '1) summary의 모든 코드 식별자는 백틱(`)으로 감싼다.\n' +
      '2) 식별자 목록에 없는 이름을 절대 만들지 않는다.\n' +
      '3) flow는 실제로 사용되는 필드만, 최대 5개. writes/reads는 사실에 있는 메서드만.\n' +
      '4) risks는 탐지된 이슈를 우선 사용하고, 없으면 빈 배열로 둔다.\n' +
      '5) 추측 금지. 사실에 없는 동작을 설명하지 않는다.';
  }

  async function callLLM(t, withFormat) {
    const body = {
      model: cfg.model,
      messages: [
        { role: 'system', content: '너는 Unity C# 정적 분석 결과를 JSON으로 정리하는 도구다. 설명문 없이 JSON 객체만 출력한다. 주어진 식별자만 사용한다.' },
        { role: 'user', content: promptFor(t) }
      ],
      temperature: 0.1,
      max_tokens: 700
    };
    if (withFormat) body.response_format = { type: 'json_object' };
    const res = await fetch(normalize(cfg.endpoint), {
      method: 'POST',
      headers: Object.assign({ 'Content-Type': 'application/json' }, cfg.key ? { Authorization: 'Bearer ' + cfg.key } : {}),
      body: JSON.stringify(body)
    });
    if (!res.ok) {
      const err = new Error('HTTP ' + res.status);
      err.status = res.status;
      throw err;
    }
    const data = await res.json();
    return (data.choices && data.choices[0] && data.choices[0].message && data.choices[0].message.content) || data.text || '';
  }

  async function generate(t) {
    if (!cfg.endpoint || !cfg.model) { openConfig(); return; }
    const key = keyFor(t);
    busy.add(key);
    cache.delete(key);
    root.__UL_renderClass && root.__UL_renderClass();
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 60000);
    let raw = '';
    try {
      let text;
      try {
        text = await callLLM(t, true);
      } catch (e) {
        if (e.status === 400) text = await callLLM(t, false);
        else throw e;
      }
      raw = text;
      if (!String(text).trim()) throw new Error('빈 응답');
      const json = parseJson(text);
      cache.set(key, { json, source: 'llm', engine: cfg.model });
    } catch (e) {
      const msg = e.name === 'AbortError' ? '시간 초과 (60s)' : (e.message || String(e));
      cache.set(key, { error: msg, raw, source: 'llm', engine: cfg.model });
    } finally {
      clearTimeout(timer);
      busy.delete(key);
      root.__UL_renderClass && root.__UL_renderClass();
    }
  }

  function applyJson(t, json, engine) {
    cache.set(keyFor(t), { json: normalizeObj(json), source: 'llm', engine: engine || 'test' });
    root.__UL_renderClass && root.__UL_renderClass();
  }

  /* ---------- config ---------- */
  function updateChip() {
    const el = document.getElementById('llmChip');
    if (!el) return;
    if (cfg.endpoint && cfg.model) {
      el.textContent = 'LLM · ' + cfg.model;
      el.classList.add('on');
      el.title = normalize(cfg.endpoint);
    } else {
      el.textContent = 'LLM 오프라인';
      el.classList.remove('on');
      el.title = '파서 기반 해설만 사용 중';
    }
  }

  function openConfig() {
    const m = document.getElementById(MODAL_ID);
    if (!m) return;
    document.getElementById('llmEndpoint').value = cfg.endpoint;
    document.getElementById('llmModel').value = cfg.model;
    document.getElementById('llmKey').value = cfg.key;
    document.getElementById('llmStatus').textContent = '';
    m.hidden = false;
    document.getElementById('llmEndpoint').focus();
  }

  function closeConfig() {
    const m = document.getElementById(MODAL_ID);
    if (m) m.hidden = true;
  }

  function saveConfig() {
    cfg.endpoint = document.getElementById('llmEndpoint').value.trim();
    cfg.model = document.getElementById('llmModel').value.trim();
    cfg.key = document.getElementById('llmKey').value.trim();
    try {
      sessionStorage.setItem('ul_llm', JSON.stringify({ endpoint: cfg.endpoint, model: cfg.model }));
    } catch (e) {}
    updateChip();
    closeConfig();
    root.__UL_renderClass && root.__UL_renderClass();
    if (root.__UL_toast) root.__UL_toast(cfg.endpoint ? 'LLM 연결 설정 저장' : 'LLM 연결 해제');
  }

  async function testConfig() {
    const st = document.getElementById('llmStatus');
    const ep = document.getElementById('llmEndpoint').value.trim();
    const model = document.getElementById('llmModel').value.trim();
    const key = document.getElementById('llmKey').value.trim();
    if (!ep || !model) { st.textContent = '주소와 모델명을 입력하세요.'; st.className = 'llm-status bad'; return; }
    st.textContent = '연결 확인 중…';
    st.className = 'llm-status';
    try {
      const res = await fetch(normalize(ep), {
        method: 'POST',
        headers: Object.assign({ 'Content-Type': 'application/json' }, key ? { Authorization: 'Bearer ' + key } : {}),
        body: JSON.stringify({ model, messages: [{ role: 'user', content: 'ping' }], max_tokens: 4, temperature: 0 })
      });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      st.textContent = '연결 성공 — ' + model;
      st.className = 'llm-status ok';
    } catch (e) {
      st.textContent = '실패: ' + e.message;
      st.className = 'llm-status bad';
    }
  }

  function action(name, t) {
    if (name === 'gen' && t) generate(t);
    else if (name === 'config') openConfig();
    else if (name === 'close') closeConfig();
    else if (name === 'save') saveConfig();
    else if (name === 'test') testConfig();
    else if (name === 'reset' && t) { cache.delete(keyFor(t)); root.__UL_renderClass && root.__UL_renderClass(); }
  }

  function init() {
    try {
      const raw = sessionStorage.getItem('ul_llm');
      if (raw) {
        const v = JSON.parse(raw);
        cfg.endpoint = v.endpoint || '';
        cfg.model = v.model || '';
      }
    } catch (e) {}
    updateChip();
    const chip = document.getElementById('llmChip');
    if (chip) chip.addEventListener('click', openConfig);
  }

  root.Explainer = { init, card, action, verify, facts, factText, cfg, narrative, generate, openConfig, updateChip, ruleJson, parseJson, applyJson };
})(window);
