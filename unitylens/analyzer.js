/* UnityLens analyzer core — brace/token based C# structure + variable flow analysis.
   Pure functions, no DOM. Works in Node and the browser. */
(function (root) {
  'use strict';

  const TYPE_KW = new Set(['class', 'struct', 'interface', 'enum', 'record']);
  const MODIFIERS = new Set('public private protected internal static readonly const abstract virtual override sealed partial async extern unsafe new event volatile required fixed'.split(' '));
  const KEYWORDS = new Set(('abstract as base bool break byte case catch char checked class const continue decimal default delegate do double else enum event explicit extern false finally fixed float for foreach goto if implicit in int interface internal is lock long namespace new null object operator out override params private protected public readonly ref return sbyte sealed short sizeof stackalloc static string struct switch this throw true try typeof uint ulong unchecked unsafe ushort using virtual void volatile while var async await yield get set add remove partial where record init required nameof value').split(' '));

  const UNITY_MESSAGES = ['Awake', 'OnEnable', 'Start', 'FixedUpdate', 'Update', 'LateUpdate', 'OnDisable', 'OnDestroy', 'OnApplicationQuit', 'OnGUI', 'OnCollisionEnter', 'OnCollisionEnter2D', 'OnTriggerEnter', 'OnTriggerEnter2D', 'OnTriggerExit', 'OnTriggerExit2D', 'OnPointerEnter', 'OnPointerExit', 'OnPointerDown', 'OnPointerClick', 'OnPointerUp', 'OnSubmit', 'OnCancel', 'Reset', 'OnValidate'];

  const KNOWN_TYPES = new Set(('Vector2 Vector3 Vector4 Quaternion Mathf Time Debug GameObject Transform RectTransform SpriteRenderer Sprite Camera Canvas CanvasGroup Slider Image Text TextMeshProUGUI TMP_Text AudioSource AudioClip Rigidbody Rigidbody2D Collider2D BoxCollider2D CircleCollider2D Animator Animation Random Enum Application SceneManager AsyncOperation Keyboard Gamepad Input System InputAction Key KeyCode Button EventSystem EventSystem PointerEventData Color Color32 Material Texture2D Texture Physics2D Physics Resources Object String Convert List Dictionary HashSet Array Tuple Task IEnumerable IEnumerator WaitForSeconds WaitForSecondsRealtime Rect Bounds Screen Cursor Scene ScriptableObject MonoBehaviour Behaviour Component CanvasRenderer LayoutElement VerticalLayoutGroup HorizontalLayoutGroup DOTween Tween Sequence').split(' '));

  const ASSIGN_OPS = new Set(['=', '+=', '-=', '*=', '/=', '%=', '&=', '|=', '^=', '<<=', '>>=', '??=']);
  const OPS = ['>>=', '<<=', '??=', '=>', '==', '!=', '<=', '>=', '&&', '||', '+=', '-=', '*=', '/=', '%=', '&=', '|=', '^=', '++', '--', '?.', '??', '::', '<<', '>>'];

  /* ---------------- lexer ---------------- */
  function lex(src) {
    const toks = [];
    let i = 0, line = 1;
    const n = src.length;
    const push = (t, v, l) => toks.push({ t, v, line: l });

    function readString(startIdx) {
      // handles "..." @"..." $"..." $@"..." @$"..." """..."""
      let j = startIdx, prefix = '';
      while (j < n && (src[j] === '$' || src[j] === '@') && src[j + 1] === '"') { prefix += src[j]; j++; }
      if (src.slice(j, j + 3) === '"""') {
        j += 3; let v = '';
        while (j < n && src.slice(j, j + 3) !== '"""') { if (src[j] === '\n') line++; v += src[j++]; }
        return { end: j + 3, value: v };
      }
      j++; let v = '';
      const verbatim = prefix.indexOf('@') >= 0;
      while (j < n) {
        const c = src[j];
        if (c === '\\' && !verbatim) { v += src[j + 1] || ''; j += 2; continue; }
        if (c === '"') {
          if (verbatim && src[j + 1] === '"') { v += '"'; j += 2; continue; }
          j++; break;
        }
        if (c === '\n') line++;
        v += c; j++;
      }
      return { end: j, value: v };
    }

    while (i < n) {
      const c = src[i];
      if (c === '\n') { line++; i++; continue; }
      if (c === ' ' || c === '\t' || c === '\r') { i++; continue; }
      if (c === '/' && src[i + 1] === '/') { while (i < n && src[i] !== '\n') i++; continue; }
      if (c === '/' && src[i + 1] === '*') {
        i += 2;
        while (i < n && !(src[i] === '*' && src[i + 1] === '/')) { if (src[i] === '\n') line++; i++; }
        i += 2; continue;
      }
      if (c === '"' || ((c === '$' || c === '@') && /["$@]/.test(src[i + 1]))) {
        const startLine = line;
        const r = readString(i);
        push('str', r.value, startLine);
        i = r.end; continue;
      }
      if (c === "'") {
        let j = i + 1, v = '';
        while (j < n) {
          if (src[j] === '\\') { v += src[j + 1]; j += 2; continue; }
          if (src[j] === "'") { j++; break; }
          v += src[j++];
        }
        push('chr', v, line); i = j; continue;
      }
      if (/[0-9]/.test(c) || (c === '.' && /[0-9]/.test(src[i + 1] || ''))) {
        let j = i;
        if (src[j] === '0' && /[xXbB]/.test(src[j + 1] || '')) { j += 2; while (j < n && /[0-9a-fA-F_]/.test(src[j])) j++; }
        else { while (j < n && /[0-9._]/.test(src[j])) j++; if (/[eE]/.test(src[j] || '')) { j++; if (/[+-]/.test(src[j] || '')) j++; while (j < n && /[0-9]/.test(src[j])) j++; } while (j < n && /[fFdDmMuUlL]/.test(src[j])) j++; }
        push('num', src.slice(i, j), line); i = j; continue;
      }
      if (/[A-Za-z_@]/.test(c)) {
        let j = i + 1;
        while (j < n && /[A-Za-z0-9_]/.test(src[j])) j++;
        let v = src.slice(i, j);
        if (v[0] === '@') v = v.slice(1);
        push('id', v, line); i = j; continue;
      }
      const three = src.substr(i, 3), two = src.substr(i, 2);
      const op = OPS.find(o => o.length === 3 && three === o) || OPS.find(o => o.length === 2 && two === o);
      if (op) { push('op', op, line); i += op.length; continue; }
      push('punc', c, line); i++;
    }
    return toks;
  }

  /* ---------------- parser ---------------- */
  function analyzeSources(sources) {
    const files = [], types = [], byName = new Map();

    sources.forEach(src => {
      const code = String(src.code || '').replace(/\r\n?/g, '\n');
      const lines = code.split('\n');
      const toks = lex(code);
      const file = { name: src.name, code, lines, loc: lines.filter(l => l.trim()).length, types: [] };
      files.push(file);

      // find type declarations anywhere (namespaces included)
      const n = toks.length;
      const bodyEnd = (k) => {
        let d = 0;
        for (let j = k; j < n; j++) {
          if (toks[j].v === '{') d++;
          else if (toks[j].v === '}') { d--; if (d === 0) return j; }
        }
        return n - 1;
      };
      const closeOf = (k, open, close) => {
        let d = 0;
        for (let j = k; j < n; j++) {
          if (toks[j].v === open) d++;
          else if (toks[j].v === close) { d--; if (!d) return j; }
        }
        return n - 1;
      };

      for (let k = 0; k < n; k++) {
        const t = toks[k];
        if (!(t.t === 'id' && TYPE_KW.has(t.v))) continue;
        const prev = toks[k - 1];
        if (prev && (prev.v === '.' || prev.v === ':')) continue;
        // walk back for modifiers / attributes
        let startK = k;
        let guard = 0;
        while (guard++ < 40) {
          const p = toks[startK - 1];
          if (!p) break;
          if (p.v === ']') {
            let d = 0, q = startK - 1;
            for (; q >= 0; q--) { if (toks[q].v === ']') d++; else if (toks[q].v === '[') { d--; if (!d) break; } }
            if (q < 0) break;
            startK = q;
          } else if (p.t === 'id' && MODIFIERS.has(p.v)) {
            startK--;
          } else break;
        }
        const parsed = parseTypeAt(startK);
        if (!parsed) continue;
        const ty = parsed.type;
        ty.file = file.name; ty.fileObj = file;
        ty.startLine = toks[startK].line;
        ty.endLine = toks[parsed.bodyEnd] ? toks[parsed.bodyEnd].line : ty.startLine;
        ty.loc = ty.endLine - ty.startLine + 1;
        types.push(ty); file.types.push(ty.name);
        if (!byName.has(ty.name)) byName.set(ty.name, ty);
        k = Math.max(k, parsed.after - 1);
      }

      function readAttrs(start) {
        let d = 0, j = start;
        const parts = [];
        for (; j < n; j++) {
          const v = toks[j].v;
          if (v === '[') { d++; if (d === 1) continue; }
          if (v === ']') { d--; if (d === 0) { j++; break; } }
          parts.push(v);
        }
        // names: identifiers directly followed by '(' or ',' or ']' at depth 1
        const names = [];
        let depth = 0;
        for (let q = start; q < j; q++) {
          const tk = toks[q].v;
          if (tk === '[') { depth++; continue; }
          if (tk === ']') { depth--; continue; }
          if (depth === 1 && toks[q].t === 'id' && !KEYWORDS.has(tk)) {
            const nx = toks[q + 1];
            if (nx && (nx.v === '(' || nx.v === ',' || nx.v === ']')) names.push(tk);
          }
        }
        return { end: j, names, raw: parts.join(' ') };
      }

      function parseTypeAt(start) {
        let j = start;
        let attrs = [], attrsRaw = '', mods = [];
        let guard = 0;
        while (j < n && guard++ < 60) {
          if (toks[j].v === '[') { const a = readAttrs(j); attrs = attrs.concat(a.names); attrsRaw += a.raw + ' '; j = a.end; continue; }
          if (toks[j].t === 'id' && MODIFIERS.has(toks[j].v)) { mods.push(toks[j].v); j++; continue; }
          break;
        }
        if (!toks[j] || !TYPE_KW.has(toks[j].v)) return null;
        const kind = toks[j].v; j++;
        if (!toks[j] || toks[j].t !== 'id') return null;
        const name = toks[j].v; j++;
        if (toks[j] && toks[j].v === '<') j = closeOf(j, '<', '>') + 1;
        let bases = [];
        if (toks[j] && toks[j].v === ':') {
          j++;
          let cur = [], depth = 0;
          while (j < n && toks[j].v !== '{' && toks[j].v !== 'where') {
            const v = toks[j].v;
            if (v === '<') depth++;
            if (v === '>') depth--;
            if (v === ',' && depth === 0) { if (cur.length) bases.push(cur.join('')); cur = []; }
            else if (v !== ' ') cur.push(v);
            j++;
          }
          if (cur.length) bases.push(cur.join(''));
        }
        while (j < n && toks[j].v !== '{' && toks[j].v !== ';') j++;
        const ty = {
          name, kind, modifiers: mods, attrs, attrsRaw: attrsRaw.trim(), bases,
          base: null, interfaces: [], file: '', fields: [], props: [], methods: [], enumNames: [],
          startLine: toks[start] ? toks[start].line : 1, endLine: 1, loc: 0,
          roles: [], issues: [], externals: [], narratives: []
        };
        ty.interfaces = bases.filter(b => /^I[A-Z]/.test(b.replace(/<.*$/, '')));
        ty.base = bases.find(b => !/^I[A-Z]/.test(b.replace(/<.*$/, ''))) || null;
        if (kind === 'enum') {
          if (toks[j] && toks[j].v === '{') {
            const e = bodyEnd(j);
            for (let q = j + 1; q < e; q++) if (toks[q].t === 'id' && !KEYWORDS.has(toks[q].v)) ty.enumNames.push(toks[q].v);
            ty.endLine = toks[e].line;
            return { type: ty, after: e + 1, bodyStart: j, bodyEnd: e };
          }
          ty.endLine = ty.startLine;
          return { type: ty, after: j, bodyStart: j, bodyEnd: j };
        }
        if (!toks[j] || toks[j].v === ';') {
          ty.endLine = ty.startLine;
          return { type: ty, after: j, bodyStart: j, bodyEnd: j };
        }
        const bs = j, be = bodyEnd(j);
        parseMembers(ty, bs, be);
        ty.endLine = toks[be] ? toks[be].line : ty.startLine;
        return { type: ty, after: be + 1, bodyStart: bs, bodyEnd: be };
      }

      function parseMembers(ty, bs, be) {
        let k = bs + 1, guard = 0;
        while (k < be && guard++ < 5000) {
          if (toks[k].v === ';') { k++; continue; }
          // nested type: skip whole body
          let p = k;
          let g2 = 0;
          while (toks[p] && toks[p].v === '[' && g2++ < 10) p = readAttrs(p).end;
          while (toks[p] && toks[p].t === 'id' && MODIFIERS.has(toks[p].v)) p++;
          if (toks[p] && TYPE_KW.has(toks[p].v)) {
            let q = p; while (q < be && toks[q].v !== '{' && toks[q].v !== ';') q++;
            k = (toks[q] && toks[q].v === '{') ? bodyEnd(q) + 1 : q + 1;
            continue;
          }

          let attrs = [], attrsRaw = '', mods = [];
          let g3 = 0;
          while (k < be && g3++ < 30) {
            if (toks[k].v === '[') { const a = readAttrs(k); attrs = attrs.concat(a.names); attrsRaw += a.raw + ' '; k = a.end; continue; }
            if (toks[k].t === 'id' && MODIFIERS.has(toks[k].v)) { mods.push(toks[k].v); k++; continue; }
            break;
          }
          if (k >= be) break;
          const declStart = k;
          // find separator at depth 0
          let d = 0, sep = -1, sepType = '';
          for (; k < be; k++) {
            const v = toks[k].v;
            if (v === '(' && d === 0) { sep = k; sepType = '('; break; }
            if (v === '<' || v === '[') { d++; continue; }
            if (v === '>' || v === ']') { d--; continue; }
            if (v === '{' && d === 0) { sep = k; sepType = '{'; break; }
            if (v === '=' && d === 0) { sep = k; sepType = '='; break; }
            if (v === ';' && d === 0) { sep = k; sepType = ';'; break; }
          }
          if (sep < 0) break;

          if (sepType === '(') {
            // method
            let nameIdx = sep - 1;
            while (nameIdx > declStart && toks[nameIdx].t !== 'id') nameIdx--;
            const name = toks[nameIdx] ? toks[nameIdx].v : '?';
            const close = closeOf(sep, '(', ')');
            const params = parseParams(sep + 1, close);
            let after = close + 1;
            let bodyStart = -1, bodyEndI = -1;
            if (toks[after] && toks[after].v === ':') { while (after < be && toks[after].v !== '{' && toks[after].v !== ';') after++; }
            if (toks[after] && toks[after].v === '{') { bodyStart = after; bodyEndI = bodyEnd(after); after = bodyEndI + 1; }
            else if (toks[after] && toks[after].v === '=>') {
              bodyStart = after; bodyEndI = after;
              while (bodyEndI < be && toks[bodyEndI].v !== ';') bodyEndI++;
              after = bodyEndI + 1;
            } else { after = after + 1; }
            const m = {
              name, params, modifiers: mods, attrs, attrsRaw: attrsRaw.trim(),
              returnType: toks.slice(declStart, nameIdx).map(t => t.v).join(' ').replace(/ ?([<>\[\],.]) ?/g, '$1'),
              line: toks[nameIdx].line, endLine: toks[bodyEndI] ? toks[bodyEndI].line : toks[nameIdx].line,
              bodyStart, bodyEnd: bodyEndI, isLifecycle: UNITY_MESSAGES.indexOf(name) >= 0,
              locals: [], usages: [], external: []
            };
            if (bodyStart >= 0) m.locals = findLocals(bodyStart, bodyEndI);
            ty.methods.push(m);
            k = Math.max(after, sep + 1);
            continue;
          }

          if (sepType === '{') {
            // property
            let nameIdx = sep - 1;
            while (nameIdx > declStart && toks[nameIdx].t !== 'id') nameIdx--;
            const name = toks[nameIdx] ? toks[nameIdx].v : '?';
            const close = bodyEnd(sep);
            const prop = {
              name, modifiers: mods, attrs, attrsRaw: attrsRaw.trim(),
              type: toks.slice(declStart, nameIdx).map(t => t.v).join(' ').replace(/ ?([<>\[\],.]) ?/g, '$1'),
              line: toks[nameIdx].line, endLine: toks[close] ? toks[close].line : toks[nameIdx].line,
              bodyStart: sep, bodyEnd: close, usages: []
            };
            ty.props.push(prop);
            k = close + 1;
            continue;
          }

          // field (possibly multiple declarators)
          let nameIdx = sep - 1;
          while (nameIdx > declStart && toks[nameIdx].t !== 'id') nameIdx--;
          if (!toks[nameIdx] || toks[nameIdx].t !== 'id') { k = sep + 1; continue; }
          const typeText = toks.slice(declStart, nameIdx).map(t => t.v).join(' ').replace(/ ?([<>\[\],.]) ?/g, '$1');
          const isSerialized = attrs.indexOf('SerializeField') >= 0 || attrs.indexOf('SerializeReference') >= 0 || (mods.indexOf('public') >= 0 && mods.indexOf('static') < 0 && mods.indexOf('const') < 0);
          let p2 = sep, curNameIdx = nameIdx;
          for (let dg = 0; dg < 60; dg++) {
            let init = '';
            if (toks[p2] && toks[p2].v === '=') {
              let e = p2 + 1, dd = 0;
              for (; e < be; e++) {
                const v = toks[e].v;
                const prevT = toks[e - 1];
                if (v === '(' || v === '[' || v === '{') dd++;
                else if (v === ')' || v === ']' || v === '}') dd--;
                else if (v === '<' && prevT && prevT.t === 'id' && /^[A-Z]/.test(prevT.v)) dd++;
                else if (v === '>' && dd > 0) dd--;
                else if (dd === 0 && (v === ';' || v === ',')) break;
              }
              init = toks.slice(p2 + 1, e).map(t => t.v).join(' ');
              p2 = e;
            }
            ty.fields.push({
              name: toks[curNameIdx].v, type: typeText, modifiers: mods, attrs, attrsRaw: attrsRaw.trim(),
              init, line: toks[curNameIdx].line, isSerialized,
              isPublic: mods.indexOf('public') >= 0, isStatic: mods.indexOf('static') >= 0,
              isConst: mods.indexOf('const') >= 0, usages: []
            });
            if (toks[p2] && toks[p2].v === ',') {
              p2++;
              let nx = p2;
              while (nx < be && toks[nx].t !== 'id') nx++;
              if (nx >= be) break;
              curNameIdx = nx; p2 = nx + 1;
              if (toks[p2] && toks[p2].v === ';') { ty.fields.push({ name: toks[nx].v, type: typeText, modifiers: mods, attrs, attrsRaw: attrsRaw.trim(), init: '', line: toks[nx].line, isSerialized, isPublic: mods.indexOf('public') >= 0, isStatic: mods.indexOf('static') >= 0, isConst: mods.indexOf('const') >= 0, usages: [] }); break; }
              continue;
            }
            break;
          }
          k = (toks[p2] && toks[p2].v === ';') ? p2 + 1 : p2;
        }
      }

      function findLocals(s, e) {
        const out = [];
        for (let k = s; k < e; k++) {
          const t = toks[k];
          if (t.t !== 'id') continue;
          const okType = t.v === 'var' || /^[A-Z]/.test(t.v);
          if (!okType) continue;
          let j = k + 1;
          if (toks[j] && toks[j].v === '[') { while (j < e && toks[j].v !== ']') j++; j++; }
          const nt = toks[j];
          if (!nt || nt.t !== 'id' || KEYWORDS.has(nt.v)) continue;
          const after = toks[j + 1];
          if (!after || ['=', ';', ',', ':', 'in'].indexOf(after.v) < 0) continue;
          const prev = toks[k - 1];
          if (!prev || ['.', 'new', 'return', 'out', 'ref', 'case', 'using', 'typeof', 'is', 'as'].indexOf(prev.v) >= 0) continue;
          out.push({ name: nt.v, type: t.v, line: nt.line, idx: j });
        }
        return out;
      }

      function parseParams(s, e) {
        const out = [];
        let cur = [], depth = 0;
        const flush = () => {
          if (!cur.length) return;
          let nameIdx = -1;
          for (let q = cur.length - 1; q >= 0; q--) if (cur[q].t === 'id' && !KEYWORDS.has(cur[q].v) && cur[q].v !== 'out' && cur[q].v !== 'ref') { nameIdx = q; break; }
          if (nameIdx >= 0) {
            const nm = cur[nameIdx];
            out.push({ name: nm.v, type: cur.slice(0, nameIdx).map(x => x.v).join(' ').replace(/ ?([<>\[\],.]) ?/g, '$1'), line: nm.line });
          }
          cur = [];
        };
        for (let q = s; q < e; q++) {
          const v = toks[q].v;
          if (v === '<' || v === '(' || v === '[') depth++;
          else if (v === '>' || v === ')' || v === ']') depth--;
          if (v === ',' && depth === 0) flush();
          else cur.push(toks[q]);
        }
        flush();
        return out;
      }
    });

    /* ---- global member index for cross-file traces ---- */
    const memberIndex = new Map();
    const indexMember = (ty, m, kind) => {
      if (!memberIndex.has(m.name)) memberIndex.set(m.name, []);
      memberIndex.get(m.name).push({ owner: ty, member: m, kind });
    };
    types.forEach(ty => {
      ty.fields.forEach(f => indexMember(ty, f, 'field'));
      ty.props.forEach(p => indexMember(ty, p, 'property'));
      ty.methods.forEach(m => indexMember(ty, m, 'method'));
    });

    /* ---- usage analysis ---- */
    types.forEach(ty => {
      ty.methods.forEach(m => {
        if (m.bodyStart < 0) return;
        const toks = ty.fileObj ? lexWithCache(ty.fileObj) : null;
        // handled in second pass below
      });
    });

    function lexWithCache(file) {
      if (!file._toks) file._toks = lex(file.code);
      return file._toks;
    }

    types.forEach(ty => {
      const toks = lexWithCache(ty.fileObj);
      const fieldMap = new Map();
      ty.fields.forEach(f => fieldMap.set(f.name, { kind: 'field', ref: f }));
      ty.props.forEach(p => fieldMap.set(p.name, { kind: 'property', ref: p }));
      const localDeclIdx = new Set();

      ty.methods.forEach(m => {
        if (m.bodyStart < 0) return;
        const scopes = new Map(fieldMap);
        m.params.forEach(p => scopes.set(p.name, { kind: 'param', ref: p }));
        m.locals.forEach(l => { scopes.set(l.name, { kind: 'local', ref: l }); localDeclIdx.add(l.idx); });

        for (let k = m.bodyStart; k <= m.bodyEnd; k++) {
          const t = toks[k];
          if (!t || t.t !== 'id') continue;
          const sym = scopes.get(t.v);
          if (!sym) continue;
          if (localDeclIdx.has(k)) continue;
          const prev = toks[k - 1], prev2 = toks[k - 2], next = toks[k + 1];
          if (prev && prev.v === '.' && !(prev2 && prev2.v === 'this')) continue;
          if (prev && (prev.v === 'nameof' || prev.v === 'typeof')) continue;
          let rw = 'read';
          if (next && ASSIGN_OPS.has(next.v)) rw = next.v === '=' ? 'write' : 'readwrite';
          else if (next && (next.v === '++' || next.v === '--')) rw = 'readwrite';
          else if (prev && (prev.v === '++' || prev.v === '--')) rw = 'readwrite';
          else if (prev && prev.v === 'out') rw = 'write';
          const codeLine = ty.fileObj.lines[t.line - 1] || '';
          const rec = {
            line: t.line, method: m.name, rw, code: codeLine.trim(),
            file: ty.fileObj.name, owner: ty.name, external: false
          };
          if (sym.kind === 'field' || sym.kind === 'property') {
            sym.ref.usages.push(rec);
            if (!m.usages.some(u => u.member === sym.ref.name && u.line === t.line && u.rw === rw)) {
              m.usages.push({ member: sym.ref.name, kind: sym.kind, line: t.line, rw, code: rec.code });
            }
          }
        }

        // external chains: A.B.C -> last known member in another type
        for (let k = m.bodyStart; k <= m.bodyEnd; k++) {
          const t = toks[k];
          if (!t || t.t !== 'id') continue;
          const prev = toks[k - 1];
          if (prev && prev.v === '.') continue;
          if (KEYWORDS.has(t.v)) continue;
          const chain = [t.v];
          let q = k;
          while (toks[q + 1] && toks[q + 1].v === '.' && toks[q + 2] && toks[q + 2].t === 'id') {
            chain.push(toks[q + 2].v); q += 2;
          }
          if (chain.length < 2) { k = q; continue; }
          if (chain[0] === 'this') continue;
          let hit = null, segIdx = -1;
          for (let ci = chain.length - 1; ci >= 1; ci--) {
            const cands = memberIndex.get(chain[ci]);
            if (!cands) continue;
            const ext = cands.filter(c => c.owner.name !== ty.name);
            if (ext.length) { hit = ext[0]; segIdx = ci; break; }
          }
          if (!hit) { k = q; continue; }
          const via = chain.slice(0, segIdx + 1).join('.');
          const next = toks[q + 1];
          let rw = 'read';
          if (next && ASSIGN_OPS.has(next.v)) rw = next.v === '=' ? 'write' : 'readwrite';
          const codeLine = ty.fileObj.lines[t.line - 1] || '';
          hit.member.usages.push({
            line: t.line, method: m.name, rw, code: codeLine.trim(), file: ty.fileObj.name,
            owner: ty.name, external: true, via
          });
          const rec = { target: hit.owner.name, member: hit.member.name, kind: hit.kind, via, line: t.line, method: m.name, rw };
          if (!ty.externals.some(e => e.target === rec.target && e.member === rec.member && e.line === rec.line && e.method === rec.method)) ty.externals.push(rec);
          m.external.push(rec);
          k = q;
        }
      });
    });

    /* ---- roles, issues, narrative ---- */
    types.forEach(ty => {
      ty.roles = classify(ty);
      ty.issues = detectIssues(ty, types, byName);
      ty.narrative = buildNarrative(ty);
      ty.stats = {
        fields: ty.fields.length, serialized: ty.fields.filter(f => f.isSerialized).length,
        methods: ty.methods.length, props: ty.props.length,
        reads: ty.fields.reduce((a, f) => a + f.usages.filter(u => u.rw !== 'write').length, 0),
        writes: ty.fields.reduce((a, f) => a + f.usages.filter(u => u.rw !== 'read').length, 0)
      };
    });

    const edges = [];
    types.forEach(ty => {
      const seen = new Set();
      ty.externals.forEach(e => {
        const key = ty.name + '>' + e.target;
        if (seen.has(key)) return;
        seen.add(key);
        edges.push({ from: ty.name, to: e.target, label: e.via, count: ty.externals.filter(x => x.target === e.target).length });
      });
      if (ty.base && byName.has(ty.base)) edges.push({ from: ty.name, to: ty.base, label: '상속', inherit: true });
    });

    return { files, types, byName, edges, unresolved: findUnresolved(types, byName) };
  }

  /* ---------------- roles ---------------- */
  function classify(ty) {
    const roles = [];
    const names = ty.methods.map(m => m.name);
    const has = n => names.indexOf(n) >= 0;
    const field = n => ty.fields.find(f => f.name === n);
    const add = (name, tone, evidence, score) => roles.push({ name, tone, evidence, score: score == null ? 50 : score });

    if (ty.kind === 'enum') {
      add('열거형 상수', 'data', ['키/상태 값을 이름으로 묶은 enum (' + ty.enumNames.length + '개 항목)'], 95);
      return roles.sort((a, b) => b.score - a.score);
    }
    if (ty.base === 'ScriptableObject') {
      const ev = ['ScriptableObject를 상속 → 씬에 붙지 않는 데이터 에셋'];
      if (/CreateAssetMenu/.test(ty.attrsRaw)) ev.push('CreateAssetMenu로 Project 창에서 .asset 생성 가능');
      add('데이터 에셋', 'data', ev, 95);
      if (ty.fields.every(f => !f.isSerialized)) add('빈 데이터 컨테이너', 'data', ['직렬화된 필드가 없음'], 30);
      return roles;
    }
    if (ty.base === 'MonoBehaviour' || ty.base === 'Behaviour' || ty.base === 'Component' || ty.base) {
      const isSingleton = ty.props.some(p => p.name === 'Instance') || ty.fields.some(f => f.name === 'instance');
      if (isSingleton && /Manager/i.test(ty.name)) add('싱글턴 매니저', 'system', ['정적 Instance 프로퍼티로 전역 접근점 제공', ty.modifiers.indexOf('static') >= 0 ? 'static 클래스' : 'DontDestroyOnLoad로 씬 전환에도 유지'], 92);
      else if (isSingleton) add('싱글턴', 'system', ['정적 Instance 접근점 보유'], 75);
      if (ty.interfaces.length && ty.interfaces.some(i => /Pointer|Drag|Submit|Select/.test(i))) add('UI 이벤트 핸들러', 'ui', ['EventSystem 인터페이스 구현: ' + ty.interfaces.join(', '), 'OnPointerEnter/Exit에서 시각 반응 처리'], 90);
      if (ty.methods.some(m => /Instantiate/.test(m.usages.map(u => u.code).join('')))) add('스폰/발사 컨트롤러', 'action', ['Instantiate로 프리팹을 런타임 생성', field('fireRate') ? 'fireRate로 연사 간격 제어' : '발사 위치/프리팹을 직렬화 필드로 주입'], 88);
      if (ty.methods.some(m => /Destroy\s*\(\s*gameObject/.test(m.usages.map(u => u.code).join('')))) add('수명 관리', 'action', ['Destroy(gameObject, t)로 오브젝트 수명 예약'], 80);
      if (ty.methods.some(m => /transform\s*\.\s*(Translate|position)/.test(m.usages.map(u => u.code).join('')))) add('이동 제어', 'action', ['Update에서 transform을 직접 갱신 (프레임 독립: Time.deltaTime)'], 85);
      if (ty.methods.some(m => /Keyboard|Gamepad|Key\./.test(m.usages.map(u => u.code).join('')))) add('입력 처리', 'system', ['Input System(Keyboard/Gamepad)에서 입력을 읽어 이동/공격으로 변환'], 84);
      if (ty.methods.some(m => /FindGameObjectsWithTag|FindFirstObjectByType|FindObjectOfType/.test(m.usages.map(u => u.code).join('')))) add('대상 탐색', 'system', ['태그/타입으로 씬 오브젝트를 검색해 참조 획득'], 78);
      if (ty.methods.some(m => /LoadSceneAsync|SceneManager/.test(m.usages.map(u => u.code).join('')))) add('씬 전환/로딩 연출', 'system', ['SceneManager로 비동기 로드', '진행률을 UI에 반영'], 90);
      if (ty.methods.some(m => /TextMeshProUGUI|TMP_Text|\.text\s*=/.test(m.usages.map(u => u.code).join('')))) add('UI 텍스트 표시', 'ui', ['TMP 컴포넌트의 text를 코드에서 갱신'], 76);
      if (ty.methods.some(m => /ClampToBounds|WorldToViewportPoint/.test(m.usages.map(u => u.code).join(''))) || ty.methods.some(m => m.name === 'ClampToBounds')) add('화면 경계 제한', 'action', ['카메라 뷰포트 좌표로 위치를 Clamp'], 70);
      if (!roles.length) add('MonoBehaviour 컴포넌트', 'system', (ty.base ? ty.base + '를 상속' : 'Unity 컴포넌트'), 55);
      return roles.sort((a, b) => b.score - a.score);
    }
    add(ty.kind === 'interface' ? '인터페이스' : '일반 C# 클래스', 'plain', ['Unity 타입을 상속하지 않는 순수 C# 타입'], 60);
    return roles;
  }

  /* ---------------- issues ---------------- */
  function detectIssues(ty, types, byName) {
    const out = [];
    const add = (sev, title, detail, evidence) => out.push({ sev, title, detail, evidence: evidence || '' });
    const codeOf = m => m.usages.map(u => u.code).join('\n');

    const baseName = (ty.file || '').replace(/\.cs$/i, '');
    const isComponent = ty.base === 'MonoBehaviour' || (ty.base && byName.has(ty.base)) || ty.interfaces.some(i => /Handler$/.test(i));
    if (ty.kind === 'class' && isComponent && baseName && baseName !== ty.name) {
      add('high', '파일명 ≠ 클래스명', 'Unity는 MonoBehaviour의 파일명과 클래스명이 같아야 Inspector에서 컴포넌트로 붙일 수 있습니다. "' + ty.name + '.cs"로 바꾸세요.', baseName + '.cs ↔ ' + ty.name);
    }
    ty.fields.forEach(f => {
      const reads = f.usages.filter(u => u.rw !== 'write').length;
      const writes = f.usages.filter(u => u.rw !== 'read').length;
      if (!f.isSerialized && reads === 0 && writes > 0) {
        add('medium', '쓰기만 하는 필드: ' + f.name, '값을 저장하지만 어디에서도 읽지 않습니다. 죽은 코드이거나 로직 누락입니다.', 'L' + f.line + ' · write ' + writes + ' / read 0');
      }
      if (f.isSerialized && f.usages.length === 0 && f.attrs.indexOf('SerializeField') >= 0) {
        // serialized but never touched in code: inspector-only is normal, only flag if suspicious name
      }
      if (/^(chddkf|temp|test|asdf|qwer)/i.test(f.name)) {
        add('low', '의미를 알 수 없는 필드명: ' + f.name, '오타이거나 실험용 필드로 보입니다. 이름을 의도에 맞게 바꾸세요.', 'L' + f.line + ' · ' + f.type);
      }
    });
    ty.methods.forEach(m => {
      const codes = codeOf(m);
      if (m.name === 'Update' || m.name === 'FixedUpdate' || m.name === 'LateUpdate') {
        if (/FindGameObjectsWithTag|FindFirstObjectByType|FindObjectOfType|GetComponent</.test(codes)) {
          add('high', m.name + ' 안에서 매 프레임 탐색', 'Find*/GetComponent를 프레임마다 호출하면 비용이 큽니다. 결과를 캐시하거나 재탐색 간격을 두세요.', 'L' + m.line + ' · ' + m.name);
        }
        if (/Camera\.main/.test(codes)) {
          add('low', m.name + '에서 Camera.main 접근', 'Camera.main은 내부적으로 FindGameObjectsWithTag를 수행합니다. Start에서 캐시하세요.', 'L' + m.line);
        }
      }
      if (m.name === 'Start' && /GetComponent</.test(codes) && !/if\s*\(\s*\w+\.?.*!= null/.test(codes)) {
        const gm = codes.match(/GetComponent<([^>]+)>/);
        add('medium', 'GetComponent 결과 null 미검사', '컴포넌트가 없으면 다음 줄에서 NullReferenceException이 발생합니다.' + (gm ? ' (' + gm[1] + ')' : ''), 'L' + m.line + ' · Start');
      }
      if (/Random\.Range\(0,\s*\w+\.Length\)/.test(codes)) {
        add('medium', '빈 배열 인덱스 위험', '배열이 비어 있으면 Random.Range(0,0)=0 → [0] 접근에서 IndexOutOfRangeException. Length 검사를 추가하세요.', 'L' + m.line);
      }
    });
    if (ty.fields.some(f => f.isStatic) || ty.props.some(p => /static/.test(p.modifiers.join(' ')))) {
      const st = ty.fields.find(f => f.isStatic);
      add('low', '정적 상태 유지', 'static 필드는 씬을 넘어 값이 남습니다. 씬 재진입 시 초기화 시점을 명시하세요.', st ? 'L' + st.line + ' · static ' + st.name : 'static 멤버');
    }
    if (/CreateAssetMenu/.test(ty.attrsRaw)) {
      const fn = (ty.attrsRaw.match(/fileName\s*=\s*"([^"]+)"/) || [])[1];
      if (fn) {
        const dup = types.filter(t => t !== ty && (t.attrsRaw.match(/fileName\s*=\s*"([^"]+)"/) || [])[1] === fn);
        if (dup.length) add('medium', 'CreateAssetMenu fileName 중복', '"' + fn + '" 이름이 ' + dup.map(d => d.name).join(', ') + '와 겹칩니다. 에셋 생성 시 파일명이 충돌합니다.', ty.name + ' ↔ ' + dup.map(d => d.name).join(', '));
      }
    }
    return out;
  }

  /* ---------------- narrative ---------------- */
  function buildNarrative(ty) {
    const out = [];
    const role = ty.roles[0] ? ty.roles[0].name : '타입';
    const base = ty.base ? ty.base + '를 상속' : '베이스 타입 없음';
    out.push('`' + ty.name + '`은(는) ' + base + (ty.interfaces.length ? ', ' + ty.interfaces.join('·') + ' 구현' : '') + '한 **' + role + '**입니다.');
    const life = ty.methods.filter(m => m.isLifecycle);
    if (life.length) {
      out.push('생명주기: ' + life.map(m => '`' + m.name + '`').join(' → ') + ' 순서로 호출됩니다.');
    }
    const used = ty.fields.filter(f => f.usages.length);
    const unused = ty.fields.filter(f => !f.usages.length && f.attrs.indexOf('SerializeField') < 0 && !f.isPublic);
    if (used.length) {
      out.push('추적된 필드 ' + used.length + '개 — ' + used.slice(0, 4).map(f => '`' + f.name + '`(' + f.usages.length + '회)').join(', ') + '.');
    }
    if (unused.length) out.push('코드에서 전혀 쓰이지 않는 필드: ' + unused.map(f => '`' + f.name + '`').join(', ') + '.');
    return out;
  }

  function findUnresolved(types, byName) {
    const out = [];
    const seen = new Set();
    types.forEach(ty => {
      const toks = lexWithCache(ty.fileObj);
      ty.methods.forEach(m => {
        if (m.bodyStart < 0) return;
        for (let k = m.bodyStart; k <= m.bodyEnd; k++) {
          const t = toks[k];
          if (!t || t.t !== 'id' || !/^[A-Z]/.test(t.v)) continue;
          const next = toks[k + 1];
          if (!next || next.v !== '.') continue;
          const prev = toks[k - 1];
          if (prev && (prev.v === '.' || prev.v === 'new' || prev.v === ':')) continue;
          if (byName.has(t.v) || KNOWN_TYPES.has(t.v)) continue;
          const localNames = ty.fields.map(f=>f.name).concat(ty.props.map(p=>p.name));
          if (localNames.indexOf(t.v) >= 0) continue;
          if (seen.has(t.v)) continue;
          seen.add(t.v);
          out.push({ name: t.v, usedBy: ty.name, line: t.line, method: m.name });
        }
      });
    });
    return out;
  }

  function lexWithCache(file) {
    if (!file._toks) file._toks = lex(file.code);
    return file._toks;
  }

  const api = { analyzeSources, lex, classify };
  root.UnityLensCore = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
