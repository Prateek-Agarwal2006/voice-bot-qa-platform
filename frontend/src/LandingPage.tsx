import Globe from "react-globe.gl";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

const SRC_LAT = 40.7, SRC_LNG = -74.0;

const ARCS = [
  { startLat: SRC_LAT, startLng: SRC_LNG, endLat:  37.7, endLng: -122.4 },
  { startLat: SRC_LAT, startLng: SRC_LNG, endLat:  51.5, endLng:   -0.1 },
  { startLat: SRC_LAT, startLng: SRC_LNG, endLat:  50.1, endLng:    8.7 },
  { startLat: SRC_LAT, startLng: SRC_LNG, endLat:  35.7, endLng:  139.7 },
  { startLat: SRC_LAT, startLng: SRC_LNG, endLat:   1.3, endLng:  103.8 },
  { startLat: SRC_LAT, startLng: SRC_LNG, endLat:  19.1, endLng:   72.9 },
  { startLat: SRC_LAT, startLng: SRC_LNG, endLat: -23.5, endLng:  -46.6 },
  { startLat: SRC_LAT, startLng: SRC_LNG, endLat: -33.9, endLng:  151.2 },
];

const POINTS = [
  { lat: SRC_LAT, lng: SRC_LNG,  size: 0.6 },
  { lat:  37.7,   lng: -122.4,   size: 0.4 },
  { lat:  51.5,   lng:   -0.1,   size: 0.4 },
  { lat:  50.1,   lng:    8.7,   size: 0.4 },
  { lat:  35.7,   lng:  139.7,   size: 0.4 },
  { lat:   1.3,   lng:  103.8,   size: 0.4 },
  { lat:  19.1,   lng:   72.9,   size: 0.4 },
  { lat: -23.5,   lng:  -46.6,   size: 0.4 },
  { lat: -33.9,   lng:  151.2,   size: 0.4 },
];

const SIZE = 600;
const POINT_COLOR  = () => "#38bdf8";
const POINT_RADIUS = (d: { size?: number }) => d.size ?? 0.4;
const ARC_COLOR    = () => "#38bdf8";

export function LandingPage() {
  const navigate = useNavigate();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const globeRef = useRef<any>(null);
  const [phase,      setPhase]      = useState<0 | 1 | 2>(0);
  const [exiting,    setExiting]    = useState(false);
  const [globeReady, setGlobeReady] = useState(false);

  useEffect(() => {
    const t1 = setTimeout(() => setPhase(1), 2000);
    const t2 = setTimeout(() => setPhase(2), 3350);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, []);

  function onGlobeReady() {
    if (!globeRef.current) return;
    globeRef.current.controls().autoRotate      = true;
    globeRef.current.controls().autoRotateSpeed = 0.7;
    globeRef.current.pointOfView({ lat: 20, lng: -30, altitude: 2.0 }, 0);
    setGlobeReady(true);
  }

  function handleEnter(path: "/latency" | "/evaluations") {
    setExiting(true);
    setTimeout(() => navigate(path), 700);
  }

  return (
    <div style={{
      position: "fixed", inset: 0, background: "#000", overflow: "hidden",
      fontFamily: "system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif",
      opacity: exiting ? 0 : 1, transition: "opacity 0.7s ease",
    }}>

      {/* Globe */}
      <div style={{
        position: "absolute", top: "50%", left: "50%",
        width: `${SIZE}px`, height: `${SIZE}px`,
        marginTop: `-${SIZE / 2}px`, marginLeft: `-${SIZE / 2}px`,
        transition: "transform 1.3s cubic-bezier(0.4,0,0.2,1), opacity 0.4s ease",
        transform: phase >= 1 ? "translateX(30vw) scale(0.82)" : "translateX(0) scale(1)",
        opacity: globeReady ? 1 : 0,
        pointerEvents: "none",
        willChange: "transform",
      }}>
        <Globe
          ref={globeRef}
          width={SIZE}
          height={SIZE}
          animateIn={false}
          onGlobeReady={onGlobeReady}
          rendererConfig={{ antialias: false, alpha: true, preserveDrawingBuffer: true }}
          backgroundColor="rgba(0,0,0,0)"
          globeImageUrl="/earth-night.jpg"
          showAtmosphere={true}
          atmosphereColor="#38bdf8"
          atmosphereAltitude={0.18}
          pointsData={POINTS}
          pointColor={POINT_COLOR}
          pointRadius={POINT_RADIUS}
          pointAltitude={0.01}
          arcsData={ARCS}
          arcColor={ARC_COLOR}
          arcAltitude={0.5}
          arcDashLength={0.35}
          arcDashGap={0.65}
          arcDashAnimateTime={2800}
          arcStroke={0.6}
        />
      </div>

      {/* Text – flies in from left */}
      <div style={{
        position: "absolute", left: "10%", top: "50%", width: "38%",
        transform: phase >= 1 ? "translateY(-50%) translateX(0)" : "translateY(-50%) translateX(-72px)",
        opacity: phase >= 1 ? 1 : 0,
        transition: "opacity 0.95s ease 0.1s, transform 0.95s cubic-bezier(0.4,0,0.2,1) 0.1s",
      }}>

        <div style={{ fontSize: 11, letterSpacing: "0.28em", color: "#38bdf8", fontWeight: 600, textTransform: "uppercase", marginBottom: 22 }}>
          Voice Bot QA Platform
        </div>

        <div style={{ lineHeight: 0.97, marginBottom: 22, letterSpacing: "-0.03em" }}>
          <div style={{ fontSize: "clamp(44px,5.6vw,80px)", fontWeight: 800, whiteSpace: "nowrap", background: "linear-gradient(120deg,#ffffff 0%,#bfdbfe 100%)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent", backgroundClip: "text" }}>
            VoiceBot
          </div>
          <div style={{ fontSize: "clamp(44px,5.6vw,80px)", fontWeight: 800, whiteSpace: "nowrap", background: "linear-gradient(120deg,#38bdf8 0%,#a855f7 100%)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent", backgroundClip: "text" }}>
            QA Platform
          </div>
        </div>

        <div style={{ fontSize: 17, color: "#94a3b8", fontWeight: 400, letterSpacing: "0.01em", marginBottom: 48 }}>
          Measure speed. Score quality.
        </div>

        <div style={{
          display: "flex", gap: "14px", alignItems: "center",
          opacity: phase >= 2 ? 1 : 0,
          transform: phase >= 2 ? "translateY(0)" : "translateY(18px)",
          transition: "opacity 0.75s ease, transform 0.75s cubic-bezier(0.4,0,0.2,1)",
        }}>
          <button
            onClick={() => handleEnter("/latency")}
            style={{ padding: "13px 26px", border: "1.5px solid rgba(56,189,248,0.35)", background: "transparent", color: "#38bdf8", borderRadius: 9, fontSize: 14, fontWeight: 500, cursor: "pointer", fontFamily: "inherit", letterSpacing: "0.01em" }}
          >
            Latency Dashboard →
          </button>
          <button
            onClick={() => handleEnter("/evaluations")}
            style={{ padding: "13px 26px", border: "none", background: "linear-gradient(135deg,#38bdf8 0%,#6366f1 100%)", color: "#fff", borderRadius: 9, fontSize: 14, fontWeight: 600, cursor: "pointer", fontFamily: "inherit", letterSpacing: "0.01em" }}
          >
            Voice Bot Evaluation →
          </button>
        </div>
      </div>

    </div>
  );
}
