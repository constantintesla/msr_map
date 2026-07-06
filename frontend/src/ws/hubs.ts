import { getCommanderWsUrl, getEngineerWsUrl, getWsUrl } from '../api/client';
import { createSocketHub } from './socketHub';

export const adminSocketHub = createSocketHub(getWsUrl);
export const engineerSocketHub = createSocketHub(getEngineerWsUrl);
export const commanderSocketHub = createSocketHub(getCommanderWsUrl);
