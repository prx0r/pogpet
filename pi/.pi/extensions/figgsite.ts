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
const ACTOR = process.env.FIGG_OWNER ?? "";
const OWNER_SIG = process.env.FIGG_OWNER_SIG ?? "";
const USER_KEY = process.env.FIGG_API_KEY ?? "";

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
	const claimed = (body && typeof body === "object" && "owner" in body)
		? String((body as {owner?: unknown}).owner ?? "")
		: form?.get("owner")?.toString() ?? new URL(path,BASE).searchParams.get("owner") ?? "";
	if (ACTOR && claimed && claimed !== ACTOR) throw new Error("This tool can only act for the current session owner.");
	if (USER_KEY) headers["X-API-Key"] = USER_KEY;
	if (OWNER_SIG) headers["X-Owner-Sig"] = OWNER_SIG;
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
				form.append("owner", params.owner || ACTOR || "agent");
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
				const owner = params.owner || ACTOR;
				const q = owner ? `?owner=${encodeURIComponent(owner)}` : "";
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
			hat: Type.Optional(Type.String({ description: "none|santa|xmas_hat" })),
			owner: Type.Optional(Type.String()),
			mesh_id: Type.Optional(Type.String()),
		}),
		execute: async (_id, params) => {
			try {
				const { status, json } = await call("POST", "/api/studio/customise", {
					line: params.line ?? "ornament",
					coat: params.coat ?? "none",
					hat: params.hat ?? "none",
					owner: params.owner || ACTOR || "",
					mesh_id: params.mesh_id ?? "",
				});
				return status === 200 && json.ok ? ok(json) : fail(json.error ?? "customise failed", status);
			} catch (e) {
				return fail(String(e));
			}
		},
	});

	pi.registerTool({
		name: "figg_studio_retexture",
		label: "Retexture preview (coat / santa / pattern)",
		description:
			"Controlled retexture on a studio line: coat colour, optional santa hat, " +
			"optional pattern. Returns still URLs, available registry ids and price. " +
			"0 Meshy credits. Registry ids only — coat is a preview grade, not a print SKU.",
		promptSnippet:
			"figg_studio_retexture({line:'ornament',coat:'chocolate',hat:'santa',pattern:'spots'})",
		parameters: Type.Object({
			line: Type.Optional(Type.String({ description: "ornament | keychain | brick" })),
			coat: Type.Optional(Type.String({ description: "none|cream|golden|chocolate|black|fawn|grey" })),
			hat: Type.Optional(Type.String({ description: "none|santa|xmas_hat" })),
			pattern: Type.Optional(Type.String({ description: "solid|spots|stripes|fairisle" })),
			owner: Type.Optional(Type.String()),
			mesh_id: Type.Optional(Type.String()),
			note: Type.Optional(Type.String({ description: "Optional free-text note stored on the preview" })),
		}),
		execute: async (_id, params) => {
			try {
				const { status, json } = await call("POST", "/api/products/personalise", {
					line: params.line ?? "ornament",
					coat: params.coat ?? "none",
					hat: params.hat ?? "none",
					pattern: params.pattern ?? "solid",
					owner: params.owner || ACTOR || "",
					mesh_id: params.mesh_id ?? "",
					texture: params.note ?? "",
					texture_note: params.note ?? "",
				});
				return status === 200 && json.ok ? ok(json) : fail(json.error ?? "retexture failed", status);
			} catch (e) {
				return fail(String(e));
			}
		},
	});

	pi.registerTool({
		name: "figg_studio_combos",
		label: "List coat / santa / pattern stills",
		description:
			"Catalogue of pre-rendered coat colours, santa hat stills, coat×hat combos " +
			"and pattern heroes, plus which assets each product line allows.",
		promptSnippet: "figg_studio_combos() → available coats, hats, combos, patterns",
		parameters: Type.Object({}),
		execute: async () => {
			try {
				const { status, json } = await call("GET", "/api/studio/combos");
				return status === 200 && json.ok ? ok(json) : fail(json.error ?? "combos failed", status);
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
					owner: params.owner || ACTOR || "",
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
				const owner = params.owner || ACTOR;
				const q = owner ? `?owner=${encodeURIComponent(owner)}` : "";
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
					owner: params.owner || ACTOR || "",
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
			"Reserve an order for a product line with coat/hat/pattern/qty. Returns order id " +
			"+ quote. Set fulfil=true to also create a Shopify draft order (no card charge). " +
			"Always show the customer the price before calling this. Controlled custom only.",
		promptSnippet: "figg_checkout({line,coat,hat,pattern,qty,fulfil?}) → order",
		parameters: Type.Object({
			line: Type.String({ description: "ornament | keychain | gift_card" }),
			coat: Type.Optional(Type.String()),
			hat: Type.Optional(Type.String()),
			pattern: Type.Optional(Type.String({ description: "solid|spots|stripes|fairisle" })),
			qty: Type.Optional(Type.Number({ description: "1-20" })),
			amount_cents: Type.Optional(Type.Number({ description: "gift_card: 1000|2500|5000" })),
			fulfil: Type.Optional(Type.Boolean({ description: "true = try Shopify draft order" })),
			email: Type.Optional(Type.String()),
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
					pattern: params.pattern ?? "solid",
					qty: params.qty ?? 1,
					amount_cents: params.amount_cents,
					fulfil: params.fulfil ?? false,
					email: params.email ?? "",
					owner: params.owner || ACTOR || "",
					mesh_id: params.mesh_id ?? "",
					note: params.note ?? "",
				});
				return status === 200 && json.ok ? ok(json) : fail(json.error ?? "checkout failed", status);
			} catch (e) {
				return fail(String(e));
			}
		},
	});

	// ── full agent chain: mesh manifest → props → personalise → order ──
	pi.registerTool({
		name: "figg_mesh_manifest",
		label: "Mesh machine-readable manifest",
		description:
			"Machine-readable view of a mesh for agents: status, GLB url, photo facts, " +
			"product bindings, studio lines, allowed hats/coats/patterns, custom policy. " +
			"Call this after upload/sculpt before personalising.",
		promptSnippet: "figg_mesh_manifest(mesh_id, owner?) → manifest",
		parameters: Type.Object({
			mesh_id: Type.String({ description: "mesh_id or 'canonical'" }),
			owner: Type.Optional(Type.String()),
		}),
		execute: async (_id, params) => {
			try {
				const owner = params.owner || ACTOR;
				const q = owner ? `?owner=${encodeURIComponent(owner)}` : "";
				const { status, json } = await call(
					"GET",
					`/api/meshes/${encodeURIComponent(params.mesh_id)}/manifest${q}`,
				);
				return status === 200 && json.ok ? ok(json) : fail(json.error ?? "manifest failed", status);
			} catch (e) {
				return fail(String(e));
			}
		},
	});

	pi.registerTool({
		name: "figg_studio_props",
		label: "Prop library (hats, coats, patterns)",
		description:
			"Machine-readable prop registry: hats (with asset paths + licences), coat " +
			"colours, retexture patterns, and per-line allowed combos. Controlled custom " +
			"only — never invent prop ids.",
		promptSnippet: "figg_studio_props() → hats, coats, patterns, lines",
		parameters: Type.Object({}),
		execute: async () => {
			try {
				const { status, json } = await call("GET", "/api/studio/props");
				return status === 200 && json.ok ? ok(json) : fail(json.error ?? "props failed", status);
			} catch (e) {
				return fail(String(e));
			}
		},
	});

	pi.registerTool({
		name: "figg_fullchain_personalise_order",
		label: "Personalise + order (controlled)",
		description:
			"Full product chain for one SKU: validate coat/pattern/hat against the line's " +
			"registry, return stills + price, then reserve an order. Optionally fulfil via " +
			"Shopify draft (fulfil=true). Use figg_upload_photo + figg_start_mesh + " +
			"figg_mesh_manifest first when starting from a customer photo.",
		promptSnippet: "figg_fullchain_personalise_order({line,coat,pattern,hat,qty})",
		parameters: Type.Object({
			line: Type.String({ description: "ornament | keychain | croc_tag | gift_card" }),
			coat: Type.Optional(Type.String()),
			pattern: Type.Optional(Type.String()),
			hat: Type.Optional(Type.String()),
			qty: Type.Optional(Type.Number()),
			amount_cents: Type.Optional(Type.Number()),
			fulfil: Type.Optional(Type.Boolean()),
			owner: Type.Optional(Type.String()),
			mesh_id: Type.Optional(Type.String()),
			email: Type.Optional(Type.String()),
		}),
		execute: async (_id, params) => {
			try {
				const owner = params.owner || ACTOR || "";
				const mesh = params.mesh_id ?? "";
				const pers = await call("POST", "/api/products/personalise", {
					line: params.line,
					coat: params.coat ?? "none",
					pattern: params.pattern ?? "solid",
					hat: params.hat ?? "none",
					owner,
					mesh_id: mesh,
				});
				if (pers.status !== 200 || !pers.json.ok) {
					return fail(pers.json.error ?? "personalise failed", pers.status);
				}
				const ord = await call("POST", "/api/products/order", {
					line: params.line,
					coat: params.coat ?? "none",
					pattern: params.pattern ?? "solid",
					hat: params.hat ?? "none",
					qty: params.qty ?? 1,
					amount_cents: params.amount_cents,
					fulfil: params.fulfil ?? false,
					email: params.email ?? "",
					owner,
					mesh_id: mesh,
				});
				if (ord.status !== 200 || !ord.json.ok) {
					return fail(ord.json.error ?? "order failed", ord.status);
				}
				return ok({
					personalise: pers.json,
					order: ord.json,
					price_cents: ord.json.price_cents,
					shopify: ord.json.shopify,
				});
			} catch (e) {
				return fail(String(e));
			}
		},
	});

	pi.registerTool({
		name: "figg_etsy_listing",
		label: "Etsy listing pack",
		description:
			"Machine-readable Etsy listing for a product: pipe-delimited title, tags, " +
			"sizes (mm), materials, processing days, photo slots. Use before writing " +
			"a marketplace listing or syncing Shopify tags.",
		promptSnippet: "figg_etsy_listing({product_id?}) → listing packs",
		parameters: Type.Object({
			product_id: Type.Optional(Type.String({
				description: "ornament | keychain | croc_tag | gift_card | xmas_card",
			})),
		}),
		execute: async (_id, params) => {
			try {
				const q = params.product_id
					? `?product_id=${encodeURIComponent(params.product_id)}`
					: "";
				const { status, json } = await call("GET", `/api/etsy/listings${q}`);
				return status === 200 && json.ok ? ok(json) : fail(json.error ?? "etsy failed", status);
			} catch (e) {
				return fail(String(e));
			}
		},
	});

	pi.registerTool({
		name: "figg_bricks_status",
		label: "Brick meshes status",
		description:
			"List installed meshes and any GLB files waiting in data/uploads/ for the " +
			"brick product line. Use when the owner says they've generated brick meshes.",
		promptSnippet: "figg_bricks_status({owner?}) → meshes + pending GLBs",
		parameters: Type.Object({
			owner: Type.Optional(Type.String()),
		}),
		execute: async (_id, params) => {
			try {
				const owner = params.owner || ACTOR;
				const q = owner ? `?owner=${encodeURIComponent(owner)}` : "";
				const { status, json } = await call("GET", `/api/bricks/status${q}`);
				return status === 200 && json.ok ? ok(json) : fail(json.error ?? "bricks failed", status);
			} catch (e) {
				return fail(String(e));
			}
		},
	});

	pi.registerTool({
		name: "figg_meshy_catalog",
		label: "Meshy Creative Lab catalogue",
		description:
			"Machine-readable Meshy product types (figure, brick, vinyl, lamp, keychain " +
			"medallion, fridge magnet, keycap, fidgets) with credit costs and how each " +
			"maps to OddHobb SKUs. Generation only — spending still requires human approval.",
		promptSnippet: "figg_meshy_catalog() → products + credits + ship note",
		parameters: Type.Object({}),
		execute: async () => {
			try {
				const { status, json } = await call("GET", "/api/meshy/catalog");
				return status === 200 && json.ok ? ok(json) : fail(json.error ?? "catalog failed", status);
			} catch (e) {
				return fail(String(e));
			}
		},
	});
	// Same owner-scoped card API as the browser and Python MCP server.
	const ownerField = Type.Optional(Type.String({description:"Current session owner; never another customer's handle"}));
	function cardTool(name: string, description: string, parameters: any,
		request: (args: any, owner: string) => Promise<{status: number; json: any}>) {
		pi.registerTool({name,label:name.replaceAll("_"," "),description,parameters,
			execute:async (_id, args) => {
				try {
					const owner=args.owner || ACTOR || "anon";
					const result=await request(args,owner);
					return result.status===200 && result.json.ok ? ok(result.json) : fail(result.json.error ?? "Card request failed",result.status);
				} catch(e) { return fail(String(e)); }
			}});
	}
	const query=(owner:string)=>"owner="+encodeURIComponent(owner);
	const id=(value:string)=>encodeURIComponent(value);
	cardTool("figg_card_library","List your uploaded photos, scene templates and saved greeting cards. No mesh is needed.",Type.Object({owner:ownerField}),async (_a,o)=>{
		const results=await Promise.all([call("GET","/api/cards/photos?"+query(o)),call("GET","/api/cards/templates?"+query(o)),call("GET","/api/cards/designs?"+query(o))]);
		const failed=results.find(r=>r.status!==200||!r.json.ok);
		return failed || {status:200,json:{ok:true,photos:results[0].json,scenes:results[1].json,designs:results[2].json}};
	});
	cardTool("figg_card_save","Save a card spec with template/format/photos/headline/recipient/sender/inside_message. Updates require expected_revision.",Type.Object({owner:ownerField,spec:Type.Any(),design_id:Type.Optional(Type.String()),expected_revision:Type.Optional(Type.Integer())}),async(a,o)=>call("POST","/api/cards/designs",{owner:o,spec:a.spec,...(a.design_id?{id:a.design_id,expected_revision:a.expected_revision}:{})}));
	cardTool("figg_card_scene","Read one shared card/video scene and its output status.",Type.Object({owner:ownerField,design_id:Type.String(),revision:Type.Optional(Type.Integer())}),async(a,o)=>call("GET","/api/cards/"+id(a.design_id)+"/scene?"+query(o)+(a.revision?"&revision="+a.revision:"")));
	cardTool("figg_card_render","Render preview, export PDF or motion MP4 from a saved revision; returns an asynchronous job.",Type.Object({owner:ownerField,design_id:Type.String(),revision:Type.Integer(),kind:Type.Union([Type.Literal("preview"),Type.Literal("export"),Type.Literal("motion")])}),async(a,o)=>call("POST","/api/cards/"+id(a.design_id)+"/render",{owner:o,revision:a.revision,kind:a.kind}));
	cardTool("figg_card_job","Check a card render job; ready outputs have private download URLs.",Type.Object({owner:ownerField,job_id:Type.String()}),async(a,o)=>call("GET","/api/cards/jobs/"+id(a.job_id)+"?"+query(o)));
	cardTool("figg_card_cutout","Remove a selected subject's background after an explicit crop. Uses the configured transformation service; no mesh generation.",Type.Object({owner:ownerField,photo_id:Type.String(),crop:Type.Array(Type.Number(),{minItems:4,maxItems:4})}),async(a,o)=>call("POST","/api/cards/cutouts",{owner:o,photo_id:a.photo_id,crop:a.crop}));
	cardTool("figg_card_reserve","Reserve a card with a ready PDF. Show the estimate first. No payment or supplier dispatch.",Type.Object({owner:ownerField,design_id:Type.String(),revision:Type.Integer(),idempotency_key:Type.String(),qty:Type.Optional(Type.Integer())}),async(a,o)=>call("POST","/api/cards/"+id(a.design_id)+"/order",{owner:o,revision:a.revision,idempotency_key:a.idempotency_key,qty:a.qty??1}));

	// ── 3D MODE: Blender review room (review.oddhobb.com) ──────────────
	// When the owner says 3D mode / review room / direct the puppet, switch
	// to these rules and reference the local Blender docs mirror plus the
	// repo scripts below. Gallery: https://review.oddhobb.com/
	// 3D viewer: https://review.oddhobb.com/three.html
	const DASH = (process.env.REVIEW_DASH_BASE ?? "http://127.0.0.1:8809").replace(/\/$/, "");
	const dashGet = async (p: string) => {
		const res = await fetch(DASH + p);
		const text = await res.text();
		try { return { status: res.status, json: JSON.parse(text) }; }
		catch { return { status: res.status, json: { raw: text.slice(0, 500) } }; }
	};
	const dashPost = async (p: string, body: unknown) => {
		const res = await fetch(DASH + p, { method: "POST",
			headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
		const text = await res.text();
		try { return { status: res.status, json: JSON.parse(text) }; }
		catch { return { status: res.status, json: { raw: text.slice(0, 500) } }; }
	};
	const MODE_3D = [
		"3D MODE rules (activate when owner says 3D mode / review room / direct the puppet):",
		"1. Reference the Blender docs mirror FIRST: /home/ubuntu/blender-docs/INDEX.md, then api/ (bpy.ops.import_scene, export_scene, mesh, object; bpy.types Mesh/Object/Modifier) and manual/ (modifiers, normals, glTF). Docs are Blender 4.2; box runs 5.0 — bpy.ops.wm.stl_export (not export_mesh.stl), BLENDER_EEVEE (not BLENDER_EEVEE_NEXT), layered Action channelbags (not action.fcurves).",
		"2. Repo scripts (all headless-safe, JSON reports): freaktown scripts/brick_qc.py (manifold/bounds/materials), repair_brick.py (weld, normals, fill, scale, STL), render_brick.py (turntable+hero), render_set.py (performance), puppet_qa.py (evidence bundle).",
		"3. QC gates before any print claim: nonmanifold==0 (or slicer-healable handful), bounds sane for the SKU, face visible from primary camera, holds still in pauses. Static meshes get whole-body acting, never faked mouths.",
		"4. Human verdicts live at the review dash gallery (/api/assets + reviews); read them before re-rendering. New outputs appear as /shots and /models entries.",
		"5. Meshy costs credits: quote + get explicit approval before any live generation call. Dry-run is the default.",
	].join("\n");
	pi.registerTool({
		name: "figg_3d_mode",
		label: "3D mode brief",
		description: "Activate 3D directing mode: Blender docs map, repo scripts, QC gates, review-dash wiring. Call this first when the owner says 3D mode.",
		promptSnippet: "figg_3d_mode() → 3D rules + Blender docs map + QC gates",
		parameters: Type.Object({}),
		execute: async () => ok({ mode: "3D", brief: MODE_3D }),
	});
	pi.registerTool({
		name: "figg_blender_docs",
		label: "Blender docs lookup",
		description: "Search the local Blender docs mirror (INDEX.md) and list repo Blender scripts. Use before writing any bpy code.",
		promptSnippet: "figg_blender_docs(query) → doc paths + script inventory",
		parameters: Type.Object({ query: Type.Optional(Type.String()) }),
		execute: async (_id, args) => {
			try {
				const q = args.query ? `?q=${encodeURIComponent(args.query)}` : "";
				const { status, json } = await dashGet(`/api/docs${q}`);
				return status === 200 ? ok(json) : fail(json.error ?? "docs failed", status);
			} catch (e) { return fail(String(e)); }
		},
	});
	pi.registerTool({
		name: "figg_blender_job",
		label: "Blender job submit",
		description: "Queue a headless Blender job on the review dash: brick_qc, brick_render, brick_repair. Returns job id; poll status.",
		promptSnippet: "figg_blender_job(kind, args) → job id (kinds: brick_qc, brick_render, brick_repair)",
		parameters: Type.Object({
			kind: Type.Union([Type.Literal("brick_qc"), Type.Literal("brick_render"), Type.Literal("brick_repair")]),
			args: Type.Any(),
		}),
		execute: async (_id, args) => {
			try {
				const { status, json } = await dashPost("/api/jobs", { kind: args.kind, args: args.args ?? {} });
				return status === 200 ? ok(json) : fail(json.error ?? "submit failed", status);
			} catch (e) { return fail(String(e)); }
		},
	});
	pi.registerTool({
		name: "figg_blender_job_status",
		label: "Blender job status",
		description: "Poll a queued Blender job; done jobs carry the log tail (QC-REPORT / RENDER DONE / REPAIR-REPORT).",
		promptSnippet: "figg_blender_job_status() → all jobs + statuses",
		parameters: Type.Object({}),
		execute: async () => {
			try {
				const { status, json } = await dashGet("/api/jobs");
				return status === 200 ? ok(json) : fail(json.error ?? "jobs failed", status);
			} catch (e) { return fail(String(e)); }
		},
	});
	pi.registerTool({
		name: "figg_review_verdicts",
		label: "Review verdicts",
		description: "Read the human's approve/redo verdicts and notes per asset from the review dash. Check before re-rendering anything.",
		promptSnippet: "figg_review_verdicts() → per-asset verdicts + notes",
		parameters: Type.Object({}),
		execute: async () => {
			try {
				const { status, json } = await dashGet("/api/assets");
				return status === 200 ? ok({ reviews: json.reviews, groups: Object.keys(json.groups || {}) }) : fail(json.error ?? "reviews failed", status);
			} catch (e) { return fail(String(e)); }
		},
	});

}
