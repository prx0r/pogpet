/**
 * MythicBee — Print Pipeline
 * Generates print-ready PDF + QR code from ExperienceManifest
 * Uses jsPDF for PDF generation and qrcode.js for QR
 */

class PrintPipeline {
  constructor() {
    this.manifest = null;
    this.brief = null;
  }

  /**
   * Generate a print-ready card PDF
   */
  async generateCard(manifest, brief) {
    this.manifest = manifest;
    this.brief = brief;

    // Dynamic import of jsPDF
    const { jsPDF } = await import("https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.2/jspdf.umd.min.js");

    // Card dimensions (mm) — Classic folded card
    const width = 148; // A5 landscape
    const height = 105;

    const doc = new jsPDF({
      orientation: "landscape",
      unit: "mm",
      format: [width, height]
    });

    // ── Front of card ──────────────────────────────────────────────
    doc.setFillColor(26, 26, 46); // Deep navy
    doc.rect(0, 0, width, height, "F");

    // Gold accent line
    doc.setFillColor(212, 175, 55);
    doc.rect(10, 10, width - 20, 0.5, "F");

    // Title
    doc.setFont("helvetica", "bold");
    doc.setFontSize(28);
    doc.setTextColor(245, 240, 231);
    doc.text(manifest.scene?.title || "THE LEGEND", width / 2, 40, { align: "center" });

    // Subtitle
    doc.setFont("helvetica", "normal");
    doc.setFontSize(14);
    doc.setTextColor(212, 175, 55);
    doc.text(brief.recipient?.toUpperCase() || "LEGEND", width / 2, 52, { align: "center" });

    // Rating badge
    doc.setFontSize(48);
    doc.setTextColor(212, 175, 55);
    doc.text("99", width / 2, 80, { align: "center" });

    doc.setFontSize(10);
    doc.setTextColor(245, 240, 231);
    doc.text("RATING", width / 2, 88, { align: "center" });

    // Gold accent line
    doc.setFillColor(212, 175, 55);
    doc.rect(10, height - 15, width - 20, 0.5, "F");

    // QR placeholder area
    doc.setFontSize(8);
    doc.setTextColor(150, 150, 150);
    doc.text("SCAN FOR DIGITAL EXPERIENCE", width - 30, height - 8, { align: "center" });

    // ── Back of card ──────────────────────────────────────────────
    doc.addPage([width, height], "landscape");
    
    doc.setFillColor(245, 240, 231); // Cream
    doc.rect(0, 0, width, height, "F");

    // Message
    doc.setFont("helvetica", "italic");
    doc.setFontSize(14);
    doc.setTextColor(26, 26, 46);
    
    const message = brief.creativeDirection || brief.description || "You make every day better just by being you.";
    const lines = doc.splitTextToSize(`"${message}"`, width - 40);
    doc.text(lines, width / 2, 35, { align: "center" });

    // From
    doc.setFont("helvetica", "normal");
    doc.setFontSize(12);
    doc.setTextColor(107, 107, 107);
    doc.text(`— ${brief.sender || "Someone who loves you"}`, width / 2, 35 + lines.length * 7 + 10, { align: "center" });

    // MythicBee branding
    doc.setFontSize(8);
    doc.setTextColor(212, 175, 55);
    doc.text("Made with ✦ by MythicBee", width / 2, height - 10, { align: "center" });

    // ── Generate QR code ──────────────────────────────────────────
    const qrDataUrl = await this.generateQR(manifest.portalId || "demo");

    // Add QR to front page
    doc.setPage(1);
    if (qrDataUrl) {
      doc.addImage(qrDataUrl, "PNG", width - 30, height - 28, 18, 18);
    }

    return doc;
  }

  /**
   * Generate QR code data URL
   */
  async generateQR(portalId) {
    try {
      const QRCode = await import("https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js");
      
      const container = document.createElement("div");
      container.style.display = "none";
      document.body.appendChild(container);

      new QRCode(container, {
        text: `https://mythicbee.com/r/${portalId}`,
        width: 128,
        height: 128,
        colorDark: "#1a1a2e",
        colorLight: "#ffffff",
      });

      const canvas = container.querySelector("canvas");
      const dataUrl = canvas ? canvas.toDataURL("image/png") : null;
      container.remove();
      return dataUrl;
    } catch (e) {
      console.error("QR generation failed:", e);
      return null;
    }
  }

  /**
   * Generate a print-ready poster PDF
   */
  async generatePoster(manifest, brief) {
    const { jsPDF } = await import("https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.2/jspdf.umd.min.js");

    const doc = new jsPDF({
      orientation: "portrait",
      unit: "mm",
      format: "a4"
    });

    // Background
    doc.setFillColor(26, 26, 46);
    doc.rect(0, 0, 210, 297, "F");

    // Gold accent
    doc.setFillColor(212, 175, 55);
    doc.rect(20, 20, 170, 0.5, "F");
    doc.rect(20, 277, 170, 0.5, "F");

    // Title
    doc.setFont("helvetica", "bold");
    doc.setFontSize(48);
    doc.setTextColor(245, 240, 231);
    doc.text((brief.recipient || "LEGEND").toUpperCase(), 105, 80, { align: "center" });

    // Subtitle
    doc.setFont("helvetica", "normal");
    doc.setFontSize(16);
    doc.setTextColor(212, 175, 55);
    doc.text("A LIVING LEGEND", 105, 95, { align: "center" });

    // Rating
    doc.setFontSize(120);
    doc.setTextColor(212, 175, 55);
    doc.text("99", 105, 180, { align: "center" });

    doc.setFontSize(14);
    doc.setTextColor(245, 240, 231);
    doc.text("OVERALL RATING", 105, 200, { align: "center" });

    // Branding
    doc.setFontSize(10);
    doc.setTextColor(150, 150, 150);
    doc.text("Made with ✦ by MythicBee", 105, 280, { align: "center" });

    return doc;
  }

  /**
   * Save PDF and trigger download
   */
  download(doc, filename) {
    doc.save(filename);
  }

  /**
   * Get PDF as blob for upload to Prodigi
   */
  getBlob(doc) {
    return doc.output("blob");
  }
}

export default PrintPipeline;
