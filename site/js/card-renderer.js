/**
 * MythicBee — Card Renderer
 * Generates deterministic print-ready cards from GiftBrief
 * Outputs 300dpi JPG/PDF ready for Prodigi
 */

class CardRenderer {
  constructor() {
    this.canvas = document.createElement('canvas');
    this.ctx = this.canvas.getContext('2d');
  }

  /**
   * Render a GameWinnerz card
   */
  async renderGameWinnerz(brief, concept, options = {}) {
    const width = 1200;  // 4" at 300dpi
    const height = 1800; // 6" at 300dpi
    this.canvas.width = width;
    this.canvas.height = height;
    const ctx = this.ctx;

    // Background
    const grad = ctx.createLinearGradient(0, 0, 0, height);
    grad.addColorStop(0, '#1a1a2e');
    grad.addColorStop(0.5, '#16213e');
    grad.addColorStop(1, '#0f3460');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, width, height);

    // Gold border
    ctx.strokeStyle = '#d4af37';
    ctx.lineWidth = 8;
    ctx.strokeRect(20, 20, width - 40, height - 40);

    // Inner border
    ctx.strokeStyle = 'rgba(212, 175, 55, 0.3)';
    ctx.lineWidth = 2;
    ctx.strokeRect(30, 30, width - 60, height - 60);

    // Rating circle
    ctx.beginPath();
    ctx.arc(width / 2, 200, 100, 0, Math.PI * 2);
    ctx.fillStyle = '#d4af37';
    ctx.fill();
    ctx.fillStyle = '#1a1a2e';
    ctx.font = 'bold 72px "Playfair Display", serif';
    ctx.textAlign = 'center';
    ctx.fillText('99', width / 2, 225);

    // Name
    ctx.fillStyle = '#f5f0e7';
    ctx.font = 'bold 64px "Playfair Display", serif';
    ctx.fillText((brief.recipient || 'LEGEND').toUpperCase(), width / 2, 380);

    // Title
    ctx.fillStyle = '#d4af37';
    ctx.font = '28px "Inter", sans-serif';
    ctx.letterSpacing = '8px';
    ctx.fillText('THE GAME WINNER', width / 2, 430);

    // Hero image placeholder (would be AI-generated)
    ctx.fillStyle = 'rgba(212, 175, 55, 0.1)';
    ctx.fillRect(100, 480, width - 200, 400);
    ctx.fillStyle = '#d4af37';
    ctx.font = '24px "Inter", sans-serif';
    ctx.fillText('[AI-GENERATED PORTRAIT]', width / 2, 700);

    // Stats
    const stats = [
      { label: 'LOYALTY', value: '99' },
      { label: 'BANTER', value: '97' },
      { label: 'DAD JOKES', value: '100' }
    ];
    stats.forEach((stat, i) => {
      const x = 200 + i * 300;
      ctx.fillStyle = '#d4af37';
      ctx.font = 'bold 48px "Inter", sans-serif';
      ctx.fillText(stat.value, x, 980);
      ctx.fillStyle = '#f5f0e7';
      ctx.font = '20px "Inter", sans-serif';
      ctx.fillText(stat.label, x, 1010);
    });

    // Footer
    ctx.fillStyle = 'rgba(212, 175, 55, 0.5)';
    ctx.font = '18px "Inter", sans-serif';
    ctx.fillText('GAMEWINNERZ', width / 2, 1150);
    ctx.fillText('LEGEND SERIES', width / 2, 1180);

    // Convert to blob
    return new Promise(resolve => {
      this.canvas.toBlob(blob => resolve(blob), 'image/jpeg', 0.95);
    });
  }

  /**
   * Render card back with QR
   */
  async renderBack(brief, portalUrl) {
    const width = 1200;
    const height = 1800;
    this.canvas.width = width;
    this.canvas.height = height;
    const ctx = this.ctx;

    // Background
    ctx.fillStyle = '#1a1a2e';
    ctx.fillRect(0, 0, width, height);

    // Gold border
    ctx.strokeStyle = '#d4af37';
    ctx.lineWidth = 8;
    ctx.strokeRect(20, 20, width - 40, height - 40);

    // Tagline
    ctx.fillStyle = '#f5f0e7';
    ctx.font = '32px "Playfair Display", serif';
    ctx.textAlign = 'center';
    ctx.fillText('HE THOUGHT HIS', width / 2, 400);
    ctx.fillText('PLAYING DAYS', width / 2, 450);
    ctx.fillText('WERE OVER.', width / 2, 500);

    ctx.fillStyle = '#d4af37';
    ctx.font = 'bold 48px "Playfair Display", serif';
    ctx.fillText('THEY WEREN\'T.', width / 2, 600);

    // QR placeholder
    ctx.fillStyle = '#f5f0e7';
    ctx.fillRect(width / 2 - 100, 750, 200, 200);
    ctx.fillStyle = '#1a1a2e';
    ctx.font = '16px "Inter", sans-serif';
    ctx.fillText('[QR CODE]', width / 2, 860);

    // Instructions
    ctx.fillStyle = '#d4af37';
    ctx.font = '24px "Inter", sans-serif';
    ctx.fillText('SCAN TO WITNESS', width / 2, 1050);
    ctx.fillText('THE MOMENT', width / 2, 1090);

    // Footer
    ctx.fillStyle = 'rgba(212, 175, 55, 0.5)';
    ctx.font = '16px "Inter", sans-serif';
    ctx.fillText(portalUrl || 'mythicbee.com/r/LEGEND', width / 2, 1200);

    return new Promise(resolve => {
      this.canvas.toBlob(blob => resolve(blob), 'image/jpeg', 0.95);
    });
  }

  /**
   * Get data URL for preview
   */
  getDataUrl() {
    return this.canvas.toDataURL('image/jpeg', 0.9);
  }
}

export default CardRenderer;
