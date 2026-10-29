// ============================================================================
//  Fixture 2030 — Hito 12 · Escenario de carga (k6)
//  ARCHIVO: scripts/escenario_k6.js
//
//  FLUJO: pico de comentarios posterior a un gol en PAR-D16-01 (ARG–BEL, el
//  partido de audiencia MÁXIMA de los Hitos 6 y 8), a través de la API del
//  Hito 10 hacia Cassandra (Hito 6).
//    · 80 % lecturas: GET  /partidos/PAR-D16-01/comentarios?limit=50
//    · 20 % escrituras: POST /partidos/PAR-D16-01/comentarios (Idempotency-Key única)
//
//  FASES (RF2): rampa 0→VUS en RAMPA_S · sostenimiento SOSTEN_S · bajada 10 s.
//  CORTE SEGURO (RNF9): k6 aborta si los errores superan el 20 % durante 20 s.
//
//  IDENTIDAD DE LA PRUEBA (RNF7): cada corrida usa usuarios propios
//  USR-LT<CORRIDA><VU> (nunca usuarios reales USR-0000xxx), así la validación
//  y la limpieza tocan SOLO lo escrito por la prueba.
//
//  Variables (las pasa scripts/ejecutar_carga.sh): BASE_URL, CORRIDA, VUS,
//  RAMPA_S, SOSTEN_S, SALIDA.
// ============================================================================
import http from "k6/http";
import { check } from "k6";
import { Counter, Trend } from "k6/metrics";
import exec from "k6/execution";

const BASE = __ENV.BASE_URL || "http://host.docker.internal:8000";
const CORRIDA = (__ENV.CORRIDA || "0000").toUpperCase();
const VUS = Number(__ENV.VUS || 20);
const RAMPA = Number(__ENV.RAMPA_S || 30);
const SOSTEN = Number(__ENV.SOSTEN_S || 120);
const PARTIDO = "PAR-D16-01";
const PICO = Date.UTC(2030, 5, 29, 17, 30, 0); // ventana pico del partido (Hito 6: 16.161 filas por bucket)

export const options = {
  scenarios: {
    pico_post_gol: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: `${RAMPA}s`, target: VUS },   // rampa
        { duration: `${SOSTEN}s`, target: VUS },  // sostenimiento
        { duration: "10s", target: 0 },           // bajada
      ],
      gracefulRampDown: "5s",
    },
  },
  thresholds: {
    // Corte seguro: si fallan más del 20 % de las requests durante 20 s, se aborta.
    http_req_failed: [{ threshold: "rate<0.20", abortOnFail: true, delayAbortEval: "20s" }],
  },
  summaryTrendStats: ["min", "avg", "med", "p(90)", "p(95)", "p(99)", "max"],
  discardResponseBodies: false,
};

const latGet = new Trend("lat_get_comentarios", true);
const latPost = new Trend("lat_post_comentario", true);
const posts201 = new Counter("posts_201_creados");
const posts200 = new Counter("posts_200_reintento");
const postsError = new Counter("posts_error");
const getsError = new Counter("gets_error");

export default function () {
  const vu = exec.vu.idInTest;
  const it = exec.vu.iterationInScenario;
  if (Math.random() < 0.8) {
    const r = http.get(`${BASE}/partidos/${PARTIDO}/comentarios?limit=50`, { tags: { op: "GET" }, timeout: "10s" });
    latGet.add(r.timings.duration);
    const ok = check(r, {
      "GET 200": (x) => x.status === 200,
      "GET trae comentarios": (x) => x.status === 200 && (x.json("items") || []).length > 0,
    });
    if (!ok) getsError.add(1);
  } else {
    const usuario = `USR-LT${CORRIDA}${String(vu).padStart(3, "0")}`;
    const clave = `h12-${CORRIDA}-${vu}-${it}`;
    // creadoEn único por (vu, iteración) dentro de la ventana pico: 17:30:00 + vu s + it ms
    const creado = new Date(PICO + vu * 1000 + (it % 59000)).toISOString();
    const cuerpo = JSON.stringify({
      usuarioId: usuario, alias: `carga${vu}`, contenido: `prueba de carga ${clave}`,
      creadoEn: creado, minutoPartido: 90, hinchada: "NEUTRAL", idioma: "es",
    });
    const r = http.post(`${BASE}/partidos/${PARTIDO}/comentarios`, cuerpo, {
      headers: { "Content-Type": "application/json", "Idempotency-Key": clave },
      tags: { op: "POST" }, timeout: "10s",
    });
    latPost.add(r.timings.duration);
    if (r.status === 201) posts201.add(1);
    else if (r.status === 200) posts200.add(1);
    else postsError.add(1);
    check(r, { "POST 201": (x) => x.status === 201 });
  }
}

// Resumen en JSON para la comparación (scripts/comparar.py) y la validación de integridad.
export function handleSummary(data) {
  const salida = __ENV.SALIDA || "/resultados";
  return {
    [`${salida}/k6_resumen.json`]: JSON.stringify(data, null, 2),
    stdout: "\n" + resumenTexto(data) + "\n",
  };
}

function resumenTexto(d) {
  const m = d.metrics;
  const v = (k, s) => (m[k] && m[k].values[s] !== undefined ? m[k].values[s] : 0);
  const f = (x) => (typeof x === "number" ? x.toFixed(1) : x);
  return [
    `Requests: ${v("http_reqs", "count")} · ${f(v("http_reqs", "rate"))} req/s · fallidas: ${(100 * v("http_req_failed", "rate")).toFixed(2)} %`,
    `GET  ms: p50 ${f(v("lat_get_comentarios", "med"))} · p95 ${f(v("lat_get_comentarios", "p(95)"))} · p99 ${f(v("lat_get_comentarios", "p(99)"))}`,
    `POST ms: p50 ${f(v("lat_post_comentario", "med"))} · p95 ${f(v("lat_post_comentario", "p(95)"))} · p99 ${f(v("lat_post_comentario", "p(99)"))}`,
    `POST 201: ${v("posts_201_creados", "count")} · 200 reintento: ${v("posts_200_reintento", "count")} · error: ${v("posts_error", "count")}`,
  ].join("\n");
}
