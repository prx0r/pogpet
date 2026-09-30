/**
 * MythicBee — Prodigi Integration v2
 * Print-on-demand fulfilment via Prodigi API v4.0
 * Uses X-API-Key header (not Bearer)
 */

class ProdigiIntegration {
  constructor() {
    // Prodigi API config — use live for real orders, sandbox for testing
    this.baseUrl = "https://api.prodigi.com/v4.0";
    this.apiKey = null;
  }

  init(apiKey) {
    this.apiKey = apiKey;
  }

  /**
   * Create a print order from ExperienceManifest
   */
  async createOrder(manifest, brief, printAssetUrl) {
    if (!this.apiKey) {
      console.error("Prodigi API key not set");
      return null;
    }

    // Map manifest vessel to Prodigi SKU
    const skuMap = {
      "classic-card": "GLOBAL-FC-8X6",
      "poster": "GLOBAL-FAP-16x24",
      "poster-a4": "GLOBAL-FAP-16x24",
      "mug": "GLOBAL-MUG-11OZ",
      "acrylic": "GLOBAL-ACRYLIC-76",
      "book": "GLOBAL-PB-8X8"
    };

    const sku = skuMap[manifest.physical?.vessel] || "GLOBAL-FAP-16x24";

    const order = {
      merchantReference: manifest.portalId || `mb_${Date.now()}`,
      shippingMethod: "Standard",
      recipient: {
        name: brief.recipient || "Test",
        address: {
          line1: brief.shippingAddress?.line1 || "123 Test Street",
          postalOrZipCode: brief.shippingAddress?.postalCode || "SW1A 1AA",
          countryCode: brief.shippingAddress?.country || "GB",
          townOrCity: brief.shippingAddress?.city || "London",
          stateOrCounty: brief.shippingAddress?.county || "London"
        }
      },
      items: [
        {
          merchantReference: `${manifest.portalId}-item-1`,
          sku: sku,
          copies: 1,
          sizing: "fillPrintArea",
          assets: [
            {
              printArea: "default",
              url: printAssetUrl || "https://pwintyimages.blob.core.windows.net/samples/stars/test-sample-grey.png"
            }
          ],
          recipientCost: {
            amount: String(manifest.pricing?.retail || "19.99"),
            currency: "GBP"
          }
        }
      ],
      metadata: {
        portalId: manifest.portalId,
        experienceType: manifest.engine,
        recipientName: brief.recipient
      }
    };

    try {
      const response = await fetch(`${this.baseUrl}/orders`, {
        method: "POST",
        headers: {
          "X-API-Key": this.apiKey,
          "Content-Type": "application/json"
        },
        body: JSON.stringify(order)
      });

      const result = await response.json();
      
      if (result.outcome === "Created" || result.outcome === "OnHold") {
        console.log("Prodigi order created:", result.order?.id);
        return result.order;
      } else {
        console.error("Prodigi order failed:", result);
        return null;
      }
    } catch (err) {
      console.error("Prodigi API error:", err);
      return null;
    }
  }

  /**
   * Get order status
   */
  async getOrder(orderId) {
    if (!this.apiKey) return null;

    try {
      const response = await fetch(`${this.baseUrl}/orders/${orderId}`, {
        headers: { "X-API-Key": this.apiKey }
      });
      return await response.json();
    } catch (err) {
      console.error("Prodigi status check failed:", err);
      return null;
    }
  }

  /**
   * Get product details by SKU
   */
  async getProduct(sku) {
    if (!this.apiKey) return null;

    try {
      const response = await fetch(`${this.baseUrl}/products/${sku}`, {
        headers: { "X-API-Key": this.apiKey }
      });
      const result = await response.json();
      return result.outcome === "Ok" ? result.product : null;
    } catch (err) {
      console.error("Prodigi product lookup failed:", err);
      return null;
    }
  }

  /**
   * Get available products for MythicBee
   */
  async getMythicBeeProducts() {
    const skus = [
      "GLOBAL-FAP-16x24",  // Poster
      "GLOBAL-FC-8X6",     // Greeting card (if available)
    ];

    const products = [];
    for (const sku of skus) {
      const product = await this.getProduct(sku);
      if (product) {
        products.push({
          id: sku,
          name: product.description,
          dimensions: product.productDimensions,
          printAreas: product.printAreas
        });
      }
    }
    return products;
  }

  /**
   * Generate print asset URL from manifest
   * (In production, this renders the actual artwork)
   */
  async generatePrintAsset(manifest, brief) {
    // For now, return placeholder
    // In production: render template → upload to CDN → return URL
    return "https://pwintyimages.blob.core.windows.net/samples/stars/test-sample-grey.png";
  }
}

export default ProdigiIntegration;
