/**
 * Protokół przekazania sprzętu (PDF, A4).
 *
 * Dokument do wydrukowania i podpisania przy wydaniu sprzętu pracownikowi.
 * W odróżnieniu od etykiet potrzebuje polskich znaków, a wbudowane czcionki
 * pdf-lib ich nie mają (kodowanie WinAnsi) — dlatego osadzamy okrojony wariant
 * Droid Sans (licencja Apache 2.0) z zestawem znaków łacińskich i polskich.
 * Plik powstał skryptem opisanym w README i waży ~28 kB.
 */
import { PROTOCOL_FONT_BASE64 } from '../assets/protocolFont';
import fontkit from '@pdf-lib/fontkit';
import { PDFDocument, rgb, type PDFFont } from 'pdf-lib';
import type { Translations } from './i18n';

const MM = 72 / 25.4;
const PAGE_W = 210 * MM;
const PAGE_H = 297 * MM;
const MARGIN = 20 * MM;
const CONTENT_W = PAGE_W - MARGIN * 2;

const BLACK = rgb(0.1, 0.1, 0.1);
const GREY = rgb(0.45, 0.45, 0.45);
const LINE = rgb(0.75, 0.75, 0.75);

/** Kolumny tabeli: szerokości w punktach, reszta przypada na nazwę sprzętu. */
const COL_NO = 12 * MM;
const COL_TAG = 32 * MM;
const COL_SERIAL = 45 * MM;

export type ProtocolPerson = {
  name: string;
  position: string;
  department: string;
  email: string;
};

export type ProtocolAsset = {
  asset_tag: string;
  name: string;
  serial_number: string | null;
};

function decodeFont(base64: string): Uint8Array {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

/** Skraca tekst do szerokości kolumny, dokładając wielokropek. */
function fit(font: PDFFont, text: string, size: number, maxWidth: number): string {
  if (font.widthOfTextAtSize(text, size) <= maxWidth) return text;
  let cut = text;
  while (cut.length > 1 && font.widthOfTextAtSize(cut + '…', size) > maxWidth) {
    cut = cut.slice(0, -1);
  }
  return cut + '…';
}

export async function generateProtocolPdf(
  person: ProtocolPerson,
  assets: ProtocolAsset[],
  t: Translations,
  today: string,
): Promise<Uint8Array> {
  const pdf = await PDFDocument.create();
  pdf.registerFontkit(fontkit);
  pdf.setTitle(`${t.protocol_title} — ${person.name}`);
  pdf.setAuthor('VanillaTracker');

  const fontBytes = decodeFont(PROTOCOL_FONT_BASE64);
  const font = await pdf.embedFont(fontBytes, { subset: true });

  let page = pdf.addPage([PAGE_W, PAGE_H]);
  let y = PAGE_H - MARGIN;

  const write = (text: string, x: number, size: number, color = BLACK) =>
    page.drawText(text, { x, y, size, font, color });

  const newPage = () => {
    page = pdf.addPage([PAGE_W, PAGE_H]);
    y = PAGE_H - MARGIN;
  };

  // ── Nagłówek ──
  write(t.protocol_title, MARGIN, 16);
  y -= 8 * MM;
  write(`${t.protocol_date}: ${today}`, MARGIN, 10, GREY);
  y -= 10 * MM;

  // ── Dane osoby ──
  write(t.protocol_person, MARGIN, 9, GREY);
  y -= 5.5 * MM;
  write(person.name, MARGIN, 13);
  y -= 6 * MM;

  const details = [
    person.position && `${t.protocol_position}: ${person.position}`,
    person.department && `${t.protocol_dept}: ${person.department}`,
    person.email,
  ].filter(Boolean) as string[];

  for (const line of details) {
    write(line, MARGIN, 10, GREY);
    y -= 5 * MM;
  }

  y -= 6 * MM;

  // ── Tabela sprzętu ──
  const colNoX = MARGIN;
  const colTagX = colNoX + COL_NO;
  const colNameX = colTagX + COL_TAG;
  const colSerialX = MARGIN + CONTENT_W - COL_SERIAL;
  const nameWidth = colSerialX - colNameX - 4 * MM;

  const drawTableHeader = () => {
    write(t.protocol_col_no, colNoX, 9, GREY);
    write(t.protocol_col_tag, colTagX, 9, GREY);
    write(t.protocol_col_name, colNameX, 9, GREY);
    write(t.protocol_col_serial, colSerialX, 9, GREY);
    y -= 2.5 * MM;
    page.drawLine({
      start: { x: MARGIN, y },
      end: { x: MARGIN + CONTENT_W, y },
      thickness: 0.7,
      color: LINE,
    });
    y -= 6 * MM;
  };

  if (assets.length === 0) {
    write(t.protocol_no_assets, MARGIN, 11, GREY);
    y -= 10 * MM;
  } else {
    drawTableHeader();

    assets.forEach((asset, index) => {
      // Zostawiamy miejsce na sekcję podpisów u dołu strony.
      if (y < MARGIN + 60 * MM) {
        newPage();
        drawTableHeader();
      }
      write(String(index + 1) + '.', colNoX, 10);
      write(asset.asset_tag, colTagX, 10);
      write(fit(font, asset.name, 10, nameWidth), colNameX, 10);
      write(fit(font, asset.serial_number || '—', 10, COL_SERIAL), colSerialX, 10);
      y -= 3 * MM;
      page.drawLine({
        start: { x: MARGIN, y },
        end: { x: MARGIN + CONTENT_W, y },
        thickness: 0.3,
        color: LINE,
      });
      y -= 5.5 * MM;
    });
  }

  // ── Oświadczenie i podpisy ──
  if (y < MARGIN + 55 * MM) newPage();

  y -= 6 * MM;
  const footerLines = wrap(font, t.protocol_footer, 9.5, CONTENT_W);
  for (const line of footerLines) {
    write(line, MARGIN, 9.5, GREY);
    y -= 5 * MM;
  }

  y -= 18 * MM;
  const signWidth = 60 * MM;
  const rightX = MARGIN + CONTENT_W - signWidth;
  for (const x of [MARGIN, rightX]) {
    page.drawLine({
      start: { x, y },
      end: { x: x + signWidth, y },
      thickness: 0.5,
      color: LINE,
    });
  }
  y -= 5 * MM;
  write(t.protocol_sign_giver, MARGIN, 8.5, GREY);
  write(t.protocol_sign_taker, rightX, 8.5, GREY);

  return pdf.save();
}

/** Łamie akapit na linie mieszczące się w zadanej szerokości. */
function wrap(font: PDFFont, text: string, size: number, maxWidth: number): string[] {
  const words = text.split(' ');
  const lines: string[] = [];
  let line = '';
  for (const word of words) {
    const candidate = line ? `${line} ${word}` : word;
    if (font.widthOfTextAtSize(candidate, size) > maxWidth && line) {
      lines.push(line);
      line = word;
    } else {
      line = candidate;
    }
  }
  if (line) lines.push(line);
  return lines;
}
