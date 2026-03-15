import { initScene } from './three-scene.js';

document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('three-canvas');
    if (container) {
        initScene(container);
    }
});
