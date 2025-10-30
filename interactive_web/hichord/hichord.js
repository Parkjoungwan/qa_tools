(() => {
  const initApp = () => {
    const $ = (sel)=> document.querySelector(sel);

    const NOTE_NAMES = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"];
    const wrap12 = (n)=>((n%12)+12)%12;
    const SCALE = { Major:[0,2,4,5,7,9,11], Minor:[0,2,3,5,7,8,10] };
    const MAX_LOOP_SECONDS = 30;

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
    let tracks = [];
    let trackIdCounter = 0;
    let audioSetupDone = false;

    const masterOut = new Tone.Gain(1);
    const masterLimiter = new Tone.Limiter(-1).toDestination();
    masterOut.connect(masterLimiter);

    const chordDucker = new Tone.Gain(1.0);
    const chordBus = new Tone.Gain(0.9).connect(chordDucker).connect(masterOut);
    const drumBus = new Tone.Gain(1.0).connect(masterOut);

    const chordSynth = new Tone.PolySynth(Tone.Synth, { maxPolyphony: 32, volume:-6 }).connect(chordBus);
    chordSynth.set({ envelope:{ attack:0.01, decay:0.18, sustain:0.8, release:0.5 }, oscillator:{ type:"triangle" } });
    Tone.Transport.bpm.value = state.bpm;
    Tone.Transport.loop = true;
    Tone.Transport.loopEnd = MAX_LOOP_SECONDS;

    const SAMPLES = { kick: "/assets/kick.wav", snare: "/assets/snare.wav", hat: "/assets/hat.wav", crunch: "/assets/crunch.wav", clap: "/assets/clap.wav", bell: "/assets/bell.wav" };
    const samplers = {};

    function setupDeferredAudio(){
      for (const [k, url] of Object.entries(SAMPLES)) {
        samplers[k] = new Tone.Player({ url, volume: -2 }).connect(drumBus);
      }
    }

    const ui = { keyName: $("#keyName"), modeName: $("#modeName"), qualityName: $("#qualityName"), invName: $("#invName"), octName: $("#octName"), presetName: $("#presetName"), bpmName: $("#bpmName"), recName: $("#recName"), recDot: $("#recDot"), compass: $("#compass"), tracks: $("#tracks"), playhead: $("#playhead"), ruler: $("#ruler"), trackLanes: $("#track-lanes"), timeline: $("#timeline"), playPauseBtn: $("#playPauseBtn") };
    function updateStatus(){ ui.keyName.textContent = NOTE_NAMES[state.key]; ui.modeName.textContent = state.mode; ui.qualityName.textContent = state.quality; ui.invName.textContent = ["Root","1st","2nd","3rd"][state.inversion] ?? "Root"; ui.octName.textContent = String(state.baseOct); ui.presetName.textContent = state.preset + (state.presetType==="drum"?" (Drum)":""); ui.bpmName.textContent = String(state.bpm); [...ui.compass.querySelectorAll(".dir")].forEach(el=> el.classList.toggle("active", el.dataset.dir===state.preset)); }
    updateStatus();

    function setupTimeline(){
      const ruler = ui.ruler;
      if (!ruler) return;
      ruler.innerHTML = '';
      for (let i = 0; i < MAX_LOOP_SECONDS; i++) {
        const tick = document.createElement('div');
        tick.className = 'ruler-tick';
        tick.style.left = `${(i / MAX_LOOP_SECONDS) * 100}%`;
        if (i % 5 === 0) {
          tick.classList.add('major');
          tick.dataset.time = `${i}s`;
        }
        ruler.appendChild(tick);
      }
    }
    setupTimeline();

    let isDraggingPlayhead = false;

    function updatePlayhead(){
      if (!ui.playhead || isDraggingPlayhead) return;
      const percent = (Tone.Transport.seconds % MAX_LOOP_SECONDS) / MAX_LOOP_SECONDS;
      ui.playhead.style.left = `${percent * 100}%`;
    }
    function animate() {
      updatePlayhead();

      const now = Tone.Transport.seconds;
      for (const track of tracks) {
        track.part.mute = !(now >= track.startTime && now < track.endTime);
      }

      requestAnimationFrame(animate);
    }
    animate();

    function updatePlayButton(state = Tone.Transport.state) {
      if (ui.playPauseBtn) {
        ui.playPauseBtn.textContent = state === 'started' ? '❚❚ Pause' : '▶ Play';
      }
    }
    updatePlayButton();

    async function togglePlay() {
      if (!audioSetupDone) {
        await Tone.start();
        setupDeferredAudio();
        audioSetupDone = true;
      }
      if (Tone.Transport.state === 'started') {
        Tone.Transport.pause();
      } else {
        Tone.Transport.start();
      }
    }

    ui.playPauseBtn?.addEventListener('click', togglePlay);
    Tone.Transport.on('start', () => updatePlayButton('started'));
    Tone.Transport.on('stop', () => updatePlayButton('stopped'));
    Tone.Transport.on('pause', () => updatePlayButton('paused'));

    function handleTimelineInteraction(e) {
      if (!audioSetupDone) return;
      const timelineRect = ui.timeline.getBoundingClientRect();
      const percent = Math.max(0, Math.min(1, (e.clientX - timelineRect.left) / timelineRect.width));
      const newTime = percent * MAX_LOOP_SECONDS;
      Tone.Transport.seconds = newTime;
      ui.playhead.style.left = `${percent * 100}%`;

      isDraggingPlayhead = true;

      const onMouseMove = (moveE) => {
        const percent = Math.max(0, Math.min(1, (moveE.clientX - timelineRect.left) / timelineRect.width));
        const newTime = percent * MAX_LOOP_SECONDS;
        Tone.Transport.seconds = newTime;
        ui.playhead.style.left = `${percent * 100}%`;
      };

      const onMouseUp = () => {
        isDraggingPlayhead = false;
        window.removeEventListener('mousemove', onMouseMove);
        window.removeEventListener('mouseup', onMouseUp);
      };

      window.addEventListener('mousemove', onMouseMove);
      window.addEventListener('mouseup', onMouseUp);
    }

    ui.timeline.addEventListener('mousedown', handleTimelineInteraction);


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
      if (pressDebounce[slotId] && (now - pressDebounce[slotId] < DEBOUNCE_THRESHOLD)) return;
      pressDebounce[slotId] = now;

      if (!audioSetupDone) {
        await Tone.start();
        setupDeferredAudio();
        audioSetupDone = true;
      }

      const transportTime = Tone.Transport.seconds;

      if(isDrumCtx(state)){
        triggerDrum(slotId, Tone.now());
        keyElBySlot[slotId]?.classList.add("active");
        setTimeout(()=> keyElBySlot[slotId]?.classList.remove("active"), 90);
        if(rec.active){
          const ctx = snapshotCtx();
          rec.events.push({ time: transportTime, slotId, dur: 0.001, ctx });
        }
        return;
      }

      if(held.has(keyChar)) return;
      const notes = chordNow(slotId);
      chordSynth.triggerAttack(notes);
      held.set(keyChar, { notes, slotId });
      keyElBySlot[slotId]?.classList.add("active");

      if (rec.active && !rec.activeDown[slotId]){
        rec.activeDown[slotId] = { t0: transportTime, ctx: snapshotCtx() };
      }
    }
    function releaseKey(keyChar){ 
      if(isDrumCtx(state)) return;
      const e = held.get(keyChar);
      if(!e) return;
      chordSynth.triggerRelease(e.notes);
      keyElBySlot[e.slotId]?.classList.remove("active");
      held.delete(keyChar);
      if (rec.active && rec.activeDown[e.slotId]){
        const { t0, ctx } = rec.activeDown[e.slotId];
        const dur = Math.max(0.04, Tone.Transport.seconds - t0);
        rec.events.push({ time: t0, slotId: e.slotId, dur, ctx });
        delete rec.activeDown[e.slotId];
      }
    }
    Object.entries(keyElBySlot).forEach(([sid, el])=>{ el.addEventListener("mousedown", ()=> pressSlot(sid, "mouse_"+sid)); el.addEventListener("mouseup", ()=> releaseKey("mouse_"+sid)); el.addEventListener("mouseleave",()=> releaseKey("mouse_"+sid)); el.addEventListener("touchstart",(ev)=>{ ev.preventDefault(); pressSlot(sid, "touch_"+sid); }, {passive:false}); el.addEventListener("touchend", ()=> releaseKey("touch_"+sid)); });

    function nearestVoicing(prevFreqs, nextFreqs){ const toMidi = f => Tone.Frequency(f).toMidi(); const pf = prevFreqs.map(toMidi).sort((a,b)=>a-b); const cand = nextFreqs.map(toMidi).sort((a,b)=>a-b); const mapped = cand.map((m,i)=>{ const ref = pf[Math.min(i, pf.length-1)]; const opts = [m-12, m, m+12]; let best = opts[0], bestd = Math.abs(opts[0]-ref); for(const o of opts){ const d=Math.abs(o-ref); if(d<bestd){best=o; bestd=d;} } return best; }).sort((a,b)=>a-b); return mapped.map(m=> Tone.Frequency(m,"midi").toFrequency()); }
    function retargetHeld(){ if(isDrumCtx(state)) return; for(const [k,e] of held){ const fresh = chordNow(e.slotId); const guided = nearestVoicing(e.notes, fresh); chordSynth.triggerRelease(e.notes); chordSynth.triggerAttack(guided); e.notes = guided; } }

    const PRESETS = { N:{type:"harm", mode:"Major",quality:"Triad",inversion:0,baseOct:4}, NE:{type:"harm", mode:"Major",quality:"Seventh",inversion:2,baseOct:4}, E:{type:"harm", mode:"Major",quality:"Triad",inversion:1,baseOct:5}, SE:{type:"harm", mode:"Major",quality:"Seventh",inversion:1,baseOct:3}, S:{type:"drum", kit:"StdA"}, SW:{type:"harm", mode:"Minor",quality:"Seventh",inversion:1,baseOct:4}, W:{type:"harm", mode:"Minor",quality:"Triad",inversion:2,baseOct:3}, NW:{type:"harm", mode:"Minor",quality:"Seventh",inversion:2,baseOct:5}, C:{} };
    function applyPreset(name){ if(name==="C") return; const p=PRESETS[name]; if(!p) return; if(p.type==="drum"){ state.presetType="drum"; state.preset=name; }else{ state.presetType="harm"; state.mode=p.mode; state.quality=p.quality; state.inversion=p.inversion; state.baseOct=p.baseOct; state.preset=name; } updateStatus(); retargetHeld(); }
    document.querySelectorAll(".dir").forEach(el=> el.addEventListener("click", ()=>applyPreset(el.dataset.dir)));

    document.querySelectorAll(".ko-pad").forEach(el=>{
      el.addEventListener("click", async ()=>{
        if (state.presetType!=="drum") applyPreset("S");
        await Tone.start();
        const id = el.dataset.ko;
        const now = Tone.now();
        const map = {kick:"K0", snare:"K1", hat:"K2", crunch:"K3", clap:"K4", bell:"K5"};
        const slot = map[id];
        if (slot) triggerDrum(slot, now);
        el.classList.add("active"); setTimeout(()=> el.classList.remove("active"), 120);
      });
    });

    function ensureTransport(){ if(Tone.Transport.state!=="started") Tone.Transport.start(); }
    const rec = { active:false, events:[], activeDown:{} };
    const snapshotCtx = ()=> ({ key:state.key, mode:state.mode, quality:state.quality, inversion:state.inversion, baseOct:state.baseOct, presetType:state.presetType });
    
    function startRec(){ 
      rec.active=true; 
      rec.events=[]; 
      rec.activeDown={}; 
      ui.recName.textContent="REC"; 
      ui.recDot.classList.add("on"); 
      ensureTransport(); 
    }

    function stopRec(){
      rec.active=false;
      for (const [sid, mark] of Object.entries(rec.activeDown)) {
        if (!mark) continue;
        const { t0, ctx } = mark;
        const dur = Math.max(0.04, Tone.Transport.seconds - t0);
        rec.events.push({ time: t0, slotId: sid, dur, ctx });
      }
      rec.activeDown={};
      ui.recName.textContent="Idle";
      ui.recDot.classList.remove("on");
      if(rec.events.length === 0) return;

      const times = rec.events.map(e => e.time);
      const endTimes = rec.events.map(e => e.time + e.dur);
      const startTime = Math.min(...times);
      const endTime = Math.max(...endTimes);

      createLoopTrack(rec.events, startTime, endTime);
    }

    function createLoopTrack(events, startTime, endTime) {
      const id = trackIdCounter++;
      const duration = endTime - startTime;

      const domElement = document.createElement('div');
      domElement.className = 'loop-bar';
      domElement.style.left = `${(startTime / MAX_LOOP_SECONDS) * 100}%`;
      domElement.style.width = `${(duration / MAX_LOOP_SECONDS) * 100}%`;

      const part = new Tone.Part((time, ev) => {
        if (isDrumCtx(ev.ctx)) {
          triggerDrum(ev.slotId, time);
        } else {
          const notes = chordSeven(ev.slotId, ev.ctx);
          chordSynth.triggerAttackRelease(notes, ev.dur, time);
        }
      }, events.map(ev => ({ ...ev, time: ev.time - startTime })));

      part.loop = true;
      part.loopEnd = duration;
      part.mute = true;
      part.start(startTime);

      const track = { id, part, events, startTime, endTime, domElement };
      tracks.push(track);
      ui.trackLanes.appendChild(domElement);
      addInteractionToLoopBar(track);
    }

    function addInteractionToLoopBar(track) {
      const timelineWidth = () => ui.timeline.offsetWidth;
      const pxToTime = (px) => (px / timelineWidth()) * MAX_LOOP_SECONDS;

      const leftHandle = document.createElement('div');
      leftHandle.className = 'handle left';
      track.domElement.appendChild(leftHandle);

      const rightHandle = document.createElement('div');
      rightHandle.className = 'handle right';
      track.domElement.appendChild(rightHandle);

      const onDrag = (e, handleType) => {
        e.preventDefault();
        const startX = e.clientX;
        const initialStart = track.startTime;
        const initialEnd = track.endTime;

        const onMouseMove = (moveE) => {
          const dx = moveE.clientX - startX;
          const dt = pxToTime(dx);

          if (handleType === 'left') {
            const newStart = Math.max(0, initialStart + dt);
            const newEnd = initialEnd;
            if (newStart >= newEnd) return;
            track.startTime = newStart;
          } else { // right
            const newEnd = Math.min(MAX_LOOP_SECONDS, initialEnd + dt);
            const newStart = initialStart;
            if (newEnd <= newStart) return;
            track.endTime = newEnd;
          }
          updateTrack(track);
        };

        const onMouseUp = () => {
          window.removeEventListener('mousemove', onMouseMove);
          window.removeEventListener('mouseup', onMouseUp);
        };

        window.addEventListener('mousemove', onMouseMove);
        window.addEventListener('mouseup', onMouseUp);
      };

      leftHandle.addEventListener('mousedown', (e) => onDrag(e, 'left'));
      rightHandle.addEventListener('mousedown', (e) => onDrag(e, 'right'));
    }

    function updateTrack(track) {
      const newDuration = track.endTime - track.startTime;
      track.domElement.style.left = `${(track.startTime / MAX_LOOP_SECONDS) * 100}%`;
      track.domElement.style.width = `${(newDuration / MAX_LOOP_SECONDS) * 100}%`;

      track.part.dispose(); // Cleanly remove the old part

      // Create a new part with the updated settings
      const newPart = new Tone.Part((time, ev) => {
        if (isDrumCtx(ev.ctx)) {
          triggerDrum(ev.slotId, time);
        } else {
          const notes = chordSeven(ev.slotId, ev.ctx);
          chordSynth.triggerAttackRelease(notes, ev.dur, time);
        }
      }, track.events.map(ev => ({ ...ev, time: ev.time - track.startTime })));

      newPart.loop = true;
      newPart.loopEnd = newDuration;
      newPart.mute = true; // Start muted
      newPart.start(track.startTime);

      track.part = newPart; // Replace the old part with the new one
    }

    function transpose(semi){ state.key=wrap12(state.key+semi); updateStatus(); retargetHeld(); }
    function toggleQuality(){ state.quality=(state.quality==="Triad")?"Seventh":"Triad"; state.inversion=Math.min(state.inversion,(state.quality==="Seventh")?3:2); updateStatus(); retargetHeld(); }
    function cycleInv(){ const m=(state.quality==="Seventh")?3:2; state.inversion=(state.inversion+1)%(m+1); updateStatus(); retargetHeld(); }
    function toggleMode(){ state.mode=(state.mode==="Major")?"Minor":"Major"; updateStatus(); retargetHeld(); }
    function shiftOct(d){ state.baseOct=Math.max(1,Math.min(7,state.baseOct+d)); updateStatus(); retargetHeld(); }

    function toggleRec(){ if(!rec.active) startRec(); else stopRec(); }
    let spacePressed = false;
    window.addEventListener("keydown",(e)=>{ const k = e.key; if (e.code === "Space" || k === " " || k === "Spacebar") { e.preventDefault(); if (!spacePressed) spacePressed = true; return; } if (k.startsWith("Arrow")) e.preventDefault(); if(e.repeat) return; 
      const dir = ({ u:"NW",i:"N",o:"NE",j:"W",l:"E",m:"SW", ",":"S", ".":"SE", U:"NW",I:"N",O:"NE",J:"W",L:"E",M:"SW", "<":"S", ">":"SE" })[k]; if(dir){ applyPreset(dir); return; } const slotId = KEY_TO_SLOT[k]; if(slotId){ e.preventDefault(); pressSlot(slotId, k); return; } if(k==="ArrowLeft"){ transpose(e.shiftKey?-12:-1); } else if(k==="ArrowRight"){ transpose(e.shiftKey?+12:+1); } else if(k==="ArrowUp"){ cycleInv(); } else if(k==="ArrowDown"){ toggleQuality(); } else if(k==="m"||k==="M"){ toggleMode(); } else if(k===">"||k==="."){ shiftOct(+1); } else if(k===","||k==="<"){ shiftOct(-1); } });
    window.addEventListener("keyup",(e)=>{ const k = e.key; if (e.code === "Space" || k === " " || k === "Spacebar") { if (spacePressed) toggleRec(); spacePressed = false; e.preventDefault(); return; } 
      const slotId = KEY_TO_SLOT[k]; if(slotId) releaseKey(k); });
    window.addEventListener("blur",()=>{ for(const k of [...held.keys()]) releaseKey(k); spacePressed=false; });
  };

  initApp();
})();