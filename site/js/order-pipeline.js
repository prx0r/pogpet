/**
 * MythicBee — Order Pipeline
 * Conversation → GiftBrief → Artwork → Prodigi → Tracking
 * Zero human intervention
 */

import ProdigiProvider from './prodigi-provider.js';
import CardRenderer from './card-renderer.js';

const prodigi = new ProdigiProvider();
const renderer = new CardRenderer();

// Product catalog with Prodigi SKUs (canonical set: character-kit/docs/prodigi/CANONICAL_PRODUCTS.md)
const PRODUCTS = {
  "digital": {
    name: "Personalised Video",
    price: 6.99,
    fulfilment: "digital",
    description: "Your pet, brought to life"
  },
  "reveal-card": {
    name: "Video + Portal Card",
    price: 12.99,
    fulfilment: "prodigi",
    sku: "GLOBAL-GRE-MOH-7X5-BLA",
    description: "7×5 portal card + video reveal"
  },
  "gift-card": {
    name: "Mug Portal",
    price: 19.99,
    fulfilment: "prodigi",
    sku: "GLOBAL-MUG-W",
    description: "11oz photo mug + video reveal"
  },
  "legend-block": {
    name: "Cushion Portal",
    price: 29.99,
    fulfilment: "prodigi",
    sku: "GLOBAL-CUSH-12X12-CAN",
    description: "12in canvas cushion + video reveal"
  }
};

class OrderPipeline {
  constructor() {
    this.orders = [];
  }

  /**
   * Create order from conversation
   */
  createOrder(brief, productType, recipientAddress) {
    const product = PRODUCTS[productType];
    if (!product) throw new Error(`Unknown product: ${productType}`);

    const orderId = `MM-${Date.now().toString(36).toUpperCase()}`;
    const portalUrl = `https://mogmug.com/x/${orderId}`;

    const order = {
      id: orderId,
      createdAt: new Date().toISOString(),
      status: "created",
      brief: { ...brief },
      product: {
        type: productType,
        name: product.name,
        price: product.price,
        fulfilment: product.fulfilment,
        sku: product.sku
      },
      recipient: recipientAddress,
      portalUrl: portalUrl,
      artwork: {
        front: null,
        back: null
      },
      supplier: {
        orderId: null,
        status: null,
        tracking: null
      }
    };

    this.orders.push(order);
    return order;
  }

  /**
   * Process order end-to-end
   */
  async processOrder(orderId) {
    const order = this.orders.find(o => o.id === orderId);
    if (!order) throw new Error(`Order not found: ${orderId}`);

    try {
      // 1. Update status
      order.status = "generating";

      // 2. Generate artwork
      if (order.product.fulfilment !== "digital") {
        const frontBlob = await renderer.renderGameWinnerz(order.brief, null);
        const backBlob = await renderer.renderBack(order.brief, order.portalUrl);

        // 3. Upload to storage (would be R2 in production)
        order.artwork.front = await this.uploadArtwork(frontBlob, `${order.id}-front.jpg`);
        order.artwork.back = await this.uploadArtwork(backBlob, `${order.id}-back.jpg`);
      }

      // 4. Submit to Prodigi (if physical)
      if (order.product.fulfilment === "prodigi" && order.recipient) {
        order.status = "submitting";
        
        const result = await prodigi.processOrder({
          orderId: order.id,
          productType: order.product.type,
          artworkUrl: order.artwork.front,
          recipient: order.recipient,
          shipping: "Standard"
        });

        if (result.success) {
          order.supplier.orderId = result.orderId;
          order.supplier.status = result.status;
          order.status = "submitted";
        } else {
          order.status = "failed";
          order.error = result.error;
        }
      } else {
        // Digital order — ready immediately
        order.status = "ready";
      }

      return order;
    } catch (err) {
      order.status = "failed";
      order.error = err.message;
      return order;
    }
  }

  /**
   * Upload artwork to storage
   */
  async uploadArtwork(blob, filename) {
    // In production: upload to R2 and return public URL
    // For now: return blob URL
    return URL.createObjectURL(blob);
  }

  /**
   * Get order status
   */
  getOrder(orderId) {
    return this.orders.find(o => o.id === orderId);
  }

  /**
   * Get all orders
   */
  getOrders() {
    return [...this.orders];
  }

  /**
   * Get stats
   */
  getStats() {
    const total = this.orders.length;
    const revenue = this.orders.reduce((sum, o) => sum + (o.product?.price || 0), 0);
    const digital = this.orders.filter(o => o.product.fulfilment === "digital").length;
    const physical = this.orders.filter(o => o.product.fulfilment !== "digital").length;
    const pending = this.orders.filter(o => ["created", "generating", "submitting"].includes(o.status)).length;
    const ready = this.orders.filter(o => o.status === "ready").length;
    const shipped = this.orders.filter(o => o.status === "shipped").length;

    return { total, revenue, digital, physical, pending, ready, shipped };
  }
}

export default OrderPipeline;
