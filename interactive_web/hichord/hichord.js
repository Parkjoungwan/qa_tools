(() => {
  const initApp = () => {
    const $ = (sel)=> document.querySelector(sel);

    const NOTE_NAMES = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"];
    const wrap12 = (n)=>((n%12)+12)%12;
    const SCALE = { Major:[0,2,4,5,7,9,11], Minor:[0,2,3,5,7,8,10] };

    const SEVEN_SET = [
      { type:"deg", val:0 }, { type:"deg", val:1 }, { type:"deg", val:3 }, { type:"deg", val:4 },
      { type:"off", val:1 }, { type:"off", val:3 }, { type:"off", val:6 },
    ];

    const TABLE = {
      Major:{ Triad:{0:[0,4,7],1:[0,3,7],3:[0,4,7],4:[0,4,7]},
              Seventh:{0:[0,4,7,11],1:[0,3,7,10],3:[0,4,7,11],4:[0,4,7,10]} },
      Minor:{ Triad:{0:[0,3,7],1:[0,2,7],3:[0,3,7],4:[0,4,7]},
              Seventh:{0:[0,3,7,10],1:[0,3,6,10],3:[0,3,7,10],4:[0,4,7,10]} }
    };
    const BLACK_TABLE = { Triad:[0,4,7], Seventh:[0,4,7,11] };

    const state = { key:0, mode:"Major", quality:"Triad", inversion:0, baseOct:4, preset:"C", presetType:"harm", bpm:100 };
    let audioSetupDone = false;

    // --- Audio Nodes ---
    const masterOut = new Tone.Gain(1);
    const masterLimiter = new Tone.Limiter(-1).toDestination();
    masterOut.connect(masterLimiter);

    const chordDucker = new Tone.Gain(1.0);
    const chordBus = new Tone.Gain(0.9).connect(chordDucker).connect(masterOut);
    const drumBus = new Tone.Gain(1.0).connect(masterOut);

    const chordSynth = new Tone.PolySynth(Tone.Synth, { maxPolyphony: 24, volume:-6 }).connect(chordBus);
    chordSynth.set({ envelope:{ attack:0.01, decay:0.18, sustain:0.8, release:0.5 }, oscillator:{ type:"triangle" } });
    Tone.Transport.bpm.value = state.bpm;

    // --- New Sampler-based Drums ---
    const SAMPLES = {
      kick: "/assets/kick.wav",
      snare: "/assets/snare.wav",
      hat: "/assets/hat.wav",
      crunch: "/assets/crunch.wav",
      clap: "/assets/clap.wav",
      bell: "/assets/bell.wav",
    };
    const samplers = {};

    // --- Deferred Audio Setup ---
    function setupDeferredAudio(){
      // Load samplers
      for (const [k, url] of Object.entries(SAMPLES)) {
        samplers[k] = new Tone.Player({ url, volume: -2 }).connect(drumBus);
      }
    }

    const ui = { keyName: $("#keyName"), modeName: $("#modeName"), qualityName: $("#qualityName"), invName: $("#invName"), octName: $("#octName"), presetName: $("#presetName"), bpmName: $("#bpmName"), recName: $("#recName"), recDot: $("#recDot"), compass: $("#compass"), tracks: $("#tracks") };
    function updateStatus(){ ui.keyName.textContent = NOTE_NAMES[state.key]; ui.modeName.textContent = state.mode; ui.qualityName.textContent = state.quality; ui.invName.textContent = ["Root","1st","2nd","3rd"][state.inversion] ?? "Root"; ui.octName.textContent = String(state.baseOct); ui.presetName.textContent = state.preset + (state.presetType==="drum"?" (Drum)":""); ui.bpmName.textContent = String(state.bpm); [...ui.compass.querySelectorAll(".dir")].forEach(el=> el.classList.toggle("active", el.dataset.dir===state.preset)); }
    updateStatus();

    const menuBtn = $("#menuBtn"), panelWrap = $("#panelWrap");
    function setMenu(open){ panelWrap.classList.toggle("open", open); menuBtn.setAttribute("aria-expanded", String(open)); }
    menuBtn.addEventListener("click", ()=> setMenu(!panelWrap.classList.contains("open")));
    function autoFold(){ const small = window.innerWidth<=900 || window.innerHeight<=620; setMenu(!small); }
    window.addEventListener("resize", autoFold); autoFold();
    const closeMenuOnOutsideClick = (e) => { if (!panelWrap.classList.contains("open")) return; if (!panelWrap.contains(e.target) && !menuBtn.contains(e.target)) setMenu(false); };
    document.addEventListener("click", closeMenuOnOutsideClick);
    document.addEventListener("touchend", closeMenuOnOutsideClick);

    function applyInversion(semis, inv){ const L=semis.length, t=Math.min(inv,L-1); for(let i=0;i<t;i++){ const x=semis.shift(); semis.push(x+12);} }
    function openVoicing(semis){ semis.sort((a,b)=>a-b); for(let i=0;i<semis.length-1;i++){ while(semis[i+1]-semis[i]<3){ semis[i+1]+=12; } } }
    function drop2IfSeventh(semis){ if(semis.length===4){ semis.sort((a,b)=>a-b); semis[2]-=12; semis.sort((a,b)=>a-b); } }
    function chordSeven(slotId, ctx){
      const idx = parseInt(slotId.slice(1),10), spec = SEVEN_SET[idx];
      let rootSemi, semis;
      if (spec.type === "deg"){
        rootSemi = ctx.key + SCALE[ctx.mode][spec.val];
        const ints = TABLE[ctx.mode][ctx.quality][spec.val].slice();
        semis = ints.map(iv => rootSemi + iv);
      } else {
        rootSemi = ctx.key + spec.val;
        const ints = (ctx.quality==="Seventh" ? BLACK_TABLE.Seventh : BLACK_TABLE.Triad).slice();
        semis = ints.map(iv => rootSemi + iv);
      }
      applyInversion(semis, Math.min(ctx.inversion, semis.length-1));
      const baseMidi = 12*(ctx.baseOct+1);
      semis = semis.map(n => n + baseMidi);
      if(ctx.quality==="Seventh") drop2IfSeventh(semis);
      openVoicing(semis);
      if(semis.length===3){ const top=Math.max(...semis); semis.push(top+12); semis.sort((a,b)=>a-b); }
      semis.sort((a,b)=>a-b);
      const MIN_MIDI = 48, MAX_MIDI = 84;
      if (Math.min(...semis) < MIN_MIDI) { for (let i=0;i<semis.length;i++) semis[i]+=12; }
      if (Math.max(...semis) > MAX_MIDI) { for (let i=0;i<semis.length;i++) semis[i]-=12; }
      for (let i=0;i<semis.length-1;i++){ while(semis[i+1]-semis[i]<3){ semis[i+1]+=12; } }
      return semis.map(m => Tone.Frequency(m,"midi").toFrequency());
    }
    const chordNow = (slotId)=> chordSeven(slotId, state);

    function triggerDrum(slotId, when){
      const map = { K0:"kick", K1:"snare", K2:"hat", K3:"crunch", K4:"clap", K5:"bell" };
      const id = map[slotId];
      if (!id || !samplers[id]) return;
      samplers[id].start(when);
      // Sidechain ducking for kick
      if (id === "kick"){
        chordDucker.gain.cancelScheduledValues(when);
        chordDucker.gain.setValueAtTime(chordDucker.gain.value, when);
        chordDucker.gain.linearRampToValueAtTime(0.7, when+0.05);
        chordDucker.gain.linearRampToValueAtTime(1.0, when+0.2);
      }
    }
    function isDrumCtx(ctx){ return ctx.presetType==="drum"; }

    const keyElBySlot = { K0: document.querySelector('[data-slot="K0"]'), K1: document.querySelector('[data-slot="K1"]'), K2: document.querySelector('[data-slot="K2"]'), K3: document.querySelector('[data-slot="K3"]'), K4: document.querySelector('[data-slot="K4"]'), K5: document.querySelector('[data-slot="K5"]'), K6: document.querySelector('[data-slot="K6"]'), };
    const held = new Map();
    const KEY_TO_SLOT = { q:"K0", w:"K1", e:"K2", r:"K3", "2":"K4", "3":"K5", "4":"K6" };
    const pressDebounce = {};
    const DEBOUNCE_THRESHOLD = 50; // ms

    async function pressSlot(slotId, keyChar){
      const now = performance.now();
      if (pressDebounce[slotId] && (now - pressDebounce[slotId] < DEBOUNCE_THRESHOLD)) {
        return; // Debounce the call
      }
      pressDebounce[slotId] = now;

      if (!audioSetupDone) {
        await Tone.start();
        setupDeferredAudio();
        audioSetupDone = true;
      }

      if(isDrumCtx(state)){
        triggerDrum(slotId, Tone.now());
        keyElBySlot[slotId]?.classList.add("active");
        setTimeout(()=> keyElBySlot[slotId]?.classList.remove("active"), 90);
        if(rec.active){
          const ctx = snapshotCtx();
          if (master.loopLen > 0){ const tAbs = Tone.Transport.seconds; pushOverdubEvent(slotId, tAbs, 0.001, ctx); }
          else { const tRel = Tone.now()-rec.startAt; rec.events.push({ time:tRel, slotId, dur:0.001, ctx }); }
        }
        return;
      }

      if(held.has(keyChar)) return;
      const notes = chordNow(slotId);
      chordSynth.triggerAttack(notes);
      held.set(keyChar, { notes, slotId });
      keyElBySlot[slotId]?.classList.add("active");

      if (rec.active && !rec.activeDown[slotId]){
        if (master.loopLen > 0){ rec.activeDown[slotId] = { t0Abs: Tone.Transport.seconds, ctx: snapshotCtx() }; }
        else { rec.activeDown[slotId] = { t0Rel: Tone.now()-rec.startAt, ctx: snapshotCtx() }; }
      }
    }
    function releaseKey(keyChar){ if(isDrumCtx(state)) return; const e = held.get(keyChar); if(!e) return; chordSynth.triggerRelease(e.notes); keyElBySlot[e.slotId]?.classList.remove("active"); held.delete(keyChar); if (rec.active && rec.activeDown[e.slotId]){ if (master.loopLen > 0){ const { t0Abs, ctx } = rec.activeDown[e.slotId]; const dur = Math.max(0.04, Tone.Transport.seconds - t0Abs); pushOverdubEvent(e.slotId, t0Abs, dur, ctx); } else { const { t0Rel, ctx } = rec.activeDown[e.slotId]; const dur = Math.max(0.04, (Tone.now()-rec.startAt) - t0Rel); rec.events.push({ time:t0Rel, slotId:e.slotId, dur, ctx }); } delete rec.activeDown[e.slotId]; } }
    Object.entries(keyElBySlot).forEach(([sid, el])=>{ el.addEventListener("mousedown", ()=> pressSlot(sid, "mouse_"+sid)); el.addEventListener("mouseup", ()=> releaseKey("mouse_"+sid)); el.addEventListener("mouseleave",()=> releaseKey("mouse_"+sid)); el.addEventListener("touchstart",(ev)=>{ ev.preventDefault(); pressSlot(sid, "touch_"+sid); }, {passive:false}); el.addEventListener("touchend", ()=> releaseKey("touch_"+sid)); });

    function nearestVoicing(prevFreqs, nextFreqs){ const toMidi = f => Tone.Frequency(f).toMidi(); const pf = prevFreqs.map(toMidi).sort((a,b)=>a-b); const cand = nextFreqs.map(toMidi).sort((a,b)=>a-b); const mapped = cand.map((m,i)=>{ const ref = pf[Math.min(i, pf.length-1)]; const opts = [m-12, m, m+12]; let best = opts[0], bestd = Math.abs(opts[0]-ref); for(const o of opts){ const d=Math.abs(o-ref); if(d<bestd){best=o; bestd=d;} } return best; }).sort((a,b)=>a-b); return mapped.map(m=> Tone.Frequency(m,"midi").toFrequency()); }
    function retargetHeld(){ if(isDrumCtx(state)) return; for(const [k,e] of held){ const fresh = chordNow(e.slotId); const guided = nearestVoicing(e.notes, fresh); chordSynth.triggerRelease(e.notes); chordSynth.triggerAttack(guided); e.notes = guided; } }

    const PRESETS = { N:{type:"harm", mode:"Major",quality:"Triad",inversion:0,baseOct:4}, NE:{type:"harm", mode:"Major",quality:"Seventh",inversion:2,baseOct:4}, E:{type:"harm", mode:"Major",quality:"Triad",inversion:1,baseOct:5}, SE:{type:"harm", mode:"Major",quality:"Seventh",inversion:1,baseOct:3}, S:{type:"drum", kit:"StdA"}, SW:{type:"harm", mode:"Minor",quality:"Seventh",inversion:1,baseOct:4}, W:{type:"harm", mode:"Minor",quality:"Triad",inversion:2,baseOct:3}, NW:{type:"harm", mode:"Minor",quality:"Seventh",inversion:2,baseOct:5}, C:{} };
    function applyPreset(name){ if(name==="C") return; const p=PRESETS[name]; if(!p) return; if(p.type==="drum"){ state.presetType="drum"; state.preset=name; }else{ state.presetType="harm"; state.mode=p.mode; state.quality=p.quality; state.inversion=p.inversion; state.baseOct=p.baseOct; state.preset=name; } updateStatus(); retargetHeld(); }
    document.querySelectorAll(".dir").forEach(el=> el.addEventListener("click", ()=>applyPreset(el.dataset.dir)));

    // Drum Pad Clicks
    document.querySelectorAll(".ko-pad").forEach(el=>{
      el.addEventListener("click", async ()=>{
        if (state.presetType!=="drum") applyPreset("S"); // Switch to drum mode if not already
        await Tone.start();
        const id = el.dataset.ko; // "kick", "snare", etc.
        const now = Tone.now();
        // Map pad id to key slot
        const map = {kick:"K0", snare:"K1", hat:"K2", crunch:"K3", clap:"K4", bell:"K5"};
        const slot = map[id];
        if (slot) triggerDrum(slot, now);
        el.classList.add("active"); setTimeout(()=> el.classList.remove("active"), 120);
      });
    });

    const TRACK_KEYS = ['z','x','c','v'];
    const tracks = TRACK_KEYS.map((k,i)=>({ key:k, part:null, enabled:false, loopEnd:0, events:[], idx:i, addedAt:0 }));
    const master = { loopLen: 0, phase0: null };
    function ensureTransport(){ if(Tone.Transport.state!=="started") Tone.Transport.start(); }
    const rec = { active:false, startAt:0, events:[], activeDown:{} };
    const snapshotCtx = ()=> ({ key:state.key, mode:state.mode, quality:state.quality, inversion:state.inversion, baseOct:state.baseOct, presetType:state.presetType });
    function renderTracks(){ ui.tracks.innerHTML=""; tracks.forEach((t,i)=>{ const div=document.createElement("div"); div.className="track"; const st=t.enabled?"on":"off"; div.innerHTML=`<div class="hdr"><div>Track ${i+1} <span class="kbd">${t.key}</span></div><div class="tag ${st}">${t.enabled?"ON":"OFF"}</div></div><div class="help">${t.part?`events: ${t.events.length}, loop: ${(master.loopLen||t.loopEnd).toFixed(2)}s`:`empty`}</div><div class="delHint ${(!t.enabled && t.part) ? "show": ""}">OFF상태에서 ${t.key.toUpperCase()} 2초 길게 → 삭제</div>`; ui.tracks.appendChild(div); }); }
    renderTracks();
    function pushOverdubEvent(slotId, tAbs, dur, ctx){ const L = master.loopLen; const start = ((tAbs % L)+L)%L; let remain = dur, curStart = start; while (remain > 0){ const room = L - curStart; const d = Math.min(remain, room); rec.events.push({ time: curStart, slotId, dur: d, ctx }); remain -= d; curStart = 0; } }
    function startRec(){ rec.active=true; rec.events=[]; rec.activeDown={}; rec.startAt=Tone.now(); ui.recName.textContent="REC"; ui.recDot.classList.add("on"); ensureTransport(); }
    function computePhaseAnchor(loopLen){ const now = Tone.Transport.seconds; const eps = 0.02; return Math.ceil((now+eps)/loopLen)*loopLen; }
    function stopRec(){ const recordingStopTime = Tone.now(); if (master.loopLen > 0){ for (const [sid, mark] of Object.entries(rec.activeDown)) { if (!mark) continue; const { t0Abs, ctx } = mark; const dur = Math.max(0.04, Tone.Transport.seconds - t0Abs); pushOverdubEvent(sid, t0Abs, dur, ctx); } } else { for (const [sid, mark] of Object.entries(rec.activeDown)) { if (!mark) continue; const { t0Rel, ctx } = mark; const dur = Math.max(0.04, (recordingStopTime - rec.startAt) - t0Rel); rec.events.push({ time:t0Rel, slotId:sid, dur, ctx }); } } rec.active=false; rec.activeDown={}; ui.recName.textContent="Idle"; ui.recDot.classList.remove("on"); if(rec.events.length===0) return; let loopEnd; if (master.loopLen > 0) { loopEnd = master.loopLen; } else { loopEnd = Math.max(recordingStopTime - rec.startAt, 0.25); } if(master.loopLen===0){ master.loopLen = loopEnd; ensureTransport(); master.phase0 = computePhaseAnchor(master.loopLen); tracks.forEach(t=>{ if(t.part){ t.part.loopEnd = master.loopLen; t.part.stop(0); t.part.start(master.phase0, 0); } }); } else { loopEnd = master.loopLen; } assignToTrackWithPolicy(rec.events, loopEnd); }
    function buildPart(events, loopLen){ const part = new Tone.Part((time, ev)=>{ if (isDrumCtx(ev.ctx)) { triggerDrum(ev.slotId, time); } else { const notes = chordSeven(ev.slotId, ev.ctx); chordSynth.triggerAttackRelease(notes, ev.dur, time); } }, events.map(ev=>({ time: ev.time, slotId: ev.slotId, dur: ev.dur, ctx: ev.ctx }))); part.loop=true; part.loopEnd=loopLen; const startAt = master.phase0 ?? 0; part.start(startAt, 0); return part; }
    function assignToTrackWithPolicy(events, loopLen){ let idx = tracks.findIndex(t=> !t.part); if(idx<0){ let latestIdx = 0; let latestAt = -Infinity; tracks.forEach((t,i)=>{ if(t.addedAt>latestAt){ latestAt=t.addedAt; latestIdx=i; } }); idx = latestIdx; clearTrack(idx); } const t = tracks[idx]; t.events = events.map(ev=>({...ev})); t.loopEnd = loopLen; t.part = buildPart(t.events, loopLen); t.enabled = true; t.part.mute = false; t.addedAt = performance.now(); ensureTransport(); renderTracks(); }
    function clearTrack(idx){ const t = tracks[idx]; if(t.part){ t.part.stop(0); t.part.dispose(); } t.part=null; t.enabled=false; t.events=[]; t.loopEnd=0; t.addedAt=0; }
    function toggleTrackByKey(k){ const idx = ['z','x','c','v'].indexOf(k); if(idx<0) return; const t = tracks[idx]; if(!t.part) return; t.enabled = !t.enabled; t.part.mute = !t.enabled; renderTracks(); }
    const trackHold = {};
    function handleTrackKeyDown(k){ const idx = ['z','x','c','v'].indexOf(k); if(idx<0) return false; const t = tracks[idx]; if(!t.part){ return toggleTrackByKey(k), true; } toggleTrackByKey(k); if(!t.enabled){ if(trackHold[k]?.timer) clearTimeout(trackHold[k].timer); trackHold[k] = { startAt: performance.now(), timer: setTimeout(()=>{ clearTrack(idx); renderTracks(); trackHold[k] = null; }, 2000) }; } return true; }
    function handleTrackKeyUp(k){ const h = trackHold[k]; if(h && h.timer){ clearTimeout(h.timer); trackHold[k] = null; } }

    function transpose(semi){ state.key=wrap12(state.key+semi); updateStatus(); retargetHeld(); }
    function toggleQuality(){ state.quality=(state.quality==="Triad")?"Seventh":"Triad"; state.inversion=Math.min(state.inversion,(state.quality==="Seventh")?3:2); updateStatus(); retargetHeld(); }
    function cycleInv(){ const m=(state.quality==="Seventh")?3:2; state.inversion=(state.inversion+1)%(m+1); updateStatus(); retargetHeld(); }
    function toggleMode(){ state.mode=(state.mode==="Major")?"Minor":"Major"; updateStatus(); retargetHeld(); }
    function shiftOct(d){ state.baseOct=Math.max(1,Math.min(7,state.baseOct+d)); updateStatus(); retargetHeld(); }

    function toggleRec(){ if(!rec.active) startRec(); else stopRec(); }
    let spacePressed = false;
    window.addEventListener("keydown",(e)=>{ const k = e.key; if (e.code === "Space" || k === " " || k === "Spacebar") { e.preventDefault(); if (!spacePressed) spacePressed = true; return; } if (k.startsWith("Arrow")) e.preventDefault(); if(e.repeat) return; if(TRACK_KEYS.includes(k)){ handleTrackKeyDown(k); return; } const dir = ({ u:"NW",i:"N",o:"NE",j:"W",l:"E",m:"SW", ",":"S", ".":"SE", U:"NW",I:"N",O:"NE",J:"W",L:"E",M:"SW", "<":"S", ">":"SE" })[k]; if(dir){ applyPreset(dir); return; } const slotId = KEY_TO_SLOT[k]; if(slotId){ e.preventDefault(); pressSlot(slotId, k); return; } if(k==="ArrowLeft"){ transpose(e.shiftKey?-12:-1); } else if(k==="ArrowRight"){ transpose(e.shiftKey?+12:+1); } else if(k==="ArrowUp"){ cycleInv(); } else if(k==="ArrowDown"){ toggleQuality(); } else if(k==="m"||k==="M"){ toggleMode(); } else if(k===">"||k==="."){ shiftOct(+1); } else if(k===","||k==="<"){ shiftOct(-1); } });
    window.addEventListener("keyup",(e)=>{ const k = e.key; if (e.code === "Space" || k === " " || k === "Spacebar") { if (spacePressed) toggleRec(); spacePressed = false; e.preventDefault(); return; } if(TRACK_KEYS.includes(k)){ handleTrackKeyUp(k); return; } const slotId = KEY_TO_SLOT[k]; if(slotId) releaseKey(k); });
    window.addEventListener("blur",()=>{ for(const k of [...held.keys()]) releaseKey(k); spacePressed=false; });
  };

  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', initApp); } else { initApp(); }
})();