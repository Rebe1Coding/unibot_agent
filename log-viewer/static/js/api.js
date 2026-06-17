export async function fetchContainers() {
  const res = await fetch("api/containers", { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  return data.containers || [];
}

export function buildStreamUrl(containers, tail) {
  const params = new URLSearchParams({
    containers: containers.join(","),
    tail: String(tail),
  });
  return `api/logs/stream?${params.toString()}`;
}
