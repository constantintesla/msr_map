import { jsPDF } from 'jspdf';
import QRCode from 'qrcode';

export interface Stage2MissionBox {
  id: number;
  name: string;
  lat: number;
  lon: number;
  code: string;
  url: string;
  loot_variant?: string;
}

const FILM_INSTRUCTIONS = [
  '1. Перейди по ссылке в QR',
  '2. Войти в приложение (инженер)',
  '3. Введи полученный код от штаба',
  '4. Подорвать плёнку и отправить видео',
  '5. Забрать ящик и доставить на базу',
  '6. Сфотографировать ящик на базе в приложении и отправь в штаб',
];

const BOX_INSTRUCTIONS = [
  '1. Перейди по ссылке в QR',
  '2. Войти в приложение (инженер)',
  '3. Введи полученный код от штаба',
  '4. Забрать ящик и доставить на базу',
  '5. Сфотографировать ящик на базе в приложении и отправь в штаб',
];

const PAGE_W = 297;
const PAGE_H = 210;
const QR_SIZE = PAGE_H * 0.72;

let regularFontBinary: string | null = null;
let boldFontBinary: string | null = null;

async function loadFontBinary(url: string): Promise<string> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Не удалось загрузить шрифт: ${url}`);
  const bytes = new Uint8Array(await res.arrayBuffer());
  let binary = '';
  const chunk = 8192;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, Math.min(i + chunk, bytes.length)));
  }
  return binary;
}

async function ensureCyrillicFont(doc: jsPDF): Promise<void> {
  const base = `${import.meta.env.BASE_URL}fonts/`;
  if (!regularFontBinary) {
    [regularFontBinary, boldFontBinary] = await Promise.all([
      loadFontBinary(`${base}Roboto-Regular.ttf`),
      loadFontBinary(`${base}Roboto-Bold.ttf`),
    ]);
  }

  doc.addFileToVFS('Roboto-Regular.ttf', regularFontBinary);
  doc.addFont('Roboto-Regular.ttf', 'Roboto', 'normal');
  doc.addFileToVFS('Roboto-Bold.ttf', boldFontBinary!);
  doc.addFont('Roboto-Bold.ttf', 'Roboto', 'bold');
  doc.setFont('Roboto', 'normal');
}

function instructionsFor(box: Stage2MissionBox): string[] {
  return box.loot_variant === 'box_direct' ? BOX_INSTRUCTIONS : FILM_INSTRUCTIONS;
}

async function renderBoxPage(
  doc: jsPDF,
  box: Stage2MissionBox,
  isFirst: boolean,
  instructions?: string[],
) {
  if (!isFirst) {
    doc.addPage('a4', 'landscape');
  }

  const lines = instructions ?? instructionsFor(box);
  const qrDataUrl = await QRCode.toDataURL(box.url, { margin: 1, width: 1024, errorCorrectionLevel: 'M' });
  const qrX = (PAGE_W - QR_SIZE) / 2;
  const qrY = (PAGE_H - QR_SIZE) / 2;

  doc.setFont('Roboto', 'bold');
  doc.setFontSize(22);
  doc.text(box.name, PAGE_W / 2, 18, { align: 'center' });

  doc.addImage(qrDataUrl, 'PNG', qrX, qrY, QR_SIZE, QR_SIZE);

  doc.setFont('Roboto', 'normal');
  doc.setFontSize(10);
  doc.setTextColor(80);
  doc.text('Перейди по ссылке в QR', PAGE_W / 2, qrY + QR_SIZE + 6, { align: 'center' });
  doc.setTextColor(0);

  const textX = 14;
  let textY = PAGE_H - 8 - lines.length * 5.5;
  doc.setFont('Roboto', 'bold');
  doc.setFontSize(12);
  doc.text('Инструкция:', textX, textY);
  textY += 6;
  doc.setFont('Roboto', 'normal');
  doc.setFontSize(10);
  for (const line of lines) {
    doc.text(line, textX, textY);
    textY += 5.5;
  }
}

export async function downloadStage2Pdf(
  boxes: Stage2MissionBox[],
  filename = 'stage2-mission.pdf',
  instructions?: string[],
) {
  if (boxes.length === 0) return;

  const doc = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' });
  await ensureCyrillicFont(doc);

  for (let i = 0; i < boxes.length; i++) {
    await renderBoxPage(doc, boxes[i], i === 0, instructions ?? instructionsFor(boxes[i]));
  }

  doc.save(filename);
}

export async function downloadStage2PdfSingle(box: Stage2MissionBox) {
  const safeName = box.name.replace(/[^\w\u0400-\u04FF-]+/g, '_').slice(0, 40);
  await downloadStage2Pdf([box], `stage2-${safeName || box.id}.pdf`);
}
