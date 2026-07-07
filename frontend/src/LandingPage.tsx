import createGlobe from "cobe";
import { useEffect, useRef, useState } from "react";

type TabTarget = "latency" | "evaluations";

interface Props {
  onEnter: (tab: TabTarget) => void;
}

const MARKERS: { location: [number, number]; size: number }[] = [
  { location: [38.9,  -77.0 ], size: 0.10 }, // US East (source)
  { location: [45.5,  -122.7], size: 0.05 }, // US West
  { location: [53.3,  -6.3  ], size: 0.07 }, // EU West
  { location: [50.1,   8.7  ], size: 0.06 }, // EU Central
  { location: [35.7,  139.7 ], size: 0.07 }, // Tokyo
  { location: [1.3,   103.8 ], size: 0.06 }, // Singapore
  { location: [19.1,  72.9  ], size: 0.06 }, // Mumbai
  { location: [-23.5, -46.6 ], size: 0.06 }, // Sao Paulo
  { location: [-33.9, 151.2 ], size: 0.06 }, // Sydney
];

const SIZE_BIG   = 620; // phase 0 display px
const SIZE_SMALL = 480; // phase 1 display px

export function LandingPage({ onEnter }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const phiRef    = useRef(0.5);
  const [phase,   setPhase]   = useState<0 | 1 | 2>(0);
  const [exiting, setExiting] = useState(false);

  useEffect(() => {
    const t1 = setTimeout(() => setPhase(1), 2000);
    const t2 = setTimeout(() => setPhase(2), 3600);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    // Grab the original parent BEFORE cobe moves the canvas into its own wrapper div.
    // cobe does: parent.insertBefore(wrapperDiv, canvas); wrapperDiv.append(canvas)
    // We need to undo this in cleanup so StrictMode double-mount doesn't stack wrappers.
    const originalParent = canvas.parentElement!;

    const DPR = Math.min(window.devicePixelRatio ?? 1, 2);

    const globe = createGlobe(canvas, {
      devicePixelRatio: DPR,
      width:  SIZE_BIG,
      height: SIZE_BIG,
      phi:    0.5,
      theta:  0.3,
      dark:         0,     // fully lit so sphere is visible against black bg
      diffuse:      1.8,
      mapSamples:   16000,
      mapBrightness: 10,
      baseColor:   [0.08, 0.22, 0.50],  // deep ocean blue
      markerColor: [0.22, 0.85, 1.0 ],
      glowColor:   [0.20, 0.55, 1.0 ],
      markers: MARKERS,
    });

    let rafId: number;
    const spin = () => {
      phiRef.current += 0.003;
      globe.update({ phi: phiRef.current });
      rafId = requestAnimationFrame(spin);
    };
    rafId = requestAnimationFrame(spin);

    return () => {
      cancelAnimationFrame(rafId);
      globe.destroy();
      // Remove cobe's wrapper div and restore canvas to its original parent
      // so StrictMode's second mount starts with a clean DOM.
      const cobeWrapper = canvas.parentElement;
      if (cobeWrapper && cobeWrapper !== originalParent) {
        originalParent.appendChild(canvas);
        cobeWrapper.remove();
      }
    };
  }, []);

  function handleEnter(tab: TabTarget) {
    setExiting(true);
    setTimeout(() => onEnter(tab), 550);
  }

  const displaySize = phase >= 1 ? SIZE_SMALL : SIZE_BIG;
  const canvasStyle: React.CSSProperties = {
    width:      displaySize,
    height:     displaySize,
    maxWidth:   "100%",
    aspectRatio: "1",
    transition: "width 0.85s cubic-bezier(0.4,0,0.2,1), height 0.85s cubic-bezier(0.4,0,0.2,1)",
  };

  return (
    <div className={`landing-root${exiting ? " landing-exit" : ""}`}>
      <div className={`landing-layout${phase >= 1 ? " landing-layout-split" : ""}`}>

        {/* ── Text LEFT ─────────────────────────────────────────────────── */}
        <div className={`landing-content${phase >= 1 ? " landing-content-in" : ""}`}>
          <p className="landing-label">Voice Bot QA Platform</p>
          <h1 className="landing-title">
            <span className="landing-word-a">VoiceBot</span>
            <span className="landing-word-b">QA Platform</span>
          </h1>
          <p className="landing-sub">Measure speed. Score quality.</p>

          <div className={`landing-nav${phase >= 2 ? " landing-nav-in" : ""}`}>
            <button className="landing-btn" onClick={() => handleEnter("latency")}>
              Latency Dashboard →
            </button>
            <button className="landing-btn landing-btn-primary" onClick={() => handleEnter("evaluations")}>
              Evaluations →
            </button>
          </div>
        </div>

        {/* ── Globe RIGHT ───────────────────────────────────────────────── */}
        <div className="landing-globe-wrap">
          <canvas ref={canvasRef} style={canvasStyle} />
        </div>

      </div>
    </div>
  );
}
