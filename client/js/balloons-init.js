import { launchBalloons } from '/js/balloons.js';
window.launchBalloons = launchBalloons;
// Execute any launch that was requested before this module finished loading
window._execBalloons?.();
