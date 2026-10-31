// ============================================================================
//  Fixture 2030 — Hito 13 · carga de SOLO LECTURA observada con Prometheus.
//  Mismo partido caliente y misma cantidad de usuarios que el Hito 12
//  (fixture2030-hito12-carga/scripts/escenario_k6.js), pero solo GET: no
//  escribe en Cassandra (RNF5). La lanza scripts/ejecutar_carga_observada.sh.
// ============================================================================
import http from "k6/http";
import { check } from "k6";

const BASE = __ENV.BASE_URL || "http://host.docker.internal:8000";
const VUS = Number(__ENV.VUS || 20);
const RAMPA = Number(__ENV.RAMPA_S || 20);
const SOSTEN = Number(__ENV.SOSTEN_S || 90);
const PARTIDO = "PAR-D16-01";

export const options = {
  scenarios: {
    lectura_pico: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: `${RAMPA}s`, target: VUS },
        { duration: `${SOSTEN}s`, target: VUS },
        { duration: "5s", target: 0 },
      ],
      gracefulRampDown: "5s",
    },
  },
  summaryTrendStats: ["med", "p(95)", "p(99)", "max"],
};

export default function () {
  const r = http.get(`${BASE}/partidos/${PARTIDO}/comentarios?limit=50`, { timeout: "10s" });
  check(r, { "GET 200": (x) => x.status === 200 });
}
