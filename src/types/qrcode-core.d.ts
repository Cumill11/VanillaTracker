/**
 * Typy dla `qrcode/lib/core/qrcode.js` — pakiet `qrcode` nie dostarcza własnych,
 * a sięgamy po sam koder z pominięciem rendererów canvas/SVG (te wymagają DOM).
 */
declare module 'qrcode/lib/core/qrcode.js' {
  export type QrErrorCorrectionLevel = 'L' | 'M' | 'Q' | 'H';

  export type QrCode = {
    /** Macierz modułów: `data[row * size + col]`, 1 = ciemny moduł. */
    modules: { size: number; data: Uint8Array };
    version: number;
    maskPattern: number;
  };

  export function create(
    data: string,
    options?: { errorCorrectionLevel?: QrErrorCorrectionLevel; version?: number },
  ): QrCode;

  const qrcode: { create: typeof create };
  export default qrcode;
}
