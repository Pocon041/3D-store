// 简单的后端 API 包装
const BASE = "";

async function handle(resp) {
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`${resp.status} ${resp.statusText}: ${text}`);
  }
  return resp.json();
}

export async function health() {
  const resp = await fetch(`${BASE}/api/health`);
  return handle(resp);
}

export async function createReconstructJob({ files, mode, quality, exportGlb, mock }) {
  const fd = new FormData();
  files.forEach((f) => fd.append("files", f));
  fd.append("mode", mode);
  fd.append("quality", quality);
  fd.append("export_glb", String(exportGlb));
  fd.append("mock", String(mock));
  const resp = await fetch(`${BASE}/api/reconstruct`, { method: "POST", body: fd });
  return handle(resp);
}

export async function createTryOnJob({ personImage, garmentImage, category, mock }) {
  const fd = new FormData();
  fd.append("person_image", personImage);
  fd.append("garment_image", garmentImage);
  fd.append("category", category);
  fd.append("mock", String(mock));
  const resp = await fetch(`${BASE}/api/tryon`, { method: "POST", body: fd });
  return handle(resp);
}

export async function getTryOnCapabilities() {
  const resp = await fetch(`${BASE}/api/tryon/capabilities`);
  return handle(resp);
}

export async function getJob(jobId) {
  const resp = await fetch(`${BASE}/api/jobs/${jobId}`);
  return handle(resp);
}

export async function listJobs(limit = 20) {
  const resp = await fetch(`${BASE}/api/jobs?limit=${limit}`);
  return handle(resp);
}

export async function getJobFiles(jobId) {
  const resp = await fetch(`${BASE}/api/jobs/${jobId}/files`);
  return handle(resp);
}

export async function getMetrics(jobId) {
  const resp = await fetch(`${BASE}/api/metrics/${jobId}`);
  return handle(resp);
}

export async function listProducts(category, query) {
  const url = new URL("/api/products", window.location.origin);
  if (category && category !== "all") url.searchParams.set("category", category);
  if (query) url.searchParams.set("q", query);
  const resp = await fetch(url.toString().replace(window.location.origin, ""));
  return handle(resp);
}

export async function getImage3DProviders() {
  const resp = await fetch(`${BASE}/api/image-to-3d/providers`);
  return handle(resp);
}

export async function createImage3DJob({ image, provider }) {
  const fd = new FormData();
  fd.append("image", image);
  if (provider) fd.append("provider", provider);
  const resp = await fetch(`${BASE}/api/image-to-3d`, { method: "POST", body: fd });
  return handle(resp);
}

export async function createGlbImportJob({ model, thumbnail, name, price, stock, category, garmentSlot }) {
  const fd = new FormData();
  fd.append("model", model);
  if (thumbnail) fd.append("thumbnail", thumbnail);
  if (name) fd.append("name", name);
  if (price !== undefined && price !== null && price !== "") fd.append("price", String(price));
  if (stock !== undefined && stock !== null && stock !== "") fd.append("stock", String(stock));
  if (category) fd.append("category", category);
  if (garmentSlot) fd.append("garment_slot", garmentSlot);
  const resp = await fetch(`${BASE}/api/import-glb`, { method: "POST", body: fd });
  return handle(resp);
}

export async function createMultiView3DJob({ images, provider }) {
  const fd = new FormData();
  images.forEach((img) => fd.append("images", img));
  if (provider) fd.append("provider", provider);
  const resp = await fetch(`${BASE}/api/multiview-to-3d`, { method: "POST", body: fd });
  return handle(resp);
}

export async function getProduct(productId) {
  const resp = await fetch(`${BASE}/api/products/${encodeURIComponent(productId)}`);
  return handle(resp);
}

export async function deleteProduct(productId) {
  const resp = await fetch(`${BASE}/api/products/${encodeURIComponent(productId)}`, {
    method: "DELETE",
  });
  return handle(resp);
}

export async function publishJobAsProduct(jobId, payload) {
  const resp = await fetch(`${BASE}/api/products/publish/${encodeURIComponent(jobId)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });
  return handle(resp);
}
