import * as THREE from '/static/vendor/three/three.module.js';

const MS = 0.007;   // market scale (bumped +1 from 0.006)
const SR = 11 * MS; // semicircle radius = 0.066

// Wood tones
const WD  = 0x7a4a1a;
const WDD = 0x5c3010;
const WDL = 0xb8813c;

function mat(color, opts) {
    return new THREE.MeshLambertMaterial(Object.assign({ color }, opts || {}));
}

function buildStall(awColor) {
    const g = new THREE.Group();
    const H = 3.4 * MS;
    const W = 4.0 * MS;
    const D = 2.8 * MS;
    const postR = 0.12 * MS;

    // 4 corner posts
    const postGeo = new THREE.CylinderGeometry(postR, postR * 1.1, H, 6);
    [[W/2, D/2], [-W/2, D/2], [W/2, -D/2], [-W/2, -D/2]].forEach(([x, z]) => {
        const post = new THREE.Mesh(postGeo, mat(WDD));
        post.position.set(x, H / 2, z);
        g.add(post);
    });

    // Top frame beams
    const beamGeo = new THREE.BoxGeometry(W + 0.28 * MS, 0.1 * MS, 0.1 * MS);
    [D/2, -D/2].forEach(z => {
        const beam = new THREE.Mesh(beamGeo, mat(WDD));
        beam.position.set(0, H - 0.05 * MS, z);
        g.add(beam);
    });
    const sBeamGeo = new THREE.BoxGeometry(0.1 * MS, 0.1 * MS, D + 0.28 * MS);
    [W/2, -W/2].forEach(x => {
        const sBeam = new THREE.Mesh(sBeamGeo, mat(WDD));
        sBeam.position.set(x, H - 0.05 * MS, 0);
        g.add(sBeam);
    });

    // Awning (inclined)
    const awning = new THREE.Mesh(
        new THREE.BoxGeometry(W + 0.55 * MS, 0.08 * MS, D + 1.55 * MS),
        mat(awColor)
    );
    awning.position.set(0, H - 0.32 * MS, -0.28 * MS);
    awning.rotation.x = -0.15;
    g.add(awning);

    // White stripes
    for (let i = 0; i < 3; i++) {
        const stripe = new THREE.Mesh(
            new THREE.BoxGeometry(W + 0.55 * MS, 0.09 * MS, 0.3 * MS),
            mat(0xffffff)
        );
        stripe.position.set(0, H - 0.30 * MS, -0.28 * MS + (i - 1) * 0.52 * MS);
        stripe.rotation.x = -0.15;
        g.add(stripe);
    }

    // Front fringe
    for (let i = 0; i < 9; i++) {
        const fringe = new THREE.Mesh(
            new THREE.BoxGeometry(0.3 * MS, 0.45 * MS, 0.05 * MS),
            mat(awColor)
        );
        fringe.position.set(-1.6 * MS + i * 0.4 * MS, H - 0.45 * MS, D/2 + 0.44 * MS);
        g.add(fringe);
    }

    // Counter
    const counter = new THREE.Mesh(
        new THREE.BoxGeometry(W + 0.18 * MS, 0.22 * MS, 0.72 * MS),
        mat(WDL)
    );
    counter.position.set(0, 0.98 * MS, D/2 - 0.22 * MS);
    g.add(counter);

    // Counter legs
    const cLegGeo = new THREE.BoxGeometry(0.12 * MS, 0.98 * MS, 0.12 * MS);
    [W/2 - 0.22 * MS, -W/2 + 0.22 * MS].forEach(x => {
        const leg = new THREE.Mesh(cLegGeo, mat(WDD));
        leg.position.set(x, 0.49 * MS, D/2 - 0.22 * MS);
        g.add(leg);
    });

    // Floor board
    const floor = new THREE.Mesh(
        new THREE.BoxGeometry(W + 0.35 * MS, 0.04 * MS, D + 0.25 * MS),
        mat(0xa08060)
    );
    floor.position.y = 0.02 * MS;
    g.add(floor);

    // Back display panel
    const panel = new THREE.Mesh(
        new THREE.BoxGeometry(W + 0.18 * MS, 1.1 * MS, 0.05 * MS),
        mat(WD)
    );
    panel.position.set(0, H - 1.85 * MS, -D/2 + 0.035 * MS);
    g.add(panel);

    return g;
}

// One barrel + one crate to the RIGHT of each stall (stall local +X side)
function addStallDecor(stallGroup) {
    const W   = 4.0 * MS;
    const sep = 0.5 * MS;           // gap from stall right edge
    const bx  = W / 2 + sep + 0.5 * MS;  // barrel center X (radius = 0.5*MS)
    const cx  = W / 2 + sep + 0.43 * MS; // crate center X  (half-width = 0.43*MS)

    // Barrel — forward side (+Z, toward customers)
    const barrel = new THREE.Mesh(
        new THREE.CylinderGeometry(0.50 * MS, 0.50 * MS, 1.0 * MS, 8),
        mat(WD)
    );
    barrel.position.set(bx, 0.50 * MS, 0.55 * MS);
    stallGroup.add(barrel);
    [0.28 * MS, -0.28 * MS].forEach(dy => {
        const ring = new THREE.Mesh(
            new THREE.CylinderGeometry(0.53 * MS, 0.53 * MS, 0.07 * MS, 8),
            mat(0x555555)
        );
        ring.position.set(bx, 0.50 * MS + dy, 0.55 * MS);
        stallGroup.add(ring);
    });

    // Crate — slightly back (-Z, toward vendor side)
    const crate = new THREE.Mesh(
        new THREE.BoxGeometry(0.85 * MS, 0.68 * MS, 0.85 * MS),
        mat(WDL)
    );
    crate.position.set(cx, 0.34 * MS, -0.55 * MS);
    stallGroup.add(crate);
    const lid = new THREE.Mesh(
        new THREE.BoxGeometry(0.88 * MS, 0.05 * MS, 0.88 * MS),
        mat(WDD)
    );
    lid.position.set(cx, 0.71 * MS, -0.55 * MS);
    stallGroup.add(lid);
    // Lid cross slats
    ['x', 'z'].forEach(axis => {
        const slat = new THREE.Mesh(
            new THREE.BoxGeometry(
                axis === 'x' ? 0.88 * MS : 0.06 * MS,
                0.04 * MS,
                axis === 'z' ? 0.88 * MS : 0.06 * MS
            ),
            mat(WD)
        );
        slat.position.set(cx, 0.74 * MS, -0.55 * MS);
        stallGroup.add(slat);
    });
}

function addVendor(stallGroup, bodyC, headC, hatC) {
    const g  = new THREE.Group();
    const D  = 2.8 * MS;
    const vz = -0.42 * MS;

    // Head
    const head = new THREE.Mesh(new THREE.SphereGeometry(0.31 * MS, 8, 6), mat(headC));
    head.position.set(0, 1.64 * MS, vz);
    g.add(head);

    // Hat brim
    const brim = new THREE.Mesh(
        new THREE.CylinderGeometry(0.46 * MS, 0.46 * MS, 0.06 * MS, 8),
        mat(hatC)
    );
    brim.position.set(0, 2.00 * MS, vz);
    g.add(brim);

    // Hat crown
    const crown = new THREE.Mesh(
        new THREE.CylinderGeometry(0.25 * MS, 0.28 * MS, 0.40 * MS, 8),
        mat(hatC)
    );
    crown.position.set(0, 2.23 * MS, vz);
    g.add(crown);

    // Torso
    const torso = new THREE.Mesh(
        new THREE.CylinderGeometry(0.26 * MS, 0.30 * MS, 0.82 * MS, 8),
        mat(bodyC)
    );
    torso.position.set(0, 0.98 * MS, vz);
    g.add(torso);

    // Apron
    const apron = new THREE.Mesh(
        new THREE.BoxGeometry(0.46 * MS, 0.62 * MS, 0.04 * MS),
        mat(0xf2f0e0)
    );
    apron.position.set(0, 0.80 * MS, vz + 0.25 * MS);
    g.add(apron);

    // Arms
    const armGeo = new THREE.CylinderGeometry(0.09 * MS, 0.09 * MS, 0.62 * MS, 5);
    [-1, 1].forEach(side => {
        const arm = new THREE.Mesh(armGeo, mat(bodyC));
        arm.rotation.z = side * 0.46;
        arm.position.set(side * 0.50 * MS, 1.12 * MS, vz);
        g.add(arm);
        const hand = new THREE.Mesh(new THREE.SphereGeometry(0.10 * MS, 6, 4), mat(headC));
        hand.position.set(side * 0.79 * MS, 0.90 * MS, vz);
        g.add(hand);
    });

    // Legs + feet
    const legGeo = new THREE.CylinderGeometry(0.10 * MS, 0.10 * MS, 0.52 * MS, 5);
    [-0.14 * MS, 0.14 * MS].forEach(lx => {
        const leg = new THREE.Mesh(legGeo, mat(0x333366));
        leg.position.set(lx, 0.28 * MS, vz);
        g.add(leg);
        const foot = new THREE.Mesh(
            new THREE.BoxGeometry(0.13 * MS, 0.07 * MS, 0.24 * MS),
            mat(0x222222)
        );
        foot.position.set(lx, 0.02 * MS, vz + 0.04 * MS);
        g.add(foot);
    });

    stallGroup.add(g);
}

function addProducts(stallGroup, type) {
    const g    = new THREE.Group();
    const D    = 2.8 * MS;
    const ctrY = 1.09 * MS;
    const cz   = D / 2 - 0.22 * MS;

    if (type === 'frutas') {
        const basket = new THREE.Mesh(
            new THREE.CylinderGeometry(0.55 * MS, 0.42 * MS, 0.28 * MS, 8),
            mat(0xc8a050)
        );
        basket.position.set(0, ctrY + 0.14 * MS, cz);
        g.add(basket);
        [[-0.9, 0xdd2200], [-0.35, 0xff6600], [0.2, 0x228833],
         [0.75, 0xffdd00], [1.3, 0xee3388]].forEach(([dx, c]) => {
            const fr = new THREE.Mesh(new THREE.SphereGeometry(0.17 * MS, 7, 5), mat(c));
            fr.position.set(dx * MS, ctrY + 0.32 * MS, cz);
            g.add(fr);
        });
    } else if (type === 'carniceria') {
        for (let i = 0; i < 3; i++) {
            const slab = new THREE.Mesh(
                new THREE.BoxGeometry(0.48 * MS, 0.16 * MS, 0.38 * MS),
                mat(0xcc3333)
            );
            slab.position.set((i - 1) * 0.72 * MS, ctrY + 0.08 * MS, cz);
            g.add(slab);
        }
        const H = 3.4 * MS;
        for (let i = 0; i < 5; i++) {
            const sau = new THREE.Mesh(
                new THREE.CylinderGeometry(0.07 * MS, 0.07 * MS, 0.52 * MS, 5),
                mat(0xaa3322)
            );
            sau.position.set((-2 + i) * 0.62 * MS, H - 0.68 * MS, 0.08 * MS);
            g.add(sau);
        }
    } else if (type === 'pescaderia') {
        const ice = new THREE.Mesh(
            new THREE.BoxGeometry(3.4 * MS, 0.06 * MS, 0.62 * MS),
            mat(0xddeeff)
        );
        ice.position.set(0, ctrY + 0.03 * MS, cz);
        g.add(ice);
        for (let i = 0; i < 4; i++) {
            const fish = new THREE.Mesh(
                new THREE.SphereGeometry(0.21 * MS, 7, 4),
                mat(i % 2 === 0 ? 0x7799bb : 0x4477aa)
            );
            fish.scale.set(1.4, 0.42, 0.9);
            fish.position.set((i - 1.5) * 0.78 * MS, ctrY + 0.10 * MS, cz);
            g.add(fish);
        }
    } else if (type === 'panaderia') {
        for (let i = 0; i < 3; i++) {
            const loaf = new THREE.Mesh(
                new THREE.CylinderGeometry(0.14 * MS, 0.17 * MS, 0.78 * MS, 6),
                mat(0xd4a040)
            );
            loaf.rotation.z = Math.PI / 2;
            loaf.position.set((i - 1) * 0.70 * MS, ctrY + 0.17 * MS, cz);
            g.add(loaf);
        }
        for (let i = 0; i < 2; i++) {
            const rosq = new THREE.Mesh(
                new THREE.TorusGeometry(0.19 * MS, 0.06 * MS, 5, 8),
                mat(0xd4a040)
            );
            rosq.rotation.x = Math.PI / 2;
            rosq.position.set((i - 0.5) * 0.55 * MS, ctrY + 0.19 * MS, cz + 0.38 * MS);
            g.add(rosq);
        }
    } else if (type === 'especias') {
        [[-0.85, 0xdd6600], [-0.28, 0xffcc00], [0.28, 0xee2200], [0.85, 0x884411]].forEach(([dx, c]) => {
            const cone = new THREE.Mesh(new THREE.ConeGeometry(0.21 * MS, 0.32 * MS, 7), mat(c));
            cone.position.set(dx * MS, ctrY + 0.16 * MS, cz);
            g.add(cone);
        });
        for (let i = 0; i < 3; i++) {
            const sack = new THREE.Mesh(
                new THREE.CylinderGeometry(0.14 * MS, 0.11 * MS, 0.33 * MS, 6),
                mat(0xd2b080)
            );
            sack.position.set((-1 + i) * 0.68 * MS, ctrY + 0.17 * MS, cz - 0.30 * MS);
            g.add(sack);
        }
    }

    stallGroup.add(g);
}

// Flat ancient stones scattered within the D-shaped market semicircle
function addCobblestones(group) {
    const groundR  = SR + 2.5 * MS;
    const cutZ     = -0.02;   // boundary toward customer side (group local Z)

    const stoneColors = [
        0x8a8878, 0x9a9088, 0x7a7870,
        0xb0a898, 0x686860, 0xa09888,
        0x706860, 0x9890a0,
    ];

    // Seeded deterministic pseudo-random
    let seed = 137;
    const rnd = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967295; };

    const step    = 1.85 * MS;
    const nCells  = Math.ceil(2 * groundR / step) + 2;
    const startXZ = -groundR - step;

    for (let row = 0; row < nCells; row++) {
        for (let col = 0; col < nCells; col++) {
            // Jittered grid position in group local XZ plane
            const px = startXZ + col * step + (rnd() - 0.5) * step * 0.55;
            const pz = startXZ + row * step + (rnd() - 0.5) * step * 0.55;

            // Keep inside D-shape: past cut line + within circle radius
            if (pz < cutZ) continue;
            if (Math.sqrt(px * px + pz * pz) > groundR * 0.97) continue;

            const sw   = (0.60 + rnd() * 0.85) * MS;   // width  (X)
            const sd   = (0.45 + rnd() * 0.75) * MS;   // depth  (Z)
            const sh   = (0.06 + rnd() * 0.05) * MS;   // height (very flat)
            const rotY = rnd() * Math.PI;
            const col2 = Math.floor(rnd() * stoneColors.length);
            // Slight Y variation for uneven ancient-floor feel
            const yJit = (rnd() - 0.5) * 0.015 * MS;

            const stone = new THREE.Mesh(new THREE.BoxGeometry(sw, sh, sd), mat(stoneColors[col2]));
            stone.position.set(px, sh / 2 + yJit, pz);
            stone.rotation.y = rotY;
            group.add(stone);
        }
    }
}

export async function makeMercado(scene) {
    const group = new THREE.Group();

    const stallDefs = [
        { type: 'frutas',     awC: 0xcc1100, bC: 0xcc6633, hC: 0xffcc99, hatC: 0x884422 },
        { type: 'carniceria', awC: 0x226622, bC: 0x2255aa, hC: 0xffcc99, hatC: 0x112266 },
        { type: 'pescaderia', awC: 0x1155bb, bC: 0x882255, hC: 0xffcc99, hatC: 0x551133 },
        { type: 'panaderia',  awC: 0xdd7700, bC: 0x3399aa, hC: 0xffcc99, hatC: 0x115566 },
        { type: 'especias',   awC: 0x882299, bC: 0xbb8833, hC: 0xffcc99, hatC: 0x885522 },
    ];

    stallDefs.forEach((def, i) => {
        const angle = -Math.PI * 0.42 + i * (Math.PI * 0.84 / 4);
        const stall = buildStall(def.awC);
        addProducts(stall, def.type);
        addVendor(stall, def.bC, def.hC, def.hatC);
        addStallDecor(stall);   // barrel + crate to the right of each stall
        stall.position.set(Math.sin(angle) * SR, 0, Math.cos(angle) * SR);
        stall.rotation.y = angle + Math.PI;
        group.add(stall);
    });

    // Ancient cobblestone floor — flat stones scattered inside the semicircle
    addCobblestones(group);

    // Central well in open center of semicircle
    const wellBase = new THREE.Mesh(
        new THREE.CylinderGeometry(0.8 * MS, 0.9 * MS, 0.5 * MS, 8),
        mat(0x888888)
    );
    wellBase.position.set(0, 0.25 * MS, SR * 0.3);
    group.add(wellBase);
    const wellTop = new THREE.Mesh(
        new THREE.CylinderGeometry(0.85 * MS, 0.8 * MS, 0.12 * MS, 8),
        mat(0x666666)
    );
    wellTop.position.set(0, 0.56 * MS, SR * 0.3);
    group.add(wellTop);

    // Visible waypoint disc — at group XZ origin so character target matches disc position
    // (group is placed at offsetX=0.23, offsetZ=-0.05 on the polygon; localX=0,localZ=0 → same spot)
    const wpDisc = new THREE.Mesh(
        new THREE.CylinderGeometry(0.34 * MS, 0.34 * MS, 0.046 * MS, 20),
        new THREE.MeshBasicMaterial({ color: 0xFF6600 })
    );
    wpDisc.position.set(0, 0.62 * MS, 0);
    group.add(wpDisc);

    // Small hitbox at the disc — same footprint as WAYPOINT_BUILDINGS hitboxes (0.5*S/fillScale)
    const hitbox = new THREE.Mesh(
        new THREE.CylinderGeometry(0.5 * MS, 0.5 * MS, 3.0 * MS, 12),
        new THREE.MeshBasicMaterial({ transparent: true, opacity: 0, depthWrite: false })
    );
    hitbox.userData.tipo = 'mercado_waypoint';
    hitbox.userData.marketConfig = { offsetX: 0.23, offsetZ: -0.05, color: 0xFF6600 };
    hitbox.position.set(0, 1.5 * MS, 0);   // centered on the disc
    group.add(hitbox);

    // Rotate market 45° on Y axis, then lay flat for the expand animation
    group.rotation.y = Math.PI / 4;
    group.rotation.x = -Math.PI / 2;
    group.visible = false;
    scene.add(group);

    return { group };
}
