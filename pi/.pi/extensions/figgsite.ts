/**
 * figgsite backend tools for pi.
 *
 * Gives the agent a safe, narrow window onto the mesh pipeline: it can push a
 * photo through, start the sculpt, and read back status/products. It cannot
 * touch the filesystem or shell for any of this — every tool is an HTTP call
 * to our own loopback API, and the bridge invokes pi with an explicit
 * `--tools` allowlist so bash/edit/write stay switched off for site visitors.
 */
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

const BASE = (process.env.FIGG_API_BASE ?? "http://127.0.0.1:8798").replace(/\/$/, "");
const TOKEN = process.env.FIGG_API_TOKEN ?? "";
const FIGG_TOKEN = process.env.FIGG_TOKEN ?? "";

function url(path: string): string {
	const sep = path.includes("?") ? "&" : "?";
	return `${BASE}${path}${TOKEN ? `${sep}token=${encodeURIComponent(TOKEN)}` : ""}`;
}

async function call(
	method: string,
	path: string,
	body?: unknown,
	form?: FormData,
): Promise<{ status: number; json: any }> {
	const headers: Record<string, string> = {};
	if (FIGG_TOKEN) headers["X-Session-Token"] = FIGG_TOKEN;
	let payload: BodyInit | undefined;
	if (form) {
		payload = form;
	} else if (body !== undefined) {
		headers["Content-Type"] = "application/json";
		payload = JSON.stringify(body);
	}
	const res = await fetch(url(path), { method, headers, body: payload });
	const text = await res.text();
	let json: any = {};
	try {
		json = text ? JSON.parse(text) : {};
	} catch {
		json = { raw: text.slice(0, 300) };
	}
	return { status: res.status, json };
}

const ok = (payload: unknown) => ({
	content: [{ type: "text" as const, text: JSON.stringify(payload, null, 1) }],
	details: payload,
});

const fail = (message: string, status = 0) => ({
	content: [{ type: "text" as const, text: `ERROR ${status}: ${message}` }],
	details: { error: message, status },
});

export default function (pi: ExtensionAPI) {
	pi.registerTool({
		name: "figg_pipeline_status",
		label: "Figg pipeline status",
		description:
			"Read the backend's current state: how many photos and meshes exist, " +
			"whether Meshy is live or stubbed, and the product catalogue.",
		promptSnippet: "figg_pipeline_status() — see uploads/meshes/products right now",
		parameters: Type.Object({}),
		execute: async () => {
			try {
				const { status, json } = await call("GET", "/health");
				return status === 200 ? ok(json) : fail(json.error ?? "health failed", status);
			} catch (e) {
				return fail(String(e));
			}
		},
	});

	pi.registerTool({
		name: "figg_upload_photo",
		label: "Upload a pet photo",
		description:
			"Upload one JPEG/PNG of a pet to the Figg backend. Returns the photo_id " +
			"needed to start a sculpt. Accepts an absolute path to a local image. " +
			"Max 10MB, at least 256px on the short side, 3 uploads per owner per day.",
		promptSnippet: "figg_upload_photo(path) → photo_id",
		parameters: Type.Object({
			path: Type.String({ description: "Absolute path to a JPEG or PNG image" }),
			owner: Type.Optional(Type.String({ description: "Who is uploading; groups the daily quota" })),
		}),
		execute: async (_id, params) => {
			try {
				// The only tool that touches the filesystem, so it gets a hard
				// sandbox: resolve symlinks and require the file to live inside
				// FIGG_UPLOAD_DIR. A site visitor must never be able to point the
				// agent at /etc/shadow.
				const fs = await import("node:fs/promises");
				const path = await import("node:path");
				const root = process.env.FIGG_UPLOAD_DIR ?? "";
				if (!root) return fail("FIGG_UPLOAD_DIR is not configured", 500);

				const resolved = path.resolve(params.path);
				const real = await fs.realpath(resolved).catch(() => resolved);
				const realRoot = await fs.realpath(root).catch(() => path.resolve(root));
				if (real !== realRoot && !real.startsWith(realRoot + path.sep)) {
					return fail(`path must be inside the upload directory (${realRoot})`, 403);
				}

				const bytes = await fs.readFile(real);
				const form = new FormData();
				form.append(
					"photo",
					new Blob([bytes], { type: "image/jpeg" }),
					real.split("/").pop() ?? "photo.jpg",
				);
				form.append("owner", params.owner ?? "agent");
				const { status, json } = await call("POST", "/api/photos", undefined, form);
				if (status !== 200 || !json.ok) return fail(json.error ?? "upload failed", status);
				return ok({
					photo_id: json.photo.id,
					reused: json.reused ?? false,
					size: `${json.photo.width}x${json.photo.height}`,
					stored_at: json.photo.r2_key,
				});
			} catch (e) {
				return fail(String(e));
			}
		},
	});

	pi.registerTool({
		name: "figg_start_mesh",
		label: "Start the sculpt",
		description:
			"Turn an uploaded photo into a 3D mesh. Returns a mesh_id immediately; " +
			"the job runs asynchronously. Re-sending an existing photo_id is safe and " +
			"returns the cached mesh instead of spending credits again.",
		promptSnippet: "figg_start_mesh(photo_id) → mesh_id",
		parameters: Type.Object({
			photo_id: Type.String({ description: "photo_id returned by figg_upload_photo" }),
		}),
		execute: async (_id, params) => {
			try {
				const { status, json } = await call("POST", "/api/meshes", {
					photo_id: params.photo_id,
				});
				if (status !== 200 || !json.ok) return fail(json.error ?? "start failed", status);
				return ok({
					mesh_id: json.mesh.id,
					status: json.mesh.status,
					cached: json.reused,
				});
			} catch (e) {
				return fail(String(e));
			}
		},
	});

	pi.registerTool({
		name: "figg_mesh_status",
		label: "Mesh status and products",
		description:
			"Check whether a sculpt finished, get its GLB url, and list every product " +
			"that mesh is now active in (figurine, bauble, video, card, sticker).",
		promptSnippet: "figg_mesh_status(mesh_id) → status + products",
		parameters: Type.Object({
			mesh_id: Type.String({ description: "mesh_id returned by figg_start_mesh" }),
		}),
		execute: async (_id, params) => {
			try {
				const { status, json } = await call("GET", `/api/meshes/${encodeURIComponent(params.mesh_id)}`);
				if (status !== 200 || !json.ok) return fail(json.error ?? "lookup failed", status);
				return ok({
					mesh_id: json.mesh.id,
					state: json.mesh.status,
					print_ready: !!json.mesh.print_ready,
					is_stub: !!json.mesh.stub,
					glb_url: json.mesh.glb_url,
					error: json.mesh.error || undefined,
					products: (json.products ?? []).map((p: any) => ({
						product: p.product,
						state: p.status,
						price: `$${(p.price_cents / 100).toFixed(2)}`,
					})),
				});
			} catch (e) {
				return fail(String(e));
			}
		},
	});

	pi.registerTool({
		name: "figg_products",
		label: "Products this mesh powers",
		description:
			"List the product bindings for a mesh only — the fan-out of what the " +
			"character is available as, and where each one is fulfilled from.",
		promptSnippet: "figg_products(mesh_id) → product list",
		parameters: Type.Object({
			mesh_id: Type.String({ description: "The mesh to inspect" }),
		}),
		execute: async (_id, params) => {
			try {
				const { status, json } = await call(
					"GET",
					`/api/meshes/${encodeURIComponent(params.mesh_id)}/products`,
				);
				if (status !== 200 || !json.ok) return fail(json.error ?? "lookup failed", status);
				return ok({
					mesh_id: json.mesh_id,
					source_glb: json.source_glb,
					products: json.products,
				});
			} catch (e) {
				return fail(String(e));
			}
		},
	});

	// ── studio (modular product lines + props + order) ────────────────
	pi.registerTool({
		name: "figg_studio_state",
		label: "Studio state",
		description:
			"Read the modular product studio: product lines (ornament/keychain/brick), " +
			"coat and hat props, the owner's meshes with GLB urls, and live prices.",
		promptSnippet: "figg_studio_state(owner?) → lines, props, meshes",
		parameters: Type.Object({
			owner: Type.Optional(Type.String({ description: "Owner handle; defaults to agent" })),
		}),
		execute: async (_id, params) => {
			try {
				const q = params.owner ? `?owner=${encodeURIComponent(params.owner)}` : "";
				const { status, json } = await call("GET", `/api/studio${q}`);
				return status === 200 && json.ok ? ok(json) : fail(json.error ?? "studio failed", status);
			} catch (e) {
				return fail(String(e));
			}
		},
	});

	pi.registerTool({
		name: "figg_studio_customise",
		label: "Customise studio preview",
		description:
			"Apply line/coat/hat to the product studio. Coat is a preview grade on " +
			"the existing mesh texture; hat is a modular prop. Returns still URLs + price.",
		promptSnippet: "figg_studio_customise({line,coat,hat}) → stills + price",
		parameters: Type.Object({
			line: Type.Optional(Type.String({ description: "ornament | keychain | brick" })),
			coat: Type.Optional(Type.String({ description: "none|cream|golden|chocolate|black|fawn|grey" })),
			hat: Type.Optional(Type.String({ description: "none|santa" })),
			owner: Type.Optional(Type.String()),
			mesh_id: Type.Optional(Type.String()),
		}),
		execute: async (_id, params) => {
			try {
				const { status, json } = await call("POST", "/api/studio/customise", {
					line: params.line ?? "ornament",
					coat: params.coat ?? "none",
					hat: params.hat ?? "none",
					owner: params.owner ?? "",
					mesh_id: params.mesh_id ?? "",
				});
				return status === 200 && json.ok ? ok(json) : fail(json.error ?? "customise failed", status);
			} catch (e) {
				return fail(String(e));
			}
		},
	});

	pi.registerTool({
		name: "figg_studio_order",
		label: "One-click studio order",
		description:
			"Reserve a studio order (line + coat + hat + qty). Returns order id and " +
			"price quote. Does NOT charge — checkout (Stripe/Shopify) is separate.",
		promptSnippet: "figg_studio_order({line,coat,hat,qty}) → order + quote",
		parameters: Type.Object({
			line: Type.String({ description: "ornament | keychain" }),
			coat: Type.Optional(Type.String()),
			hat: Type.Optional(Type.String()),
			qty: Type.Optional(Type.Number({ description: "1-20" })),
			owner: Type.Optional(Type.String()),
			mesh_id: Type.Optional(Type.String()),
			note: Type.Optional(Type.String()),
		}),
		execute: async (_id, params) => {
			try {
				const { status, json } = await call("POST", "/api/studio/order", {
					line: params.line,
					coat: params.coat ?? "none",
					hat: params.hat ?? "none",
					qty: params.qty ?? 1,
					owner: params.owner ?? "",
					mesh_id: params.mesh_id ?? "",
					note: params.note ?? "",
				});
				return status === 200 && json.ok ? ok(json) : fail(json.error ?? "order failed", status);
			} catch (e) {
				return fail(String(e));
			}
		},
	});

	// ── products storefront (per-line assets + checkout) ──────────────
	pi.registerTool({
		name: "figg_product_assets",
		label: "Product line assets",
		description:
			"List studio product lines with the props that make sense on each " +
			"(e.g. xmas ornament → santa hat + coats; keychain → coats only), " +
			"prices, stills and status.",
		promptSnippet: "figg_product_assets() → lines + assets + prices",
		parameters: Type.Object({
			owner: Type.Optional(Type.String()),
		}),
		execute: async (_id, params) => {
			try {
				const q = params.owner ? `?owner=${encodeURIComponent(params.owner)}` : "";
				const { status, json } = await call("GET", `/api/products/studio${q}`);
				return status === 200 && json.ok ? ok(json) : fail(json.error ?? "products failed", status);
			} catch (e) {
				return fail(String(e));
			}
		},
	});

	pi.registerTool({
		name: "figg_product_personalise",
		label: "Personalise a product",
		description:
			"Apply coat/hat (and optional texture note) to a product line for the " +
			"active mesh. Returns stills + price. Coat is preview grade; hat is a " +
			"modular Blender prop. Validate assets against figg_product_assets first.",
		promptSnippet: "figg_product_personalise({line,coat,hat}) → stills",
		parameters: Type.Object({
			line: Type.String({ description: "ornament | keychain" }),
			coat: Type.Optional(Type.String()),
			hat: Type.Optional(Type.String()),
			texture: Type.Optional(Type.String({ description: "Optional texture/decal note" })),
			owner: Type.Optional(Type.String()),
			mesh_id: Type.Optional(Type.String()),
		}),
		execute: async (_id, params) => {
			try {
				const { status, json } = await call("POST", "/api/products/personalise", {
					line: params.line,
					coat: params.coat ?? "none",
					hat: params.hat ?? "none",
					texture: params.texture ?? "",
					owner: params.owner ?? "",
					mesh_id: params.mesh_id ?? "",
				});
				return status === 200 && json.ok ? ok(json) : fail(json.error ?? "personalise failed", status);
			} catch (e) {
				return fail(String(e));
			}
		},
	});

	pi.registerTool({
		name: "figg_checkout",
		label: "Checkout a personalised product",
		description:
			"Reserve an order for a product line with coat/hat/qty. Returns order id " +
			"+ quote. Does NOT charge — Stripe/Shopify payment is separate. " +
			"Always show the customer the price before calling this.",
		promptSnippet: "figg_checkout({line,coat,hat,qty}) → order + quote",
		parameters: Type.Object({
			line: Type.String({ description: "ornament | keychain" }),
			coat: Type.Optional(Type.String()),
			hat: Type.Optional(Type.String()),
			qty: Type.Optional(Type.Number({ description: "1-20" })),
			owner: Type.Optional(Type.String()),
			mesh_id: Type.Optional(Type.String()),
			note: Type.Optional(Type.String()),
		}),
		execute: async (_id, params) => {
			try {
				const { status, json } = await call("POST", "/api/products/order", {
					line: params.line,
					coat: params.coat ?? "none",
					hat: params.hat ?? "none",
					qty: params.qty ?? 1,
					owner: params.owner ?? "",
					mesh_id: params.mesh_id ?? "",
					note: params.note ?? "",
				});
				return status === 200 && json.ok ? ok(json) : fail(json.error ?? "checkout failed", status);
			} catch (e) {
				return fail(String(e));
			}
		},
	});
}
