/**
 * MythicBee — 3D Bartholomew
 * Three.js character with animated wings, antenna, and idle motion
 */

class Bartholomew3D {
  constructor(container) {
    this.container = container;
    this.scene = null;
    this.camera = null;
    this.renderer = null;
    this.bee = null;
    this.wings = [];
    this.antennae = [];
    this.cape = null;
    this.time = 0;
    this.state = 'idle';
  }

  async init() {
    // Dynamic import Three.js
    const THREE = await import('https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js');
    this.THREE = THREE;

    // Scene
    this.scene = new THREE.Scene();
    this.scene.background = null; // Transparent

    // Camera
    this.camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
    this.camera.position.set(0, 0.5, 2.5);
    this.camera.lookAt(0, 0, 0);

    // Renderer
    this.renderer = new THREE.WebGLRenderer({ 
      alpha: true, 
      antialias: true,
      powerPreference: "high-performance"
    });
    this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.shadowMap.enabled = true;
    this.container.appendChild(this.renderer.domElement);

    // Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    this.scene.add(ambientLight);

    const directionalLight = new THREE.DirectionalLight(0xffd700, 0.8);
    directionalLight.position.set(2, 3, 2);
    directionalLight.castShadow = true;
    this.scene.add(directionalLight);

    const rimLight = new THREE.DirectionalLight(0xd4af37, 0.4);
    rimLight.position.set(-1, 1, -2);
    this.scene.add(rimLight);

    // Build Bartholomew
    this.buildBee(THREE);

    // Start animation
    this.animate();

    // Handle resize
    window.addEventListener('resize', () => this.onResize());

    console.log("Bartholomew 3D initialized");
  }

  buildBee(THREE) {
    this.bee = new THREE.Group();

    // ── Body (main thorax) ──────────────────────────────
    const bodyGeom = new THREE.CapsuleGeometry(0.25, 0.4, 8, 16);
    const bodyMat = new THREE.MeshStandardMaterial({
      color: 0xffd700,
      metalness: 0.3,
      roughness: 0.4
    });
    const body = new THREE.Mesh(bodyGeom, bodyMat);
    body.rotation.z = Math.PI / 2;
    body.castShadow = true;
    this.bee.add(body);

    // Black stripes
    const stripeGeom = new THREE.CapsuleGeometry(0.26, 0.08, 8, 16);
    const stripeMat = new THREE.MeshStandardMaterial({ color: 0x1a1a2e });
    
    [-0.12, 0.0, 0.12].forEach(z => {
      const stripe = new THREE.Mesh(stripeGeom, stripeMat);
      stripe.rotation.z = Math.PI / 2;
      stripe.position.z = z;
      this.bee.add(stripe);
    });

    // ── Head ────────────────────────────────────────────
    const headGeom = new THREE.SphereGeometry(0.2, 16, 16);
    const headMat = new THREE.MeshStandardMaterial({
      color: 0xffd700,
      metalness: 0.3,
      roughness: 0.4
    });
    const head = new THREE.Mesh(headGeom, headMat);
    head.position.set(0.35, 0.1, 0);
    head.castShadow = true;
    this.bee.add(head);

    // Eyes
    const eyeGeom = new THREE.SphereGeometry(0.05, 16, 16);
    const eyeMat = new THREE.MeshStandardMaterial({ 
      color: 0x6b3fa0,
      emissive: 0x6b3fa0,
      emissiveIntensity: 0.3
    });
    
    const leftEye = new THREE.Mesh(eyeGeom, eyeMat);
    leftEye.position.set(0.48, 0.15, 0.08);
    this.bee.add(leftEye);
    
    const rightEye = new THREE.Mesh(eyeGeom, eyeMat);
    rightEye.position.set(0.48, 0.15, -0.08);
    this.bee.add(rightEye);

    // Eye highlights
    const highlightGeom = new THREE.SphereGeometry(0.02, 8, 8);
    const highlightMat = new THREE.MeshBasicMaterial({ color: 0xffffff });
    
    const leftHighlight = new THREE.Mesh(highlightGeom, highlightMat);
    leftHighlight.position.set(0.52, 0.18, 0.1);
    this.bee.add(leftHighlight);
    
    const rightHighlight = new THREE.Mesh(highlightGeom, highlightMat);
    rightHighlight.position.set(0.52, 0.18, -0.06);
    this.bee.add(rightHighlight);

    // ── Antennae ────────────────────────────────────────
    const antennaGeom = new THREE.CylinderGeometry(0.01, 0.015, 0.25, 8);
    const antennaMat = new THREE.MeshStandardMaterial({ color: 0x1a1a2e });
    
    const leftAntenna = new THREE.Mesh(antennaGeom, antennaMat);
    leftAntenna.position.set(0.35, 0.35, 0.08);
    leftAntenna.rotation.z = -0.3;
    leftAntenna.rotation.x = 0.2;
    this.bee.add(leftAntenna);
    this.antennae.push(leftAntenna);
    
    const rightAntenna = new THREE.Mesh(antennaGeom, antennaMat);
    rightAntenna.position.set(0.35, 0.35, -0.08);
    rightAntenna.rotation.z = -0.3;
    rightAntenna.rotation.x = -0.2;
    this.bee.add(rightAntenna);
    this.antennae.push(rightAntenna);

    // Antenna tips (balls)
    const tipGeom = new THREE.SphereGeometry(0.025, 8, 8);
    const tipMat = new THREE.MeshStandardMaterial({ 
      color: 0xffd700,
      emissive: 0xffd700,
      emissiveIntensity: 0.2
    });
    
    const leftTip = new THREE.Mesh(tipGeom, tipMat);
    leftTip.position.set(0.28, 0.48, 0.12);
    this.bee.add(leftTip);
    this.antennae.push(leftTip);
    
    const rightTip = new THREE.Mesh(tipGeom, tipMat);
    rightTip.position.set(0.28, 0.48, -0.12);
    this.bee.add(rightTip);
    this.antennae.push(rightTip);

    // ── Wings (4 wings, translucent) ────────────────────
    const wingShape = new THREE.Shape();
    wingShape.moveTo(0, 0);
    wingShape.bezierCurveTo(0.15, 0.1, 0.3, 0.15, 0.35, 0.05);
    wingShape.bezierCurveTo(0.3, -0.05, 0.15, -0.1, 0, 0);
    
    const wingGeom = new THREE.ShapeGeometry(wingShape);
    const wingMat = new THREE.MeshStandardMaterial({
      color: 0xe8f0ff,
      transparent: true,
      opacity: 0.6,
      side: THREE.DoubleSide,
      metalness: 0.1,
      roughness: 0.2
    });

    // Left front wing
    const leftFront = new THREE.Mesh(wingGeom, wingMat);
    leftFront.position.set(-0.1, 0.2, 0.15);
    leftFront.rotation.x = -0.5;
    leftFront.scale.set(1.2, 1.2, 1.2);
    this.bee.add(leftFront);
    this.wings.push(leftFront);

    // Left back wing
    const leftBack = new THREE.Mesh(wingGeom, wingMat);
    leftBack.position.set(-0.15, 0.18, 0.18);
    leftBack.rotation.x = -0.3;
    leftBack.scale.set(0.9, 0.9, 0.9);
    this.bee.add(leftBack);
    this.wings.push(leftBack);

    // Right front wing
    const rightFront = new THREE.Mesh(wingGeom, wingMat);
    rightFront.position.set(-0.1, 0.2, -0.15);
    rightFront.rotation.x = 0.5;
    rightFront.scale.set(1.2, 1.2, 1.2);
    this.bee.add(rightFront);
    this.wings.push(rightFront);

    // Right back wing
    const rightBack = new THREE.Mesh(wingGeom, wingMat);
    rightBack.position.set(-0.15, 0.18, -0.18);
    rightBack.rotation.x = 0.3;
    rightBack.scale.set(0.9, 0.9, 0.9);
    this.bee.add(rightBack);
    this.wings.push(rightBack);

    // ── Cape ────────────────────────────────────────────
    const capeGeom = new THREE.PlaneGeometry(0.3, 0.4, 8, 8);
    const capeMat = new THREE.MeshStandardMaterial({
      color: 0xcc3333,
      side: THREE.DoubleSide,
      roughness: 0.6
    });
    this.cape = new THREE.Mesh(capeGeom, capeMat);
    this.cape.position.set(-0.15, 0.1, 0);
    this.cape.rotation.y = Math.PI;
    this.cape.rotation.x = 0.2;
    this.bee.add(this.cape);

    // ── Arms (tiny) ─────────────────────────────────────
    const armGeom = new THREE.CapsuleGeometry(0.02, 0.12, 4, 8);
    const armMat = new THREE.MeshStandardMaterial({ color: 0xffd700 });
    
    const leftArm = new THREE.Mesh(armGeom, armMat);
    leftArm.position.set(0.15, -0.05, 0.2);
    leftArm.rotation.z = -0.5;
    leftArm.rotation.x = 0.3;
    this.bee.add(leftArm);
    
    const rightArm = new THREE.Mesh(armGeom, armMat);
    rightArm.position.set(0.15, -0.05, -0.2);
    rightArm.rotation.z = -0.5;
    rightArm.rotation.x = -0.3;
    this.bee.add(rightArm);

    // Position the whole bee
    this.bee.position.y = 0.2;
    this.bee.rotation.y = -0.3; // Slight angle
    this.scene.add(this.bee);
  }

  animate() {
    requestAnimationFrame(() => this.animate());
    
    this.time += 0.016;
    
    if (this.bee) {
      // Idle hover
      this.bee.position.y = 0.2 + Math.sin(this.time * 1.5) * 0.08;
      this.bee.rotation.z = Math.sin(this.time * 0.8) * 0.05;
      this.bee.rotation.x = Math.sin(this.time * 1.2) * 0.03;
      
      // Wing flutter (fast!)
      this.wings.forEach((wing, i) => {
        const speed = 15 + i * 2;
        const amplitude = 0.4 + i * 0.1;
        wing.rotation.y = Math.sin(this.time * speed) * amplitude;
      });
      
      // Antenna bob
      this.antennae.forEach((ant, i) => {
        if (ant.geometry.type === 'SphereGeometry') {
          // Tips only
          ant.position.y = 0.48 + Math.sin(this.time * 2 + i) * 0.02;
        }
      });
      
      // Cape sway
      if (this.cape) {
        this.cape.rotation.x = 0.2 + Math.sin(this.time * 2) * 0.1;
        this.cape.position.y = 0.1 + Math.sin(this.time * 1.5) * 0.02;
      }
    }

    this.renderer.render(this.scene, this.camera);
  }

  onResize() {
    const w = this.container.clientWidth;
    const h = this.container.clientHeight;
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(w, h);
  }

  setState(newState) {
    this.state = newState;
    // Could trigger different animations here
  }

  destroy() {
    this.renderer.dispose();
    this.container.removeChild(this.renderer.domElement);
  }
}

export default Bartholomew3D;
