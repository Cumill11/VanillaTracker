/**
 * Etykiety PDF 35×25 mm - port `label_pdf.py` (reportlab + qrcode) na pdf-lib.
 *
 * Układ bez zmian: [ kod QR 20×20 mm ] | separator | [ tag obrócony o +90° ].
 * QR rysujemy wektorowo (prostokąty), a nie jako PNG - mniejszy plik i ostry
 * wydruk w każdej rozdzielczości.
 */
import { PDFDocument, StandardFonts, degrees, rgb, type PDFFont, type PDFPage } from 'pdf-lib';
// Sam koder QR, bez rendererów canvas/SVG - te sięgają po DOM, którego
// w Workers nie ma.
import QR from 'qrcode/lib/core/qrcode.js';

const MM = 72 / 25.4;

const PAGE_W = 35 * MM;
const PAGE_H = 25 * MM;

const QR_SIZE = 20 * MM;
const QR_X = 1.0 * MM + 2.5 * MM; // 1 mm marginesu + 2,5 mm przesunięcia w prawo
const QR_Y = (PAGE_H - QR_SIZE) / 2; // wyśrodkowanie w pionie

const SEPARATOR_X = QR_X + QR_SIZE + 0.8 * MM;
const STRIP_LEFT = SEPARATOR_X + 1.0 * MM;
const STRIP_RIGHT = PAGE_W - QR_X; // prawy margines równy lewemu
const STRIP_W = STRIP_RIGHT - STRIP_LEFT;

const QR_BORDER_MODULES = 1;

function qrMatrix(text: string): { size: number; data: Uint8Array } {
  return QR.create(text, { errorCorrectionLevel: 'M' }).modules;
}

/**
 * Dobiera największy rozmiar czcionki mieszczący tag w pasku po prawej -
 * odpowiednik `_max_font_size`. `maxLen` ogranicza długość napisu (wzdłuż
 * wysokości strony), `maxAsc` jego wysokość (wzdłuż szerokości paska).
 */
function maxFontSize(
  font: PDFFont,
  text: string,
  maxLen: number,
  maxAsc: number,
  start = 16.0,
): number {
  for (let size = start; size >= 5; size -= 0.25) {
    const width = font.widthOfTextAtSize(text, size);
    const ascent = size * 0.72;
    if (width <= maxLen && ascent <= maxAsc) return size;
  }
  return 5.0;
}

function drawQr(page: PDFPage, text: string): void {
  const { size, data } = qrMatrix(text);
  const total = size + QR_BORDER_MODULES * 2;
  const cell = QR_SIZE / total;

  // Biała podkładka - quiet zone musi być jasna, żeby czytnik złapał kod.
  page.drawRectangle({
    x: QR_X,
    y: QR_Y,
    width: QR_SIZE,
    height: QR_SIZE,
    color: rgb(1, 1, 1),
  });

  const black = rgb(0, 0, 0);
  for (let row = 0; row < size; row++) {
    let runStart = -1;
    // Ciągi sąsiadujących modułów rysujemy jednym prostokątem - bez tego
    // między nimi potrafią prześwitywać włosowe szczeliny.
    for (let col = 0; col <= size; col++) {
      const dark = col < size && data[row * size + col] === 1;
      if (dark && runStart === -1) runStart = col;
      if (!dark && runStart !== -1) {
        page.drawRectangle({
          x: QR_X + (runStart + QR_BORDER_MODULES) * cell,
          y: QR_Y + QR_SIZE - (row + QR_BORDER_MODULES + 1) * cell,
          width: (col - runStart) * cell,
          height: cell,
          color: black,
        });
        runStart = -1;
      }
    }
  }
}

function drawLabel(page: PDFPage, font: PDFFont, assetTag: string, assetUrl: string): void {
  drawQr(page, assetUrl);

  page.drawLine({
    start: { x: SEPARATOR_X, y: 1.0 * MM },
    end: { x: SEPARATOR_X, y: PAGE_H - 1.0 * MM },
    thickness: 0.4,
    color: rgb(0.7, 0.7, 0.7),
  });

  const fontSize = maxFontSize(font, assetTag, PAGE_H - 2.5 * MM, STRIP_W - 0.5 * MM);
  const textWidth = font.widthOfTextAtSize(assetTag, fontSize);

  // Obrót o 90° wokół punktu (x, y): napis biegnie w górę strony, a wyśrodkowanie
  // uzyskujemy cofając początek o połowę jego długości.
  page.drawText(assetTag, {
    x: STRIP_RIGHT - 0.6 * MM,
    y: PAGE_H / 2 - textWidth / 2,
    size: fontSize,
    font,
    rotate: degrees(90),
    color: rgb(0.05, 0.05, 0.05),
  });
}

type LabelAsset = { id: number; asset_tag: string };

export async function generateLabelsPdf(
  assets: LabelAsset[],
  baseUrl: string,
): Promise<Uint8Array> {
  const pdf = await PDFDocument.create();
  pdf.setTitle('VanillaTracker - Etykiety');
  pdf.setAuthor('VanillaTracker');

  const font = await pdf.embedFont(StandardFonts.HelveticaBold);

  for (const asset of assets) {
    const page = pdf.addPage([PAGE_W, PAGE_H]);
    drawLabel(page, font, asset.asset_tag, `${baseUrl}/assets/${asset.id}/`);
  }

  return pdf.save();
}

export function pdfResponse(bytes: Uint8Array, filename: string): Response {
  return new Response(bytes as unknown as BodyInit, {
    headers: {
      'content-type': 'application/pdf',
      'content-disposition': `inline; filename="${filename}"`,
      'cache-control': 'no-store',
    },
  });
}
