import * as THREE from '/static/vendor/three/three.module.js';
import { OrbitControls } from '/static/vendor/three/OrbitControls.js';

export function initScene(container) {
    const width = container.clientWidth;
    const height = container.clientHeight;

    // Scene
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x141414);

    // Camera
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
    camera.position.set(3, 3, 3);
   
   
    // Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(window.devicePixelRatio);
    container.appendChild(renderer.domElement);

    // Controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;

    // Cube
    const geometry = new THREE.BoxGeometry(1, 1, 1);
    const material = new THREE.MeshStandardMaterial({
        color: 0x3b82f6,
        metalness: 0.3,
        roughness: 0.4,
    });
    const cube = new THREE.Mesh(geometry, material);
    cube.position.y = 0.5;
    scene.add(cube);

    // Grid
    const grid = new THREE.GridHelper(10, 20, 0x262626, 0x1a1a1a);
    scene.add(grid);

    // Lights
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.4);
    scene.add(ambientLight);

    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
    directionalLight.position.set(5, 10, 7);
    scene.add(directionalLight);

    const pointLight = new THREE.PointLight(0xa855f7, 0.6, 20);
    pointLight.position.set(-3, 3, -3);
    scene.add(pointLight);

    // Animation
    function animate() {
        requestAnimationFrame(animate);
        cube.rotation.y += 0.005;
        cube.rotation.x += 0.002;
        controls.update();
        renderer.render(scene, camera);
    }

    animate();

    // Resize
    window.addEventListener('resize', () => {
        const w = container.clientWidth;
        const h = container.clientHeight;
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
        renderer.setSize(w, h);
    });

    
}
