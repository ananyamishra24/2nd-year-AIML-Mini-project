/* ─── Balloons animation wrapper ──────────────────────────
   Vanilla JS equivalent of the React balloons component.
   Uses locally vendored balloons-js (client/js/balloons-lib.js)
   to avoid CSP / external script restrictions.
──────────────────────────────────────────────────────── */

let _balloons = null;
let _textBalloons = null;
let _loading = null;

async function loadLib() {
  if (_balloons) return;
  if (_loading) return _loading;
  _loading = import('/js/balloons-lib.js').then(mod => {
    _balloons = mod.balloons;
    _textBalloons = mod.textBalloons;
  });
  return _loading;
}

/**
 * Launch the default colourful balloons animation.
 * @param {function} [onLaunch] - optional callback fired after launch
 */
export async function launchBalloons(onLaunch) {
  await loadLib();
  _balloons();
  if (onLaunch) onLaunch();
}

/**
 * Launch text balloons.
 * @param {string} text
 * @param {{ fontSize?: number, color?: string }} [opts]
 * @param {function} [onLaunch]
 */
export async function launchTextBalloons(text, opts = {}, onLaunch) {
  await loadLib();
  _textBalloons([{
    text,
    fontSize: opts.fontSize ?? 120,
    color:    opts.color    ?? '#7c3aed',
  }]);
  if (onLaunch) onLaunch();
}
