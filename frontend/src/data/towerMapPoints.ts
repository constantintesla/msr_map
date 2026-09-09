// Точки карты Башни по сторонам — из Башня.kml / СБГ.kml / ДРГ.kml /
// Првонек.kml / Корбул.kml (координаты идентичны для всех экспортов файлов,
// см. backend/app/tower/seed.py — единый источник истины для сидинга).

export interface TowerMapPoint {
  name: string;
  lat: number;
  lon: number;
}

const O_MARKERS: TowerMapPoint[] = [
  { name: 'О1', lat: 44.221972, lon: 131.700395 },
  { name: 'О2', lat: 44.222368, lon: 131.699322 },
  { name: 'О3', lat: 44.222729, lon: 131.698378 },
  { name: 'О4', lat: 44.223122, lon: 131.697391 },
  { name: 'О5', lat: 44.223460, lon: 131.696463 },
  { name: 'О6', lat: 44.223960, lon: 131.695250 },
  { name: 'О7', lat: 44.224332, lon: 131.694247 },
  { name: 'О8', lat: 44.224717, lon: 131.693212 },
  { name: 'О9', lat: 44.225059, lon: 131.692305 },
  { name: 'О10', lat: 44.225470, lon: 131.691313 },
  { name: 'О11', lat: 44.225847, lon: 131.690267 },
  { name: 'О12', lat: 44.226243, lon: 131.689274 },
];

const CAMP: TowerMapPoint[] = [
  { name: 'Лагерь СБГ', lat: 44.229672, lon: 131.690154 },
  { name: 'Парковка', lat: 44.228373, lon: 131.685959 },
];

const MINES: TowerMapPoint[] = [
  { name: 'Шахта 1', lat: 44.225643, lon: 131.695620 },
  { name: 'Шахта 2', lat: 44.224725, lon: 131.696447 },
  { name: 'Шахта 3', lat: 44.223756, lon: 131.697283 },
];

const KPP: TowerMapPoint[] = [
  { name: 'КПП1-1', lat: 44.226189, lon: 131.692472 },
  { name: 'КПП1-2', lat: 44.226589, lon: 131.693909 },
  { name: 'КПП1-3', lat: 44.225666, lon: 131.694328 },
  { name: 'КПП2-1', lat: 44.225293, lon: 131.696216 },
  { name: 'КПП2-2', lat: 44.226143, lon: 131.697133 },
  { name: 'КПП2-3', lat: 44.225290, lon: 131.698346 },
  { name: 'КПП3-1', lat: 44.224098, lon: 131.696640 },
  { name: 'КПП3-2', lat: 44.224755, lon: 131.697637 },
  { name: 'КПП3-3', lat: 44.224129, lon: 131.698249 },
  { name: 'КПП4-1', lat: 44.222841, lon: 131.698903 },
  { name: 'КПП4-2', lat: 44.221676, lon: 131.699461 },
  { name: 'КПП4-3', lat: 44.221230, lon: 131.698367 },
];

const G_POINTS: TowerMapPoint[] = [
  { name: 'Г1', lat: 44.227431, lon: 131.690288 },
  { name: 'Г2', lat: 44.222699, lon: 131.695197 },
  { name: 'Г3', lat: 44.219500, lon: 131.700228 },
];

const VILLAGE_PRVONEK: TowerMapPoint = { name: 'Деревня Првонек', lat: 44.226893, lon: 131.695014 };
const VILLAGE_KORBUL: TowerMapPoint = { name: 'Деревня Корбул', lat: 44.224225, lon: 131.699268 };

const D1: TowerMapPoint[] = [
  { name: 'Д1-1', lat: 44.227327, lon: 131.693727 },
  { name: 'Д1-2', lat: 44.228319, lon: 131.694381 },
  { name: 'Д1-3', lat: 44.229026, lon: 131.697321 },
];
const D2: TowerMapPoint[] = [
  { name: 'Д2-1', lat: 44.225121, lon: 131.699606 },
  { name: 'Д2-2', lat: 44.224728, lon: 131.701591 },
  { name: 'Д2-3', lat: 44.223521, lon: 131.702814 },
];

const M1: TowerMapPoint = { name: 'М1', lat: 44.228111, lon: 131.695915 };
const M2: TowerMapPoint = { name: 'М2', lat: 44.223936, lon: 131.701076 };

const START_POINT: TowerMapPoint = { name: 'Точка старта', lat: 44.227588, lon: 131.698287 };

// Башня.kml — полный набор, для админки
export const TOWER_MAP_ADMIN: TowerMapPoint[] = [
  ...O_MARKERS,
  ...CAMP,
  VILLAGE_PRVONEK,
  ...MINES,
  VILLAGE_KORBUL,
  ...D1,
  M1,
  ...D2,
  M2,
  ...KPP,
  ...G_POINTS,
];

// СБГ.kml
const TOWER_MAP_SBG: TowerMapPoint[] = [...O_MARKERS, ...CAMP, ...MINES, ...KPP, ...G_POINTS];

// ДРГ.kml — без Г2/Г3, плюс точка старта
const TOWER_MAP_DRG: TowerMapPoint[] = [
  ...O_MARKERS,
  ...CAMP,
  ...MINES,
  ...KPP,
  { name: 'Г1', lat: 44.227431, lon: 131.690288 },
  START_POINT,
];

// Првонек.kml — свои схроны, оба села видны для ориентира
const TOWER_MAP_PRVONEK: TowerMapPoint[] = [...CAMP, VILLAGE_PRVONEK, ...MINES, VILLAGE_KORBUL, ...D1, M1];

// Корбул.kml
const TOWER_MAP_KORBUL: TowerMapPoint[] = [...CAMP, VILLAGE_PRVONEK, ...MINES, VILLAGE_KORBUL, ...D2, M2];

export const TOWER_MAP_BY_FACTION: Record<string, TowerMapPoint[]> = {
  admin: TOWER_MAP_ADMIN,
  sbg: TOWER_MAP_SBG,
  drg: TOWER_MAP_DRG,
  prvonek: TOWER_MAP_PRVONEK,
  korbul: TOWER_MAP_KORBUL,
};

export const TOWER_MAP_CENTER: [number, number] = [44.2245, 131.6955];
