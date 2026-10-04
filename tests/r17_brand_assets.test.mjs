import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const css = ['styles.css', 'ui/components.css'].map(f => fs.readFileSync(new URL('../frontend/' + f, import.meta.url), 'utf8')).join('\n');
const iconSet = JSON.parse(fs.readFileSync(new URL('../frontend/icons/icon-set.json', import.meta.url), 'utf8'));
const pngSize = path => { const b = fs.readFileSync(new URL('..' + path.replace('/assets', '/frontend'), import.meta.url)); return [b.readUInt32BE(16), b.readUInt32BE(20)]; };

test('R17: slots de marca existem e ícones são quadrados', () => {
  for (const slot of ['brand.logo', 'brand.icon', 'brand.favicon']) assert.ok(iconSet.icons[slot], slot);
  for (const slot of ['brand.icon', 'brand.favicon']) { const [w, h] = pngSize(iconSet.icons[slot]); assert.equal(w, h, `${slot} não é quadrado`); }
});

test('R17: toda imagem de marca usa object-fit: contain (sem corte ou distorção)', () => {
  for (const cls of ['brand-logo', 'r2-login-logo', 'public-logo']) {
    const rules = [...css.matchAll(new RegExp(`\\.${cls}\\{([^}]*)\\}`, 'g'))].map(m => m[1]).join(';');
    assert.match(rules, /object-fit:\s*contain/, `.${cls} sem contain`);
    assert.doesNotMatch(rules, /object-fit:\s*(cover|fill)/, `.${cls} distorce`);
  }
});
