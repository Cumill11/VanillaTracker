/**
 * Zamienia plik czcionki na moduł TypeScript z zawartością w base64.
 *
 *   node scripts/font-to-module.mjs src/assets/DroidSans-latin-pl.ttf src/assets/protocolFont.ts
 *
 * Worker nie potrafi wczytać pliku binarnego z dysku, a wtyczka Cloudflare
 * blokuje importy zasobów przez `?inline` — czcionka musi więc trafić do
 * pakietu jako zwykły napis.
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { basename } from 'node:path';

const [source, target] = process.argv.slice(2);
if (!source || !target) {
  console.error('Użycie: node scripts/font-to-module.mjs <czcionka.ttf> <moduł.ts>');
  process.exit(1);
}

const bytes = readFileSync(source);
const base64 = bytes.toString('base64');

const module = `/**
 * Czcionka protokołu przekazania, zapisana w base64.
 *
 * Plik wygenerowany z \`${basename(source)}\` poleceniem:
 *   node scripts/font-to-module.mjs ${source} ${target}
 * Nie edytuj ręcznie.
 */
export const PROTOCOL_FONT_BASE64 =
  '${base64}';
`;

writeFileSync(target, module);
console.error(
  `${basename(source)}: ${(bytes.length / 1024).toFixed(1)} kB -> ${(base64.length / 1024).toFixed(1)} kB w base64`,
);
