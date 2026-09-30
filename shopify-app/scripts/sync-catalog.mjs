#!/usr/bin/env node
/**
 * OddHobb catalog -> Shopify product sync.
 *
 * Reads OUR canonical feed (public, no token) and upserts every product into
 * the Shopify store, so Shopify stays a mirror of the OddHobb registry —
 * exactly the "create product once" machine from docs/GTM-STRATEGY.md.
 *
 *   SHOPIFY_STORE=xxx.myshopify.com SHOPIFY_ADMIN_TOKEN=shpat_... \
 *     node ./scripts/sync-catalog.mjs [--dry-run] [--feed URL]
 *
 * Env:
 *   SHOPIFY_STORE        yourstore.myshopify.com (no https://)
 *   SHOPIFY_ADMIN_TOKEN  Admin API token with write_products + read_products
 *   FEED_URL             default https://oddhobb.com/backend/api/feeds/shopify.json
 *
 * Idempotent: matches existing products by handle; updates price/title/vendor
 * in place, adds the image only when the product has no media yet.
 * Images come from our public /img/ URLs (no token) — see backend/server.py
 * _public_product_image. EST prices are synced as-is; the storefront shows
 * the same EST figures, so feed and shelf never disagree.
 */
const FEED_URL =
  process.env.FEED_URL ??
  "https://oddhobb.com/backend/api/feeds/shopify.json";
const STORE = process.env.SHOPIFY_STORE ?? "";
const DRY = process.argv.includes("--dry-run");
const API_VERSION = "2024-10";

// Dev Dashboard apps don't expose a copyable shpat_ token in the UI — you
// exchange client_id + client_secret for a 24h access token (client_credentials
// grant). Accept either a live SHOPIFY_ACCESS_TOKEN or a manual
// SHOPIFY_ADMIN_TOKEN; refresh via credentials when possible.
const CLIENT_ID = process.env.SHOPIFY_API_KEY ?? "";
const CLIENT_SECRET = process.env.SHOPIFY_API_SECRET ?? "";
let TOKEN = process.env.SHOPIFY_ACCESS_TOKEN || process.env.SHOPIFY_ADMIN_TOKEN || "";

if (!STORE) {
  console.error("Missing SHOPIFY_STORE=xxx.myshopify.com");
  process.exit(2);
}
if (!TOKEN && !(CLIENT_ID && CLIENT_SECRET)) {
  console.error(
    "Need SHOPIFY_ACCESS_TOKEN (shpat_...) or SHOPIFY_API_KEY + SHOPIFY_API_SECRET "
    + "to mint one via client_credentials. Store: Settings > Apps > Develop apps."
  );
  process.exit(2);
}

async function refreshToken() {
  if (!(CLIENT_ID && CLIENT_SECRET)) return TOKEN;
  const res = await fetch(`https://${STORE}/admin/oauth/access_token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "client_credentials",
      client_id: CLIENT_ID,
      client_secret: CLIENT_SECRET,
    }),
  });
  const json = await res.json();
  if (!json.access_token) throw new Error("token exchange failed: " + JSON.stringify(json).slice(0, 200));
  TOKEN = json.access_token;
  return TOKEN;
}

async function gql(query, variables = {}) {
  if (!TOKEN) await refreshToken();
  const res = await fetch(
    `https://${STORE}/admin/api/${API_VERSION}/graphql.json`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": TOKEN,
      },
      body: JSON.stringify({ query, variables }),
    }
  );
  if (res.status === 401 && CLIENT_ID && CLIENT_SECRET) {
    await refreshToken();
    const res2 = await fetch(
      `https://${STORE}/admin/api/${API_VERSION}/graphql.json`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Shopify-Access-Token": TOKEN,
        },
        body: JSON.stringify({ query, variables }),
      }
    );
    const json2 = await res2.json();
    if (json2.errors?.length) throw new Error("GraphQL: " + JSON.stringify(json2.errors).slice(0, 300));
    return json2.data;
  }
  const json = await res.json();
  if (json.errors?.length) throw new Error("GraphQL: " + JSON.stringify(json.errors).slice(0, 300));
  return json.data;
}

const FIND_BY_HANDLE = `
  query($q: String!) { products(first: 1, query: $q) {
    edges { node { id title variants(first: 1) { edges { node { id price } } }
      media(first: 1) { edges { node { id } } } } } } }`;
const CREATE = `
  mutation($input: ProductInput!, $media: [CreateMediaInput!]) {
    productCreate(input: $input, media: $media) {
      product { id handle variants(first: 1) { edges { node { id } } } }
      userErrors { field message } } }`;
const UPDATE = `
  mutation($input: ProductInput!) {
    productUpdate(input: $input) { product { id } userErrors { field message } } }`;
const VARIANT_PRICE = `
  mutation($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
    productVariantsBulkUpdate(productId: $productId, variants: $variants) {
      userErrors { field message } } }`;
const ADD_MEDIA = `
  mutation($productId: ID!, $media: [CreateMediaInput!]!) {
    productCreateMedia(productId: $productId, media: $media) {
      media { alt } mediaUserErrors { field message } } }`;

function fail(errors, what) {
  const bad = (errors ?? []).filter((e) => e.message);
  if (bad.length) throw new Error(`${what}: ${bad.map((e) => e.message).join("; ").slice(0, 200)}`);
}

const feed = await (await fetch(FEED_URL)).json();
const products = feed.products ?? [];
console.log(`feed: ${products.length} products <- ${FEED_URL}${DRY ? " (DRY RUN)" : ""}`);

// Fail fast on bad credentials before touching any products.
try {
  const shop = await gql(`{ shop { name } }`);
  console.log(`store: ${shop.shop.name}`);
} catch (e) {
  console.error(`Cannot reach the Shopify Admin API at ${STORE}: ${e.message}`);
  console.error("Check SHOPIFY_STORE (xxx.myshopify.com) and SHOPIFY_ADMIN_TOKEN " +
    "(Store settings > Apps > Develop apps; scopes write_products + read_products).");
  process.exit(3);
}

let created = 0, updated = 0;
for (const p of products) {
  const handle = p.handle;
  const found = await gql(FIND_BY_HANDLE, { q: `handle:${handle}` });
  const node = found.products.edges[0]?.node ?? null;
  const price = p.variants?.[0]?.price ?? "0.00";
  const imageSrc = p.images?.[0]?.src ?? null;

  if (DRY) {
    console.log(`${node ? "UPDATE" : "CREATE"} ${handle} — ${p.title} £${price}${imageSrc && !node?.media?.edges?.length ? " +img" : ""}`);
    continue;
  }

  if (!node) {
    const media = imageSrc
      ? [{ originalSource: imageSrc, mediaContentType: "IMAGE" }]
      : [];
    const r = await gql(CREATE, {
      input: {
        title: p.title, descriptionHtml: p.body_html, vendor: p.vendor,
        productType: p.product_type, tags: p.tags, status: "ACTIVE",
      },
      media,
    });
    fail(r.productCreate.userErrors, `create ${handle}`);
    const newId = r.productCreate.product.id;
    const newVariant = r.productCreate.product.variants?.edges?.[0]?.node?.id ?? null;
    if (newVariant) {
      const v = await gql(VARIANT_PRICE, {
        productId: newId,
        variants: [{ id: newVariant, price }],
      });
      fail(v.productVariantsBulkUpdate.userErrors, `price ${handle}`);
    }
    created++;
    console.log(`CREATE ${handle} (£${price})`);
    continue;
  }

  const r = await gql(UPDATE, {
    input: {
      id: node.id, title: p.title, descriptionHtml: p.body_html,
      vendor: p.vendor, productType: p.product_type, tags: p.tags,
    },
  });
  fail(r.productUpdate.userErrors, `update ${handle}`);
  // bulk price update needs the existing variant id, not just the price
  const variantId = node.variants?.edges?.[0]?.node?.id ?? null;
  if (variantId) {
    const v = await gql(VARIANT_PRICE, {
      productId: node.id,
      variants: [{ id: variantId, price }],
    });
    fail(v.productVariantsBulkUpdate.userErrors, `price ${handle}`);
  }
  if (imageSrc && !node.media.edges.length) {
    const m = await gql(ADD_MEDIA, {
      productId: node.id,
      media: [{ originalSource: imageSrc, mediaContentType: "IMAGE" }],
    });
    fail(m.productCreateMedia.mediaUserErrors, `image ${handle}`);
  }
  updated++;
  console.log(`UPDATE ${handle} (£${price})`);
}
console.log(`done: ${created} created, ${updated} updated, ${products.length} total`);
