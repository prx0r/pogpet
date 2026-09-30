/**
 * MythicBee — Order Management
 * Simple order tracking for manual fulfilment
 * Stores orders locally + R2
 */

class OrderManager {
  constructor() {
    this.orders = [];
    this.loadOrders();
  }

  loadOrders() {
    try {
      const stored = localStorage.getItem("mythicbee-orders");
      this.orders = stored ? JSON.parse(stored) : [];
    } catch (e) {
      this.orders = [];
    }
  }

  saveOrders() {
    localStorage.setItem("mythicbee-orders", JSON.stringify(this.orders));
  }

  /**
   * Create a new order
   */
  createOrder(orderData) {
    const order = {
      id: `MB-${Date.now().toString(36).toUpperCase()}`,
      createdAt: new Date().toISOString(),
      status: "pending",
      
      // Customer info
      customer: {
        name: orderData.customerName,
        email: orderData.customerEmail,
        source: orderData.source || "etsy"
      },
      
      // Gift brief
      brief: {
        recipient: orderData.recipientName,
        relationship: orderData.relationship,
        occasion: orderData.occasion,
        age: orderData.age,
        interests: orderData.interests || [],
        personality: orderData.personality,
        description: orderData.description,
        tone: orderData.tone
      },
      
      // Product
      product: {
        type: orderData.productType, // "dogcasso" or "gamewinners"
        variant: orderData.variant,   // "digital", "card", "print", "acrylic"
        price: orderData.price,
        currency: orderData.currency || "GBP"
      },
      
      // Assets
      assets: {
        customerPhoto: orderData.customerPhoto || null,
        generatedImages: [],
        finalImage: null
      },
      
      // Fulfilment
      fulfilment: {
        method: orderData.variant === "digital" ? "digital" : "prodigi",
        prodigiOrderId: null,
        trackingUrl: null,
        recipientUrl: `https://mythicbee.com/r/${this.generatePortalId()}`
      },
      
      // Timeline
      timeline: [
        { event: "order_created", at: new Date().toISOString() }
      ]
    };

    this.orders.push(order);
    this.saveOrders();
    return order;
  }

  /**
   * Update order status
   */
  updateOrder(orderId, updates) {
    const order = this.orders.find(o => o.id === orderId);
    if (!order) return null;

    Object.assign(order, updates);
    order.timeline.push({
      event: "order_updated",
      at: new Date().toISOString(),
      changes: Object.keys(updates)
    });

    this.saveOrders();
    return order;
  }

  /**
   * Mark image generated
   */
  markImageGenerated(orderId, imageUrl, prompt) {
    const order = this.orders.find(o => o.id === orderId);
    if (!order) return null;

    order.assets.generatedImages.push({
      url: imageUrl,
      prompt,
      generatedAt: new Date().toISOString()
    });

    order.status = "image_ready";
    order.timeline.push({
      event: "image_generated",
      at: new Date().toISOString()
    });

    this.saveOrders();
    return order;
  }

  /**
   * Mark image selected
   */
  markImageSelected(orderId, imageUrl) {
    const order = this.orders.find(o => o.id === orderId);
    if (!order) return null;

    order.assets.finalImage = imageUrl;
    order.status = "approved";
    order.timeline.push({
      event: "image_approved",
      at: new Date().toISOString()
    });

    this.saveOrders();
    return order;
  }

  /**
   * Mark fulfilled
   */
  markFulfilled(orderId, trackingUrl) {
    const order = this.orders.find(o => o.id === orderId);
    if (!order) return null;

    order.status = "fulfilled";
    order.fulfilment.trackingUrl = trackingUrl;
    order.timeline.push({
      event: "order_fulfilled",
      at: new Date().toISOString()
    });

    this.saveOrders();
    return order;
  }

  /**
   * Get order by ID
   */
  getOrder(orderId) {
    return this.orders.find(o => o.id === orderId) || null;
  }

  /**
   * Get all orders
   */
  getOrders(filters = {}) {
    let results = [...this.orders];
    
    if (filters.status) {
      results = results.filter(o => o.status === filters.status);
    }
    if (filters.type) {
      results = results.filter(o => o.product.type === filters.type);
    }
    if (filters.from) {
      results = results.filter(o => new Date(o.createdAt) >= new Date(filters.from));
    }
    
    return results;
  }

  /**
   * Generate stats
   */
  getStats() {
    const total = this.orders.length;
    const digital = this.orders.filter(o => o.product.variant === "digital").length;
    const physical = this.orders.filter(o => o.product.variant !== "digital").length;
    const revenue = this.orders.reduce((sum, o) => sum + (o.product.price || 0), 0);
    const dogcasso = this.orders.filter(o => o.product.type === "dogcasso").length;
    const gamewinners = this.orders.filter(o => o.product.type === "gamewinners").length;

    return {
      total,
      digital,
      physical,
      revenue,
      dogcasso,
      gamewinners,
      conversionRate: total > 0 ? (physical / total * 100).toFixed(1) + "%" : "0%"
    };
  }

  /**
   * Generate portal ID
   */
  generatePortalId() {
    return Math.random().toString(36).substring(2, 8).toUpperCase();
  }
}

export default OrderManager;
