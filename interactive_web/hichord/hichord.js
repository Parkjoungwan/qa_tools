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

    // --- Audio Nodes (Creation only) ---
    const masterOut = new Tone.Gain(1);
    const masterLimiter = new Tone.Limiter(-1).toDestination();
    masterOut.connect(masterLimiter);

    const chordDucker = new Tone.Gain(1.0);
    const chordBus = new Tone.Gain(0.9).connect(chordDucker).connect(masterOut);
    // drum bus (OP-KO chain): Sampler -> KO FX -> Lo-fi stage -> master
    const drumBus = new Tone.Gain(1.0);
    // OP-KO FX (punch-in): stutter/gater/tape/wow/bits/lpf/rev/pump
    const fxStutter = new Tone.FeedbackDelay(0.06, 0.25); fxStutter.wet.value = 0;
    const fxGate   = new Tone.Tremolo(8, 0.9);    fxGate.wet.value   = 0;
    const fxTapeRP = new Tone.PitchShift({ pitch: 0 });   // tape-stop 흉내(피치→-12로 램프)
    const fxWow    = new Tone.Vibrato(0.3, 0.03);         fxWow.wet.value    = 0;
    const fxBits   = new Tone.BitCrusher(8);              fxBits.wet ? fxBits.wet.value=0 : 0;
    const fxLP     = new Tone.Filter(12000, "lowpass", -24);
    const fxRev    = new Tone.Reverb({ decay: 0.7, wet: 0 });
    // 기존 lo-fi 스테이지(색감 유지)
    const drumCrusher = new Tone.BitCrusher(4);
    const drumLP = new Tone.Filter(7800, "lowpass", -24);
    const drumDrive = new Tone.Distortion(0.12);
    const drumFlutter = new Tone.Vibrato(0.28, 0.02);
    // chain: Drum → (KO FX들 직렬) → Lo-fi → master
    drumBus.chain(fxStutter, fxGate, fxTapeRP, fxWow, fxBits, fxLP, fxRev, drumCrusher, drumLP, drumDrive, drumFlutter, masterOut);

    // OP-KO: 샘플 뱅크(1~4)
    const BANKS = {
      1: { kck:"/assets/b1/kick.wav", snr:"/assets/b1/snare.wav", cht:"/assets/b1/hat_closed.wav", ohat:"/assets/b1/hat_open.wav", clp:"/assets/b1/clap.wav", tom:"/assets/b1/tom.wav", rid:"/assets/b1/ride.wav" },
      2: { kck:"/assets/b2/kick.wav", snr:"/assets/b2/snare.wav", cht:"/assets/b2/hat_closed.wav", ohat:"/assets/b2/hat_open.wav", clp:"/assets/b2/clap.wav", tom:"/assets/b2/tom.wav", rid:"/assets/b2/ride.wav" },
      3: { kck:"/assets/b3/kick.wav", snr:"/assets/b3/snare.wav", cht:"/assets/b3/hat_closed.wav", ohat:"/assets/b3/hat_open.wav", clp:"/assets/b3/clap.wav", tom:"/assets/b3/tom.wav", rid:"/assets/b3/ride.wav" },
      4: { kck:"/assets/b4/kick.wav", snr:"/assets/b4/snare.wav", cht:"/assets/b4/hat_closed.wav", ohat:"/assets/b4/hat_open.wav", clp:"/assets/b4/clap.wav", tom:"/assets/b4/tom.wav", rid:"/assets/b4/ride.wav" },
    };
    let currentBank = 1;
    const samplers = {};
    const hatOpenGate = new Tone.Gain(1).connect(drumBus);
    let ohPlayer = null;

    function loadBank(n){
      currentBank = n;
      const S = BANKS[n];
      // dispose & rebuild
      for (const k of Object.keys(samplers)) { try{ samplers[k].dispose(); }catch{} delete samplers[k]; }
      if (ohPlayer){ try{ ohPlayer.dispose(); }catch{} ohPlayer=null; }
      for (const [k, url] of Object.entries(S)) {
        if (k === "ohat") continue; // open-hat는 별도 게이트로
        samplers[k] = new Tone.Player({ url, volume: -2 }).connect(drumBus);
      }
      ohPlayer = new Tone.Player({ url: S.ohat, volume: -2 }).connect(hatOpenGate);
      // UI 표시
      document.querySelectorAll(".bank-btn").forEach(b=> b.classList.toggle("active", Number(b.dataset.bank)===n));
    }
    loadBank(1);

    // --- Deferred Audio Setup ---
    function setupDeferredAudio(){
      fxGate.start();
      // Drum Bus FX
      const drumCrusher = new Tone.BitCrusher(4);
      const drumLP = new Tone.Filter(7800, "lowpass", -24);
      const drumDrive = new Tone.Distortion(0.12);
      const drumFlutter = new Tone.Vibrato(0.28, 0.02);
      drumBus.chain(drumCrusher, drumLP, drumDrive, drumFlutter, masterOut);

      // Vinyl Noise
      const vinylNoise = new Tone.Noise("pink");
      const vinylHP = new Tone.Filter(2500, "highpass", -12);
      const vinylLP = new Tone.Filter(8000, "lowpass", -12);
      const vinylCrush = new Tone.BitCrusher(6);
      const vinylGain = new Tone.Gain(0.02).connect(masterOut);
      vinylNoise.chain(vinylHP, vinylLP, vinylCrush, vinylGain);
      vinylNoise.start();
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

    // per-slot trim info: 0~1 (비율), reverse flag
    const TRIM = {
      kck:{ start:0, end:1, rev:false },
      snr:{ start:0, end:1, rev:false },
      cht:{ start:0, end:1, rev:false },
      ohat:{ start:0, end:1, rev:false },
      clp:{ start:0, end:1, rev:false },
      tom:{ start:0, end:1, rev:false },
      rid:{ start:0, end:1, rev:false },
    };
    function triggerWithTrim(player, id, when){
      if (!player || !player.buffer || !player.buffer.duration) { player?.start(when); return; }
      const d = player.buffer.duration;
      let { start, end, rev } = TRIM[id];
      start = Math.max(0, Math.min(start, 0.95));
      end   = Math.max(start+0.05, Math.min(end, 1));
      const off = start * d;
      const dur = (end - start) * d;
      player.reverse = !!rev;
      player.start(when, off, dur);
    }

    function triggerDrum(slotId, when){
      // K0..K6 -> kck/snr/cht/tom/ohat/clp/rid
      const map = { K0:"kck", K1:"snr", K2:"cht", K3:"tom", K4:"ohat", K5:"clp", K6:"rid" };
      const id = map[slotId];
      if (!id) return;
      if (id === "ohat"){
        // open hat trigger + choke reset
        hatOpenGate.gain.cancelScheduledValues(when);
        hatOpenGate.gain.setValueAtTime(1, when);
        triggerWithTrim(ohPlayer, "ohat", when);
      } else {
        // close hat 가 오픈햇 초크
        if (id === "cht"){
          hatOpenGate.gain.cancelScheduledValues(when);
          hatOpenGate.gain.setValueAtTime(hatOpenGate.gain.value, when);
          hatOpenGate.gain.linearRampToValueAtTime(0, when + 0.005);
          hatOpenGate.gain.linearRampToValueAtTime(1, when + 0.08);
        }
        triggerWithTrim(samplers[id], id, when);
      }
      // 킥 → 코드 버스 펌프 (사이드체인)
      if (id === "kck"){
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

    async function pressSlot(slotId, keyChar){
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

    // OP-KO pads & FX
    document.querySelectorAll(".ko-pad").forEach(el=>{
      el.addEventListener("click", async ()=>{
        if (state.presetType!=="drum") applyPreset("S");
        await Tone.start();
        const id = el.dataset.ko;
        const now = Tone.now();
        const map = {kck:"K0", snr:"K1", cht:"K2", tom:"K3", ohat:"K4", clp:"K5", rid:"K6"};
        const slot = map[id];
        if (slot) triggerDrum(slot, now);
        el.classList.add("active"); setTimeout(()=> el.classList.remove("active"), 120);
      });
    });
    document.querySelectorAll(".fx").forEach(el=>{
      const code = el.dataset.fx;
      el.addEventListener("mousedown", ()=> koFxDown(({stut:"a",gate:"s",tape:"d",wow:"f",bits:"g",lpf:"h",rev:"j",pump:"k"})[code]));
      el.addEventListener("mouseup",   ()=> koFxUp  (({stut:"a",gate:"s",tape:"d",wow:"f",bits:"g",lpf:"h",rev:"j",pump:"k"})[code]));
      el.addEventListener("mouseleave",()=> koFxUp  (({stut:"a",gate:"s",tape:"d",wow:"f",bits:"g",lpf:"h",rev:"j",pump:"k"})[code]));
    });

    // FX knobs binding
    (function bindFxKnobs(){
      const q = (s)=>document.querySelector(s);
      q(".kn.stut")?.addEventListener("input", e=> fxStutter.wet.rampTo(parseFloat(e.target.value), 0.05));
      q(".kn.gate")?.addEventListener("input", e=> fxGate.wet.rampTo(parseFloat(e.target.value), 0.05));
      q(".kn.wow") ?.addEventListener("input", e=> fxWow.wet.rampTo(parseFloat(e.target.value), 0.05));
      q(".kn.bits")?.addEventListener("input", e=> { fxBits.bits = parseInt(e.target.value,10); });
      q(".kn.lpf") ?.addEventListener("input", e=> fxLP.frequency.rampTo(parseFloat(e.target.value), 0.05));
      q(".kn.rev") ?.addEventListener("input", e=> fxRev.wet.rampTo(parseFloat(e.target.value), 0.05));
    })();

    // Bank buttons & number keys
    document.querySelectorAll(".bank-btn").forEach(b=>{
      b.addEventListener("click", ()=> loadBank(Number(b.dataset.bank)));
    });
    window.addEventListener("keydown", (e)=>{
      if (e.repeat) return;
      if (["1","2","3","4"].includes(e.key)){
        loadBank(Number(e.key));
      }
    });

    // Trim bindings
    const trimSlotSel = document.getElementById("trimSlot");
    const trimStart = document.getElementById("trimStart");
    const trimEnd   = document.getElementById("trimEnd");
    const trimRev   = document.getElementById("trimRev");
    function syncTrimUI(){
      const t = TRIM[trimSlotSel.value]; if(!t) return;
      trimStart.value = t.start; trimEnd.value = t.end; trimRev.checked = t.rev;
    }
    trimSlotSel?.addEventListener("change", syncTrimUI);
    trimStart?.addEventListener("input", ()=>{ const t=TRIM[trimSlotSel.value]; t.start=parseFloat(trimStart.value); if(t.end<=t.start) { t.end=Math.min(1,t.start+0.05); trimEnd.value=t.end; }});
    trimEnd  ?.addEventListener("input", ()=>{ const t=TRIM[trimSlotSel.value]; t.end=parseFloat(trimEnd.value); if(t.end<=t.start){ t.start=Math.max(0,t.end-0.05); trimStart.value=t.start; }});
    trimRev  ?.addEventListener("change",()=>{ const t=TRIM[trimSlotSel.value]; t.rev=!!trimRev.checked; });
    syncTrimUI();

    const TRACK_KEYS = ['z','x','c','v'];
    const tracks = TRACK_KEYS.map((k,i)=>({ key:k, part:null, enabled:false, loopEnd:0, events:[], idx:i, addedAt:0 }));
    const master = { loopLen: 0, phase0: null };
    function ensureTransport(){ if(Tone.Transport.state!=="started") Tone.Transport.start(); }
    const rec = { active:false, startAt:0, events:[], activeDown:{} };
    const snapshotCtx = ()=> ({ key:state.key, mode:state.mode, quality:state.quality, inversion:state.inversion, baseOct:state.baseOct, presetType:state.presetType });
    function renderTracks(){ ui.tracks.innerHTML=""; tracks.forEach((t,i)=>{ const div=document.createElement("div"); div.className="track"; const st=t.enabled?"on":"off"; div.innerHTML=`<div class="hdr"><div>Track ${i+1} <span class="kbd">${t.key}</span></div><div class="tag ${st}">${t.enabled?"ON":"OFF"}</div></div><div class="help">${t.part?`events: ${t.events.length}, loop: ${(master.loopLen||t.loopEnd).toFixed(2)}s`:`empty`}</div><div class="delHint ${(!t.enabled && t.part) ? "show": ""}">OFF상태에서 ${t.key.toUpperCase()} 2초 길게 → 삭제</div>`; ui.tracks.appendChild(div); }); }
    renderTracks();

    // === Step Repeat Grid (16 steps @ 16n) ===
    const sgGrid = document.getElementById("sgGrid");
    const sgTargetSel = document.getElementById("sgTarget");
    const SG = { steps: Array(16).fill(false), target:"snr", seq:null };
    function buildSgUI(){
      if(!sgGrid) return;
      sgGrid.innerHTML = "";
      for(let i=0;i<16;i++){
        const b=document.createElement("button");
        b.className="sg-cell"; b.textContent=String(i+1);
        b.addEventListener("click", ()=>{
          SG.steps[i]=!SG.steps[i];
          b.classList.toggle("on", SG.steps[i]);
          rebuildSgSeq();
        });
        sgGrid.appendChild(b);
      }
    }
    function rebuildSgSeq(){
      // dispose
      if(SG.seq){ try{ SG.seq.stop(0); SG.seq.dispose(); }catch{} SG.seq=null; }
      // 빈 그리드면 종료
      if(!SG.steps.some(Boolean)) return;
      ensureTransport();
      const onSteps = SG.steps.map((v,i)=> v ? i : -1).filter(i=> i>=0);
      SG.seq = new Tone.Sequence((time, stepIdx)=>{
        const id = SG.target;
        // open hat choke if needed
        if (id==="cht"){
          hatOpenGate.gain.cancelScheduledValues(time);
          hatOpenGate.gain.setValueAtTime(hatOpenGate.gain.value, time);
          hatOpenGate.gain.linearRampToValueAtTime(0, time + 0.005);
          hatOpenGate.gain.linearRampToValueAtTime(1, time + 0.08);
        }
        if (id==="ohat") triggerWithTrim(ohPlayer, "ohat", time);
        else triggerWithTrim(samplers[id], id, time);
      }, onSteps, "16n");
      SG.seq.loop = true;
      const startAt = master.phase0 ?? 0;
      SG.seq.start(startAt);
    }
    buildSgUI();
    sgTargetSel?.addEventListener("change", ()=>{ SG.target = sgTargetSel.value; rebuildSgSeq(); });
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
    // OP-KO punch-in handler (drum preset에서만 반응)
    function koFxDown(k){
      if (state.presetType !== "drum") return false;
      const now = Tone.now();
      if (k==="a"||k==="A"){ fxStutter.wet.rampTo(0.8, 0.02); return true; }       // STUT
      if (k==="s"||k==="S"){ fxGate.wet.rampTo(0.8, 0.02);    return true; }       // GATE
      if (k==="d"||k==="D"){ fxTapeRP.pitch = -12; setTimeout(()=>{ fxTapeRP.pitch=0; }, 220); return true; } // TAPE one-shot
      if (k==="f"||k==="F"){ fxWow.wet.rampTo(0.7, 0.02);     return true; }       // WOW
      if (k==="g"||k==="G"){ fxBits.bits = 4; /* wet없으면 그대로 */ return true; } // BITS
      if (k==="h"||k==="H"){ fxLP.frequency.rampTo(2400, 0.05); return true; }     // LPF sweep down
      if (k==="j"||k==="J"){ fxRev.wet.rampTo(0.35, 0.02);    return true; }       // REV
      if (k==="k"||k==="K"){ // PUMP: 순간 전체 드럼 볼륨 살짝 내렸다 복귀(킥 유사)
        drumBus.gain.cancelScheduledValues(now);
        drumBus.gain.setValueAtTime(drumBus.gain.value, now);
        drumBus.gain.linearRampToValueAtTime(0.75, now+0.02);
        drumBus.gain.linearRampToValueAtTime(1.0,  now+0.20);
        return true;
      }
      return false;
    }
    function koFxUp(k){
      if (state.presetType !== "drum") return false;
      if (k==="a"||k==="A"){ fxStutter.wet.rampTo(0, 0.05); return true; }
      if (k==="s"||k==="S"){ fxGate.wet.rampTo(0, 0.05);    return true; }
      if (k==="f"||k==="F"){ fxWow.wet.rampTo(0, 0.05);     return true; }
      if (k==="g"||k==="G"){ fxBits.bits = 8; return true; }
      if (k==="h"||k==="H"){ fxLP.frequency.rampTo(12000, 0.2); return true; }
      if (k==="j"||k==="J"){ fxRev.wet.rampTo(0, 0.15);     return true; }
      return false;
    }

    window.addEventListener("keydown",(e)=>{
      const k = e.key;
      if (e.code === "Space" || k === " " || k === "Spacebar") { e.preventDefault(); if (!spacePressed) spacePressed = true; return; }
      if (k.startsWith("Arrow")) e.preventDefault();
      if(e.repeat) return;

      if(TRACK_KEYS.includes(k)){ handleTrackKeyDown(k); return; }
      if(koFxDown(k)){ // 드럼 FX 키는 여기서 소비
        const fxBtn = ({a:"stut",s:"gate",d:"tape",f:"wow",g:"bits",h:"lpf",j:"rev",k:"pump"})[k.toLowerCase()];
        fxBtn && document.querySelector(`[data-fx="${fxBtn}"]`)?.classList.add("on");
        return;
      }

      const dir = ({ u:"NW",i:"N",o:"NE",j:"W",l:"E",m:"SW", ",":"S", ".":"SE",
                     U:"NW",I:"N",O:"NE",J:"W",L:"E",M:"SW", "<":"S", ">":"SE" })[k];
      if(dir){ applyPreset(dir); return; }

      const slotId = KEY_TO_SLOT[k];
      if(slotId){ e.preventDefault(); pressSlot(slotId, k); return; }

      if(k==="ArrowLeft"){ transpose(e.shiftKey?-12:-1); }
      else if(k==="ArrowRight"){ transpose(e.shiftKey?+12:+1); }
      else if(k==="ArrowUp"){ cycleInv(); }
      else if(k==="ArrowDown"){ toggleQuality(); }
      else if(k==="m"||k==="M"){ toggleMode(); }
      else if(k===">"||k==="."){ shiftOct(+1); }
      else if(k===","||k==="<"){ shiftOct(-1); }
    });

    window.addEventListener("keyup",(e)=>{
      const k = e.key;
      if (e.code === "Space" || k === " " || k === "Spacebar") { if (spacePressed) toggleRec(); spacePressed = false; e.preventDefault(); return; }
      if(TRACK_KEYS.includes(k)){ handleTrackKeyUp(k); return; }
      if(koFxUp(k)){
        const fxBtn = ({a:"stut",s:"gate",f:"wow",g:"bits",h:"lpf",j:"rev"})[k.toLowerCase()];
        fxBtn && document.querySelector(`[data-fx="${fxBtn}"]`)?.classList.remove("on");
        return;
      }
      const slotId = KEY_TO_SLOT[k];
      if(slotId) releaseKey(k);
    });
    window.addEventListener("blur",()=>{ for(const k of [...held.keys()]) releaseKey(k); spacePressed=false; });
  };

  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', initApp); } else { initApp(); }
})();
