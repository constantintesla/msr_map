import { downloadStage2Pdf, type Stage2MissionBox } from './stage2Pdf';

export type { Stage2MissionBox as Stage1MissionBox };

const STAGE1_INSTRUCTIONS = [
  '0. Только инженеры',
  '1. Перейди по ссылке в QR',
  '2. Войти в приложение (логин и пароль)',
  '3. Введи полученный код от штаба',
  '4. Каждые 2 мин подтверждать удержание',
  '5. Не отходить далее 10 м от таблички',
];

export async function downloadStage1Pdf(boxes: Stage2MissionBox[], filename = 'stage1-kt-mission.pdf') {
  return downloadStage2Pdf(boxes, filename, STAGE1_INSTRUCTIONS);
}

export async function downloadStage1PdfSingle(box: Stage2MissionBox) {
  const safeName = box.name.replace(/[^\w\u0400-\u04FF-]+/g, '_').slice(0, 40);
  return downloadStage1Pdf([box], `stage1-kt-${safeName || box.id}.pdf`);
}
