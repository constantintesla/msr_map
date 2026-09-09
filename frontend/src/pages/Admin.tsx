import { useCallback, useEffect, useRef, useState } from 'react';
import {
  adminAction,
  wipeAllMapObjects,
  adminConfirmCache,
  adminConfirmDelivery,
  adminConfirmPoint,
  exportLogs,
  exportEngineers,
  fetchEngineerLocations,
  fetchGameSettings,
  fetchStage1Mission,
  fetchStage2Assignments,
  fetchStage2Mission,
  fetchStage3Mertvyaki,
  fetchAdminStatus,
  issueStage2Target,
  enableStage2,
  startStage1Slot,
  updateMertvyak,
  updateStage1Code,
  updateStage2Code,
  updateStage2Mission,
  updateGameSettings,
  calibrateGps,
  uploadKmz,
  updateMapPoint,
  createMapPoint,
  deleteMapPoint,
  updateMapCache,
  createMapCache,
  deleteMapCache,
  updateMapLandmark,
  createMapLandmark,
  deleteMapLandmark,
  fetchScenarios,
  createScenario,
  activateScenario,
  archiveScenario,
  type StatusData,
  type EngineerLocation,
  type GameSettings,
  type Stage2Assignment,
  type Scenario,
} from '../api/client';
import ChatPanel from '../components/ChatPanel';
import FieldOrdersPanel from '../components/FieldOrdersPanel';
import LogoutButton from '../components/LogoutButton';
import AdminToolbar from '../components/admin/AdminToolbar';
import AdminSettingsPanel from '../components/admin/AdminSettingsPanel';
import AdminMapEditorBar from '../components/admin/AdminMapEditorBar';
import AdminPanelShell from '../components/admin/AdminPanelShell';
import AdminQuickNav from '../components/admin/AdminQuickNav';
import AdminTracksPanel from '../components/admin/AdminTracksPanel';
import ScenarioSwitcher from '../components/admin/ScenarioSwitcher';
import TowerAdminPanel from '../components/admin/TowerAdminPanel';
import MobileSheet from '../components/MobileSheet';
import { useIsNarrow } from '../hooks/useMediaQuery';
import { adminSocketHub } from '../ws/hubs';
import GameMap, { type MapCreateTarget } from '../components/GameMap';
import AdminMapPopup from '../components/AdminMapPopup';
import QRPrint from '../components/QRPrint';
import { downloadStage1Pdf, downloadStage1PdfSingle } from '../utils/stage1Pdf';
import { downloadStage2Pdf, downloadStage2PdfSingle } from '../utils/stage2Pdf';
import 'leaflet/dist/leaflet.css';

interface MissionBox {
  id: number;
  name: string;
  lat: number;
  lon: number;
  code: string;
  url: string;
  enabled?: boolean;
}

interface WsPacket {
  e: string;
  p_id?: number;
  t?: string;
}

export default function AdminPage() {
  const isNarrow = useIsNarrow();
  const [data, setData] = useState<StatusData | null>(null);
  const [pulsePointId, setPulsePointId] = useState<number | null>(null);
  const [warnPointId, setWarnPointId] = useState<number | null>(null);
  const [explosionCacheId, setExplosionCacheId] = useState<number | null>(null);
  const [flyTo, setFlyTo] = useState<[number, number] | null>(null);
  const [missionOpen, setMissionOpen] = useState(false);
  const [lootPanelOpen, setLootPanelOpen] = useState(false);
  const [mission, setMission] = useState<MissionBox[]>([]);
  const [selectedMissionId, setSelectedMissionId] = useState<number | null>(null);
  const [mapSelection, setMapSelection] = useState<{ kind: 'point' | 'cache' | 'landmark'; id: number } | null>(null);
  const [mapEditMode, setMapEditMode] = useState(false);
  const [createTarget, setCreateTarget] = useState<MapCreateTarget | null>(null);
  const [editName, setEditName] = useState('');
  const [nameSaving, setNameSaving] = useState(false);
  const [landmarkCreateKind, setLandmarkCreateKind] = useState<'base' | 'start' | 'base_start'>('base');
  const [landmarkCreateSide, setLandmarkCreateSide] = useState<'A' | 'B'>('A');
  const [mertvyakCreateSide, setMertvyakCreateSide] = useState<'A' | 'B'>('A');
  const [editCode, setEditCode] = useState('');
  const [codeSaving, setCodeSaving] = useState(false);
  const [error, setError] = useState('');
  const [chatOpen, setChatOpen] = useState(
    () => typeof window !== 'undefined' && !window.matchMedia('(max-width: 767px)').matches,
  );
  const [tracksOpen, setTracksOpen] = useState(false);
  const [chatSide, setChatSide] = useState<'A' | 'B'>('A');
  const [chatThread, setChatThread] = useState<'cmd' | 'eng'>('cmd');
  const [chatRefresh, setChatRefresh] = useState(0);
  const [ordersRefresh, setOrdersRefresh] = useState(0);
  const [engineers, setEngineers] = useState<EngineerLocation[]>([]);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settings, setSettings] = useState<GameSettings | null>(null);
  const [settingsDraft, setSettingsDraft] = useState({
    a: 5,
    b: 5,
    captureRadius: 10,
    disableCaptureDistance: false,
    stage1Recapturable: true,
    captureMinutes: 2,
    holdPingMinutes: 2,
    postHoldMinutes: 10,
    postHoldPingMinutes: 2,
    stage2IssueMinutes: 60,
    stage2IssueMode: 'random' as 'random' | 'sequential',
    stage1SlotMinutes: 120,
    stage1HoldSlots: '2,3,6,8,10\n4,5,9,11,12\n1,3,6,7,10',
    gpsAccuracyBonusMax: 20,
    gpsMinAccuracyForCapture: 0,
    gpsLatOffset: 0,
    gpsLonOffset: 0,
    calibrateTrueLat: '',
    calibrateTrueLon: '',
    calibrateMeasuredLat: '',
    calibrateMeasuredLon: '',
  });
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [scenariosOpen, setScenariosOpen] = useState(false);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [scenariosLoading, setScenariosLoading] = useState(false);
  const [scenariosError, setScenariosError] = useState('');
  const [stage2Assignments, setStage2Assignments] = useState<Stage2Assignment[]>([]);
  const [stage2IssueLoading, setStage2IssueLoading] = useState(false);
  const [actionMsg, setActionMsg] = useState('');
  const popupSwitchRef = useRef(false);

  const gameStatusLabel = (status: string) => {
    if (status === 'running') return { text: 'Идёт', className: 'text-green-400' };
    if (status === 'paused') return { text: 'Пауза', className: 'text-warning' };
    return { text: 'Ожидание старта', className: 'text-zinc-400' };
  };

  const runAdminAction = async (path: string) => {
    setActionMsg('');
    try {
      const res = await adminAction(path);
      setActionMsg(res.message);
      setError('');
      await load();
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Ошибка действия';
      setError(msg);
      setActionMsg('');
    }
  };

  const loadSettings = useCallback(() => {
    fetchGameSettings()
      .then((s) => {
        setSettings(s);
        setSettingsDraft((d) => ({
          ...d,
          a: s.engineers_per_side_a,
          b: s.engineers_per_side_b,
          captureRadius: s.capture_radius_m,
          disableCaptureDistance: s.disable_capture_distance,
          stage1Recapturable: s.stage1_recapturable ?? true,
          captureMinutes: Math.round(s.point_capture_seconds / 60),
          holdPingMinutes: Math.round(s.point_hold_ping_seconds / 60),
          postHoldMinutes: Math.round(s.post_hold_seconds / 60),
          postHoldPingMinutes: Math.round(s.post_hold_ping_seconds / 60),
          stage2IssueMinutes: s.stage2_issue_interval_minutes,
          stage2IssueMode: s.stage2_issue_mode === 'sequential' ? 'sequential' : 'random',
          stage1SlotMinutes: s.stage1_slot_minutes ?? 120,
          stage1HoldSlots: (s.stage1_hold_slots || [[2, 3, 6, 8, 10], [4, 5, 9, 11, 12], [1, 3, 6, 7, 10]])
            .map((slot) => slot.join(','))
            .join('\n'),
          gpsAccuracyBonusMax: s.gps_accuracy_bonus_max_m ?? 20,
          gpsMinAccuracyForCapture: s.gps_min_accuracy_for_capture_m ?? 0,
          gpsLatOffset: s.gps_lat_offset ?? 0,
          gpsLonOffset: s.gps_lon_offset ?? 0,
        }));
      })
      .catch(() => {});
  }, []);

  const loadEngineers = useCallback(() => {
    fetchEngineerLocations()
      .then(setEngineers)
      .catch(() => {});
  }, []);

  const loadStage2Assignments = useCallback(() => {
    fetchStage2Assignments()
      .then(setStage2Assignments)
      .catch(() => {});
  }, []);

  const loadScenarios = useCallback(() => {
    setScenariosLoading(true);
    fetchScenarios()
      .then((list) => {
        setScenarios(list);
        setScenariosError('');
      })
      .catch((e) => setScenariosError(e instanceof Error ? e.message : 'Ошибка загрузки сценариев'))
      .finally(() => setScenariosLoading(false));
  }, []);

  const load = useCallback(() => {
    return fetchAdminStatus()
      .then((d) => {
        setData(d);
        setError('');
      })
      .catch(() => setError('Нет связи с API'));
  }, []);

  const loadRef = useRef(load);
  loadRef.current = load;
  const loadEngineersRef = useRef(loadEngineers);
  loadEngineersRef.current = loadEngineers;
  const loadStage2AssignmentsRef = useRef(loadStage2Assignments);
  loadStage2AssignmentsRef.current = loadStage2Assignments;
  const loadSettingsRef = useRef(loadSettings);
  loadSettingsRef.current = loadSettings;
  const loadScenariosRef = useRef(loadScenarios);
  loadScenariosRef.current = loadScenarios;

  useEffect(() => {
    load();
    loadEngineers();
    loadSettings();
    loadScenarios();
    const id = setInterval(() => {
      load();
      loadEngineers();
    }, 5000);
    return () => clearInterval(id);
  }, [load, loadEngineers, loadSettings, loadScenarios]);

  useEffect(() => {
    if (data?.current_stage !== 1 && data?.current_stage !== 2 && data?.current_stage !== 3) {
      setMissionOpen(false);
      setLootPanelOpen(false);
      setMission([]);
    }
    if (data?.stage2_enabled || data?.current_stage === 2 || lootPanelOpen) {
      loadStage2Assignments();
    }
  }, [data?.current_stage, data?.stage2_enabled, lootPanelOpen, loadStage2Assignments]);

  // WebSocket: shared hub — one connection, StrictMode-safe teardown
  useEffect(() => {
    return adminSocketHub.subscribe((packet) => {
        if (packet.e === 'ping' && packet.p_id) {
        setPulsePointId(packet.p_id as number);
          setTimeout(() => setPulsePointId(null), 1500);
        }
      if (packet.e === 'hold_leave' && packet.p_id) {
        setWarnPointId(packet.p_id as number);
        setTimeout(() => setWarnPointId(null), 5000);
      }
      if (packet.e === 'cache_detonate' && packet.p_id) {
        setExplosionCacheId(packet.p_id as number);
        setTimeout(() => setExplosionCacheId(null), 1500);
      }
      if (packet.e === 'scenario_switched') {
        loadRef.current();
        loadSettingsRef.current();
        loadEngineersRef.current();
        loadScenariosRef.current();
        setMapSelection(null);
        setMission([]);
        setMissionOpen(false);
        setLootPanelOpen(false);
      }
      if (
        packet.e === 'hold_expired' ||
        packet.e === 'cache_detonate' ||
        packet.e === 'hold_start' ||
        packet.e === 'hold_ping' ||
        packet.e === 'point_capture' ||
        packet.e === 'point_hold_ready' ||
        packet.e === 'hold_leave' ||
        packet.e === 'stage_change' ||
        packet.e === 'point_confirmed' ||
        packet.e === 'chat' ||
        packet.e === 'location' ||
        packet.e === 'field_order_update' ||
        packet.e === 'stage2_issued' ||
        packet.e === 'game_state' ||
        packet.e === 'settings_update' ||
        packet.e === 'map_update'
      ) {
        loadRef.current();
        if (packet.e === 'chat') setChatRefresh((n) => n + 1);
        if (packet.e === 'location') loadEngineersRef.current();
        if (packet.e === 'field_order_update') setOrdersRefresh((n) => n + 1);
        if (packet.e === 'stage2_issued') loadStage2AssignmentsRef.current();
      }
    });
  }, []);

  useEffect(() => {
    if (data?.game_status !== 'idle') {
      setMapEditMode(false);
      setCreateTarget(null);
    }
  }, [data?.game_status]);

  const handleObjectMove = async (
    kind: 'point' | 'cache' | 'landmark',
    id: number,
    lat: number,
    lon: number
  ) => {
    try {
      if (kind === 'point') await updateMapPoint(id, { lat, lon });
      else if (kind === 'cache') await updateMapCache(id, { lat, lon });
      else await updateMapLandmark(id, { lat, lon });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ошибка перемещения');
      await load();
    }
  };

  const handleMapClickCreate = async (lat: number, lon: number) => {
    if (!createTarget) return;
    try {
      if (createTarget.kind === 'point') {
        await createMapPoint({ lat, lon, stage: createTarget.stage });
        if (createTarget.stage === 1) {
          setActionMsg('КТ создана. Обновите слоты захвата в настройках этапа 1 при необходимости.');
        }
      } else if (createTarget.kind === 'cache') {
        await createMapCache({
          lat,
          lon,
          stage: createTarget.stage,
          cache_kind: createTarget.cache_kind,
          team_side: createTarget.team_side,
        });
      } else {
        await createMapLandmark({
          lat,
          lon,
          kind: createTarget.landmarkKind,
          team_side: createTarget.team_side,
        });
      }
      setCreateTarget(null);
      setError('');
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ошибка создания объекта');
    }
  };

  const handleSaveObjectName = async () => {
    if (!mapSelection) return;
    setNameSaving(true);
    try {
      if (mapSelection.kind === 'point') {
        await updateMapPoint(mapSelection.id, { name: editName });
      } else if (mapSelection.kind === 'cache') {
        await updateMapCache(mapSelection.id, { name: editName });
      } else {
        await updateMapLandmark(mapSelection.id, { name: editName });
      }
      await load();
      setError('');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ошибка сохранения имени');
    } finally {
      setNameSaving(false);
    }
  };

  const handleDeleteSelectedObject = async () => {
    if (!mapSelection) return;
    const label =
      mapSelection.kind === 'point' ? 'точку' : mapSelection.kind === 'cache' ? 'схрон' : 'ориентир';
    if (!window.confirm(`Удалить ${label}?`)) return;
    try {
      if (mapSelection.kind === 'point') await deleteMapPoint(mapSelection.id);
      else if (mapSelection.kind === 'cache') await deleteMapCache(mapSelection.id);
      else await deleteMapLandmark(mapSelection.id);
      setMapSelection(null);
      await load();
      setError('');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ошибка удаления');
    }
  };

  const mapEditPopupProps = mapEditMode
    ? {
        mapEditMode: true,
        editName,
        onEditName: setEditName,
        onSaveName: () => void handleSaveObjectName(),
        nameSaving,
        onDelete: () => void handleDeleteSelectedObject(),
      }
    : {};

  const focusObject = (lat: number, lon: number) => {
    setFlyTo([lat, lon]);
  };

  const beginPopupSwitch = () => {
    popupSwitchRef.current = true;
    window.setTimeout(() => {
      popupSwitchRef.current = false;
    }, 250);
  };

  const selectLandmark = (lm: NonNullable<StatusData['landmarks']>[number]) => {
    beginPopupSwitch();
    setMapSelection({ kind: 'landmark', id: lm.id });
    focusObject(lm.lat, lm.lon);
    if (mapEditMode) setEditName(lm.name);
  };

  const selectPoint = (p: NonNullable<StatusData['points']>[number]) => {
    beginPopupSwitch();
    setMapSelection({ kind: 'point', id: p.id });
    focusObject(p.lat, p.lon);
    if (mapEditMode) setEditName(p.name);
    const m = mission.find((x) => x.id === p.id);
    if (m) {
      setSelectedMissionId(m.id);
      setEditCode(m.code);
      return;
    }
    if (data?.current_stage === 1) {
      fetchStage1Mission()
        .then((ms) => {
          setMission(ms);
          setMissionOpen(true);
          const found = ms.find((x) => x.id === p.id);
          if (found) {
            setSelectedMissionId(found.id);
            setEditCode(found.code);
          }
        })
        .catch(() => {});
    }
  };

  const selectCache = (c: NonNullable<StatusData['caches']>[number]) => {
    beginPopupSwitch();
    setMapSelection({ kind: 'cache', id: c.id });
    focusObject(c.lat, c.lon);
    if (mapEditMode) setEditName(c.name);
    const m = mission.find((x) => x.id === c.id);
    if (m) {
      setSelectedMissionId(m.id);
      setEditCode(m.code);
      return;
    }
    if ((data?.stage2_enabled || data?.current_stage === 2 || lootPanelOpen) && c.cache_kind === 'film_loot') {
      fetchStage2Mission()
        .then((ms) => {
          setMission(ms);
          setMissionOpen(true);
          const found = ms.find((x) => x.id === c.id);
          if (found) {
            setSelectedMissionId(found.id);
            setEditCode(found.code);
          }
        })
        .catch(() => {});
    }
    if (data?.current_stage === 3 && c.cache_kind === 'mertvyak') {
      fetchStage3Mertvyaki()
        .then((ms) => {
          setMission(ms);
          setMissionOpen(true);
          const found = ms.find((x) => x.id === c.id);
          if (found) {
            setSelectedMissionId(found.id);
            setEditCode(found.code);
          }
        })
        .catch(() => {});
    }
  };

  const loadMission = () => {
    const stage = data?.current_stage;
    if (stage === 1) {
      return fetchStage1Mission()
        .then((m) => {
          setMission(m);
          setMissionOpen(true);
          if (m.length > 0 && selectedMissionId === null) {
            setSelectedMissionId(m[0].id);
            setEditCode(m[0].code);
          }
        })
        .catch(() => {});
    }
    if (stage === 2) {
      return fetchStage2Mission()
        .then((m) => {
          setMission(m);
          setMissionOpen(true);
          if (m.length > 0 && selectedMissionId === null) {
            setSelectedMissionId(m[0].id);
            setEditCode(m[0].code);
          }
        })
        .catch(() => {});
    }
    if (stage === 3) {
      return fetchStage3Mertvyaki()
        .then((m) => {
          setMission(m);
          setMissionOpen(true);
          if (m.length > 0 && selectedMissionId === null) {
            setSelectedMissionId(m[0].id);
            setEditCode(m[0].code);
          }
        })
        .catch(() => {});
    }
    return Promise.resolve();
  };

  const toggleSettings = () => {
    if (settingsOpen) {
      setSettingsOpen(false);
      return;
    }
    setMissionOpen(false);
    setLootPanelOpen(false);
    setScenariosOpen(false);
    setSettingsOpen(true);
  };

  const toggleScenarios = () => {
    if (scenariosOpen) {
      setScenariosOpen(false);
      return;
    }
    setMissionOpen(false);
    setLootPanelOpen(false);
    setSettingsOpen(false);
    setScenariosOpen(true);
    loadScenarios();
  };

  const handleCreateScenario = async (name: string) => {
    try {
      await createScenario(name);
      setScenariosError('');
      loadScenarios();
    } catch (e) {
      setScenariosError(e instanceof Error ? e.message : 'Не удалось создать сценарий');
    }
  };

  const handleActivateScenario = async (id: number) => {
    if (
      !window.confirm(
        'Переключить активный сценарий? Текущие приказы и позиции инженеров на карте будут сброшены.',
      )
    ) {
      return;
    }
    try {
      await activateScenario(id);
      setScenariosError('');
      loadScenarios();
      await load();
      loadSettings();
      loadEngineers();
    } catch (e) {
      setScenariosError(e instanceof Error ? e.message : 'Не удалось переключить сценарий');
    }
  };

  const handleArchiveScenario = async (id: number) => {
    if (!window.confirm('Архивировать сценарий?')) return;
    try {
      await archiveScenario(id);
      setScenariosError('');
      loadScenarios();
    } catch (e) {
      setScenariosError(e instanceof Error ? e.message : 'Не удалось архивировать сценарий');
    }
  };

  const toggleLootPanel = () => {
    if (lootPanelOpen) {
      setLootPanelOpen(false);
      return;
    }
    setSettingsOpen(false);
    setMissionOpen(false);
    setScenariosOpen(false);
    fetchStage2Mission()
      .then((m) => {
        setMission(m);
        setLootPanelOpen(true);
        if (m.length > 0 && selectedMissionId === null) {
          setSelectedMissionId(m[0].id);
          setEditCode(m[0].code);
        }
      })
      .catch(() => {});
  };

  const toggleMissionPanel = () => {
    if (missionOpen) {
      setMissionOpen(false);
      return;
    }
    setSettingsOpen(false);
    setLootPanelOpen(false);
    setScenariosOpen(false);
    if (mission.length > 0) {
      setMissionOpen(true);
      return;
    }
    void loadMission();
  };

  const selectMissionBox = (m: MissionBox) => {
    beginPopupSwitch();
    setSelectedMissionId(m.id);
    setEditCode(m.code);
    if (data?.current_stage === 1 && missionOpen && !lootPanelOpen) {
      setMapSelection({ kind: 'point', id: m.id });
    } else {
      setMapSelection({ kind: 'cache', id: m.id });
    }
    focusObject(m.lat, m.lon);
  };

  const saveMissionCode = async () => {
    const digits = editCode.replace(/\D/g, '');
    if (digits.length < 4 || digits.length > 6) {
      return;
    }
    setCodeSaving(true);
    try {
      if (data?.current_stage === 1 && missionOpen && !lootPanelOpen) {
        const pointId =
          selectedMissionId ?? (mapSelection?.kind === 'point' ? mapSelection.id : null);
        if (pointId === null) return;
        const updated = await updateStage1Code(pointId, digits);
        setMission((prev) => prev.map((m) => (m.id === updated.id ? updated : m)));
        setEditCode(updated.code);
        setSelectedMissionId(updated.id);
      } else if (data?.current_stage === 3 && !lootPanelOpen) {
        const cacheId =
          selectedMissionId ?? (mapSelection?.kind === 'cache' ? mapSelection.id : null);
        if (cacheId === null) return;
        const updated = await updateMertvyak(cacheId, { code: digits });
        setMission((prev) => prev.map((m) => (m.id === updated.id ? updated : m)));
        setEditCode(updated.code);
        setSelectedMissionId(updated.id);
      } else {
        const cacheId =
          selectedMissionId ?? (mapSelection?.kind === 'cache' ? mapSelection.id : null);
        if (cacheId === null) return;
        const updated = await updateStage2Code(cacheId, digits);
        setMission((prev) => prev.map((m) => (m.id === updated.id ? updated : m)));
        setEditCode(updated.code);
        setSelectedMissionId(updated.id);
        }
      } catch {
        // ignore
    } finally {
      setCodeSaving(false);
    }
  };

  const toggleFilmLootEnabled = async (cacheId: number, enabled: boolean) => {
    setCodeSaving(true);
    try {
      const updated = await updateStage2Mission(cacheId, { enabled });
      setMission((prev) => prev.map((m) => (m.id === updated.id ? updated : m)));
      load();
    } catch {
      // ignore
    } finally {
      setCodeSaving(false);
    }
  };

  const toggleMertvyakEnabled = async (cacheId: number, enabled: boolean) => {
    setCodeSaving(true);
    try {
      const updated = await updateMertvyak(cacheId, { enabled });
      setMission((prev) => prev.map((m) => (m.id === updated.id ? updated : m)));
      load();
    } catch {
      // ignore
    } finally {
      setCodeSaving(false);
    }
  };

  const selectedMission = mission.find((m) => m.id === selectedMissionId) ?? null;
  const hasFilmLoot = (data?.caches ?? []).some((c) => c.cache_kind === 'film_loot');

  const handleForceRelease = (pointId: number) => {
    adminAction(`/hold/force-release/${pointId}`).then(() => {
      load();
    });
  };

  const handleAdminConfirmCache = (cacheId: number) => {
    adminConfirmCache(cacheId)
      .then(() => load())
      .catch(() => {});
  };

  const handleAdminConfirmCacheManual = (cacheId: number, side: 'A' | 'B') => {
    adminConfirmCache(cacheId, { side })
      .then(() => load())
      .catch(() => {});
  };

  const handleAdminConfirmDelivery = (cacheId: number) => {
    adminConfirmDelivery(cacheId)
      .then(() => load())
      .catch(() => {});
  };

  const handleAdminConfirmDeliveryManual = (cacheId: number, side: 'A' | 'B') => {
    adminConfirmDelivery(cacheId, { side })
      .then(() => load())
      .catch(() => {});
  };

  const handleAdminConfirmPoint = (pointId: number) => {
    adminConfirmPoint(pointId)
      .then(() => load())
      .catch(() => {});
  };

  const renderAdminPopup = (target: {
    kind: 'point' | 'cache' | 'landmark';
    data:
      | StatusData['points'][number]
      | StatusData['caches'][number]
      | NonNullable<StatusData['landmarks']>[number];
  }) => {
    if (target.kind === 'landmark') {
      const lm = target.data as NonNullable<StatusData['landmarks']>[number];
      return (
        <AdminMapPopup
          landmark={lm}
          currentStage={data?.current_stage ?? 1}
          {...mapEditPopupProps}
        />
      );
    }
    if (target.kind === 'point') {
      const pt = target.data as StatusData['points'][number];
      const m = mission.find((x) => x.id === pt.id) ?? null;
      return (
        <AdminMapPopup
          point={pt}
          currentStage={data?.current_stage ?? 1}
          mission={data?.current_stage === 1 ? m : null}
          editCode={mapSelection?.kind === 'point' && mapSelection.id === pt.id ? editCode : m?.code}
          onEditCode={setEditCode}
          onSaveCode={() => void saveMissionCode()}
          codeSaving={codeSaving}
          onDownloadPdf={
            m && data?.current_stage === 1
              ? () => downloadStage1PdfSingle(m).catch(() => {})
              : undefined
          }
          onForceRelease={data?.current_stage === 1 ? handleForceRelease : undefined}
          onAdminConfirmPoint={handleAdminConfirmPoint}
          stage1Phase={data?.stage1_phase}
          {...mapEditPopupProps}
        />
      );
    }
    const cache = target.data as StatusData['caches'][number];
    const m = mission.find((x) => x.id === cache.id) ?? null;
    return (
      <AdminMapPopup
        cache={cache}
        currentStage={data?.current_stage ?? 1}
        mission={m}
        editCode={mapSelection?.id === cache.id ? editCode : m?.code}
        onEditCode={setEditCode}
        onSaveCode={() => void saveMissionCode()}
        codeSaving={codeSaving}
        onDownloadPdf={
          m
            ? () => downloadStage2PdfSingle(m).catch(() => {})
            : undefined
        }
        onAdminConfirm={handleAdminConfirmCache}
        onAdminConfirmManual={handleAdminConfirmCacheManual}
        onAdminConfirmDelivery={handleAdminConfirmDelivery}
        onAdminConfirmDeliveryManual={handleAdminConfirmDeliveryManual}
        {...mapEditPopupProps}
      />
    );
  };

  const copyMission = () => {
    const text = mission
      .map((m) => `${m.name}\nКоординаты: ${m.lat.toFixed(6)}, ${m.lon.toFixed(6)}\nКод: ${m.code}\nQR: ${m.url}`)
      .join('\n\n---\n\n');
    navigator.clipboard.writeText(text).catch(() => {});
  };

  const parseHoldSlots = (text: string): number[][] =>
    text
      .split('\n')
      .map((line) =>
        line
          .split(/[,;\s]+/)
          .map((x) => parseInt(x.trim(), 10))
          .filter((n) => !Number.isNaN(n) && n >= 1 && n <= 99)
      )
      .filter((slot) => slot.length > 0);

  const saveSettings = async () => {
    const clampInt = (v: number, min: number, max: number, fallback: number) => {
      const n = Math.round(Number.isFinite(v) ? v : fallback);
      if (n < min) return min;
      if (n > max) return max;
      return n;
    };
    setSettingsSaving(true);
    try {
      const s = await updateGameSettings({
        engineers_per_side_a: clampInt(settingsDraft.a, 1, 50, 5),
        engineers_per_side_b: clampInt(settingsDraft.b, 1, 50, 5),
        capture_radius_m: clampInt(settingsDraft.captureRadius, 1, 500, 10),
        disable_capture_distance: settingsDraft.disableCaptureDistance,
        stage1_recapturable: settingsDraft.stage1Recapturable,
        point_capture_seconds: clampInt(settingsDraft.captureMinutes, 1, 60, 2) * 60,
        point_hold_ping_seconds: clampInt(settingsDraft.holdPingMinutes, 1, 60, 2) * 60,
        post_hold_seconds: clampInt(settingsDraft.postHoldMinutes, 1, 120, 10) * 60,
        post_hold_ping_seconds: clampInt(settingsDraft.postHoldPingMinutes, 1, 60, 2) * 60,
        stage2_issue_interval_minutes: clampInt(settingsDraft.stage2IssueMinutes, 1, 1440, 60),
        stage2_issue_mode: settingsDraft.stage2IssueMode,
        stage1_slot_minutes: clampInt(settingsDraft.stage1SlotMinutes, 1, 1440, 120),
        stage1_hold_slots: parseHoldSlots(settingsDraft.stage1HoldSlots),
        gps_accuracy_bonus_max_m: clampInt(settingsDraft.gpsAccuracyBonusMax, 0, 100, 20),
        gps_min_accuracy_for_capture_m: clampInt(settingsDraft.gpsMinAccuracyForCapture, 0, 200, 0),
        gps_lat_offset: Number.isFinite(settingsDraft.gpsLatOffset) ? settingsDraft.gpsLatOffset : 0,
        gps_lon_offset: Number.isFinite(settingsDraft.gpsLonOffset) ? settingsDraft.gpsLonOffset : 0,
      });
      setSettings(s);
      setActionMsg('Настройки применены');
      setError('');
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ошибка настроек');
    } finally {
      setSettingsSaving(false);
    }
  };

  const calibrateGpsFromDraft = async () => {
    const trueLat = parseFloat(settingsDraft.calibrateTrueLat);
    const trueLon = parseFloat(settingsDraft.calibrateTrueLon);
    const measuredLat = parseFloat(settingsDraft.calibrateMeasuredLat);
    const measuredLon = parseFloat(settingsDraft.calibrateMeasuredLon);
    if ([trueLat, trueLon, measuredLat, measuredLon].some((n) => Number.isNaN(n))) {
      setError('Введите все четыре координаты для калибровки');
      return;
    }
    setSettingsSaving(true);
    try {
      const s = await calibrateGps({
        true_lat: trueLat,
        true_lon: trueLon,
        measured_lat: measuredLat,
        measured_lon: measuredLon,
      });
      setSettings(s);
      setSettingsDraft((d) => ({
        ...d,
        gpsLatOffset: s.gps_lat_offset ?? 0,
        gpsLonOffset: s.gps_lon_offset ?? 0,
      }));
      setActionMsg('Смещение GPS записано');
      setError('');
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ошибка калибровки');
    } finally {
      setSettingsSaving(false);
    }
  };

  const handleKmz = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    if (
      !window.confirm(
        'Импортировать KML/KMZ? Все точки, схроны и базы будут заменены, активные захваты/удержания и невыданные приказы будут сброшены.',
      )
    ) {
      return;
    }
    try {
      await uploadKmz(file);
      load();
    } catch {
      // ignore
    }
  };

  if (error && !data) {
    return (
      <div className="min-h-dvh flex flex-col items-center justify-center p-6 gap-4">
        <p className="text-sideB">{error}</p>
        <button type="button" className="btn border border-zinc-600" onClick={() => load()}>
          Повторить
        </button>
      </div>
    );
  }

  if (!data) {
    return <div className="min-h-dvh flex items-center justify-center">Загрузка админки...</div>;
  }

  const activeScenario = scenarios.find((s) => s.is_active);
  const isTowerScenario = activeScenario?.name === 'Башня';

  if (isTowerScenario) {
    return (
      <div className="h-dvh flex flex-col overflow-hidden">
        <div className="flex items-center justify-between p-3 border-b border-zinc-800 bg-zinc-950 shrink-0">
          <h1 className="text-base font-bold text-sideA">Башня — админка</h1>
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="btn text-xs border border-zinc-600 min-h-0 py-1.5"
              onClick={toggleScenarios}
            >
              Сменить сценарий
            </button>
            <LogoutButton />
          </div>
        </div>
        <div className="flex-1 overflow-y-auto">
          <TowerAdminPanel />
        </div>
        <AdminPanelShell
          open={scenariosOpen}
          isNarrow={isNarrow}
          onClose={toggleScenarios}
          title="Мероприятия"
          borderClass="border-sideA/40"
        >
          <ScenarioSwitcher
            scenarios={scenarios}
            loading={scenariosLoading}
            error={scenariosError}
            onCreate={handleCreateScenario}
            onActivate={handleActivateScenario}
            onArchive={handleArchiveScenario}
          />
        </AdminPanelShell>
      </div>
    );
  }

  return (
    <div className="h-dvh flex flex-col overflow-hidden">
      {/* Переключатель этапов */}
      <div className="hidden md:flex shrink-0 gap-1.5 p-1.5 md:gap-2 md:p-2 border-b border-zinc-800 bg-zinc-950 no-print">
        {(data.stages || []).filter((s) => s.stage !== 2).map((s) => (
          <button
            key={s.stage}
            type="button"
            className={`flex-1 min-h-0 max-md:min-h-0 md:min-h-touch rounded-lg px-1.5 md:px-2 py-1.5 md:py-2 text-xs md:text-sm font-bold transition-colors ${
              data.current_stage === s.stage
                ? s.stage === 1
                  ? 'bg-sideA text-white'
                  : s.stage === 3
                    ? 'bg-warning text-black'
                    : 'bg-zinc-200 text-black'
                : 'border border-zinc-700 text-zinc-400'
            }`}
            onClick={() => void runAdminAction(`/game/stage/${s.stage}`)}
          >
            <span className="block truncate">{s.label}</span>
            <span className="hidden md:block text-xs font-normal opacity-80">
              {s.points_count > 0 && `${s.points_count} КТ`}
              {s.points_count > 0 && s.caches_count > 0 && ' · '}
              {s.caches_count > 0 && `${s.caches_count} схр.`}
              {s.points_count === 0 && s.caches_count === 0 && 'нет KML'}
            </span>
          </button>
        ))}
      </div>

      <AdminToolbar
        data={data}
        gameStatus={gameStatusLabel(data.game_status)}
        actionMsg={actionMsg}
        error={error}
        settingsOpen={settingsOpen}
        missionOpen={missionOpen}
        lootPanelOpen={lootPanelOpen}
        chatOpen={chatOpen}
        tracksOpen={tracksOpen}
        scenariosOpen={scenariosOpen}
        hasFilmLoot={hasFilmLoot}
        onStart={() => void runAdminAction('/game/start')}
        onPause={() => void runAdminAction('/game/pause')}
        onStartStage1Slot={() => {
          startStage1Slot()
            .then((res) => {
              setActionMsg(res.message);
              setError('');
              return load();
            })
            .catch((e) => setError(e instanceof Error ? e.message : 'Ошибка'));
        }}
        onReset={() => {
          if (window.confirm('Сбросить игру? Счёт, захваты и выдачи этапа 2 будут обнулены.')) {
            void runAdminAction('/game/reset');
          }
        }}
        onKmlReload={() => {
          if (
            !window.confirm(
              'Перезагрузить пресет KML? Все точки, схроны и базы будут заменены, активные захваты/удержания и невыданные приказы будут сброшены.',
            )
          ) {
            return;
          }
          void adminAction('/kml/reload').then(load);
        }}
        onKmzChange={handleKmz}
        onToggleSettings={toggleSettings}
        onToggleMission={toggleMissionPanel}
        onToggleLoot={toggleLootPanel}
        onExportLogs={() => exportLogs()}
        onToggleChat={() => setChatOpen(!chatOpen)}
        onToggleTracks={() => setTracksOpen((v) => !v)}
        onToggleScenarios={toggleScenarios}
        mapEditMode={mapEditMode}
        gameIdle={data.game_status === 'idle'}
        onToggleMapEdit={() => {
          setMapEditMode((v) => !v);
          setCreateTarget(null);
        }}
        onStageChange={(stage) => void runAdminAction(`/game/stage/${stage}`)}
        onWipeMap={() => {
          if (
            !window.confirm(
              'Удалить ВСЕ точки, схроны и базы с карты? Действие необратимо. Восстановить можно через «KML пресет».',
            )
          ) {
            return;
          }
          void wipeAllMapObjects()
            .then((res) => {
              setActionMsg(res.message);
              setError('');
              setMapSelection(null);
              setCreateTarget(null);
              return load();
            })
            .catch((e) => setError(e instanceof Error ? e.message : 'Ошибка удаления'));
        }}
      />

      {settingsOpen && (
        isNarrow ? (
          <MobileSheet open onClose={toggleSettings} title="Настройки игры">
            <AdminSettingsPanel
              embedded="sheet"
              data={data}
              settings={settings}
              settingsDraft={settingsDraft}
              settingsSaving={settingsSaving}
              hasFilmLoot={hasFilmLoot}
              onDraftChange={setSettingsDraft}
              onSave={() => void saveSettings()}
              onGpsCalibrate={() => calibrateGpsFromDraft()}
              onDownloadEngineers={() => exportEngineers().catch((e) => setError(e instanceof Error ? e.message : 'Ошибка экспорта'))}
            />
          </MobileSheet>
        ) : (
          <AdminSettingsPanel
            data={data}
            settings={settings}
            settingsDraft={settingsDraft}
            settingsSaving={settingsSaving}
            hasFilmLoot={hasFilmLoot}
            onDraftChange={setSettingsDraft}
            onSave={() => void saveSettings()}
            onGpsCalibrate={() => calibrateGpsFromDraft()}
            onDownloadEngineers={() => exportEngineers().catch((e) => setError(e instanceof Error ? e.message : 'Ошибка экспорта'))}
          />
        )
      )}

      <AdminPanelShell
        open={scenariosOpen}
        isNarrow={isNarrow}
        onClose={toggleScenarios}
        title="Мероприятия"
        borderClass="border-sideA/40"
      >
        <ScenarioSwitcher
          scenarios={scenarios}
          loading={scenariosLoading}
          error={scenariosError}
          onCreate={handleCreateScenario}
          onActivate={handleActivateScenario}
          onArchive={handleArchiveScenario}
        />
      </AdminPanelShell>

      <AdminPanelShell
        open={data.current_stage === 1 && missionOpen}
        isNarrow={isNarrow}
        onClose={toggleMissionPanel}
        title="Таблички КТ · этап 1"
        borderClass="border-sideA/40"
      >
          {mission.length === 0 ? (
            <p className="p-4 text-sm text-zinc-400">Загрузка КТ…</p>
          ) : (
            <div className="p-4 space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-base font-bold text-sideA">Таблички КТ · этап 1</h2>
                  <p className="text-sm text-zinc-400 mt-0.5">QR + код на каждую контрольную точку</p>
                </div>
                <div className="flex flex-wrap gap-2 items-start">
                  <button type="button" className="btn text-sm border border-zinc-600" onClick={copyMission}>
                    Копировать текст
                  </button>
                  <button
                    type="button"
                    className="btn text-sm border border-sideA text-sideA"
                    onClick={() => downloadStage1Pdf(mission).catch(() => {})}
                  >
                    PDF всех КТ ({mission.length} листов)
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2">
                {mission.map((m) => (
                  <button
                    key={m.id}
                    type="button"
                    className={`rounded-lg border px-3 py-2 text-left text-sm transition-colors ${
                      selectedMissionId === m.id
                        ? 'border-sideA bg-sideA/15 text-sideA'
                        : 'border-zinc-700 bg-zinc-950 hover:border-sideA/50'
                    }`}
                    onClick={() => selectMissionBox(m)}
                  >
                    <span className="font-semibold block">{m.name}</span>
                    <span className="font-mono text-xs text-zinc-400 mt-0.5">код {m.code}</span>
                  </button>
                ))}
              </div>

              {selectedMission && (
                <div className="rounded-lg border border-zinc-700 bg-zinc-950 p-4 grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <h3 className="text-lg font-bold">{selectedMission.name}</h3>
                    <p className="font-mono text-sm text-zinc-400">
                      {selectedMission.lat.toFixed(6)}, {selectedMission.lon.toFixed(6)}
                    </p>
                    <a
                      href={selectedMission.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-sideA underline text-sm break-all"
                    >
                      {selectedMission.url}
                    </a>
                  </div>
                  <div className="space-y-3">
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-zinc-400">Код таблички:</span>
                      <input
                        className="input w-24 text-center font-mono text-lg py-1 min-h-0"
                        inputMode="numeric"
                        maxLength={6}
                        value={editCode}
                        onChange={(e) => setEditCode(e.target.value.replace(/\D/g, ''))}
                      />
                      <button
                        type="button"
                        className="btn text-sm border border-zinc-600"
                        disabled={codeSaving}
                        onClick={() => void saveMissionCode()}
                      >
                        {codeSaving ? '…' : 'Сохранить'}
                      </button>
                    </div>
                    <p className="text-xs text-zinc-500">
                      Лист A4 альбомный: QR и инструкция для наклейки на табличку.
                    </p>
                    <button
                      type="button"
                      className="btn w-full sm:w-auto text-sm border-2 border-sideA text-sideA bg-sideA/10"
                      onClick={() => downloadStage1PdfSingle(selectedMission).catch(() => {})}
                    >
                      PDF: {selectedMission.name} (1 лист)
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </AdminPanelShell>

      <AdminPanelShell
        open={lootPanelOpen}
        isNarrow={isNarrow}
        onClose={toggleLootPanel}
        title="Задача-2 · ящики"
        borderClass="border-warning/40"
      >
          {mission.length === 0 ? (
            <p className="p-4 text-sm text-zinc-400">Загрузка ящиков…</p>
          ) : (
            <div className="p-4 space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-base font-bold text-warning">Задача-2 · ящики</h2>
                  <p className="text-sm text-zinc-400 mt-0.5">
                    {data.stage2_enabled
                      ? 'Активна параллельно с захватом КТ'
                      : 'Резерв — включите, когда понадобится'}
                    {data.stage2_enabled && (
                      <>
                        {' '}
                        · интервал {data.stage2_issue_interval_minutes ?? 60} мин
                        {data.stage2_next_issue_at && (
                          <> · след. автовыдача ~{new Date(data.stage2_next_issue_at).toLocaleTimeString()}</>
                        )}
                      </>
                    )}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2 items-start">
                  {!data.stage2_enabled && (
                    <button
                      type="button"
                      className="btn text-sm border border-green-600 text-green-400"
                      onClick={() => {
                        enableStage2()
                          .then(() => load())
                          .catch((e) => setError(e instanceof Error ? e.message : 'Ошибка'));
                      }}
                    >
                      Включить Задачу-2
                    </button>
                  )}
                  <button
                    type="button"
                    className="btn text-sm border border-warning text-warning disabled:opacity-50"
                    disabled={stage2IssueLoading || !data.stage2_enabled}
                    title={data.stage2_enabled ? undefined : 'Сначала включите Задачу-2'}
                    onClick={() => {
                      setStage2IssueLoading(true);
                      issueStage2Target()
                        .then(() => {
                          load();
                          return fetchStage2Assignments().then(setStage2Assignments);
                        })
                        .catch((e) => setError(e instanceof Error ? e.message : 'Ошибка'))
                        .finally(() => setStage2IssueLoading(false));
                    }}
                  >
                    {stage2IssueLoading ? '…' : 'Выдать цель сейчас'}
                  </button>
                  <button type="button" className="btn text-sm border border-zinc-600" onClick={copyMission}>
                    Копировать текст
                  </button>
                  <button
                    type="button"
                    className="btn text-sm border border-warning text-warning"
                    title="Один PDF-файл: по листу A4 на каждый ящик"
                    onClick={() => downloadStage2Pdf(mission).catch(() => {})}
                  >
                    PDF всех ящиков ({mission.length} листов)
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2">
                {mission.map((m) => {
                  const issued = stage2Assignments.some((a) => a.cache_id === m.id);
                  const done = stage2Assignments.find((a) => a.cache_id === m.id);
                  return (
                  <button
                    key={m.id}
                    type="button"
                    className={`rounded-lg border px-3 py-2 text-left text-sm transition-colors ${
                      selectedMissionId === m.id
                        ? 'border-warning bg-warning/15 text-warning'
                        : issued
                          ? done?.delivered
                            ? 'border-green-600/60 bg-green-950/40'
                            : done?.destroyed
                              ? 'border-purple-600/60 bg-purple-950/30'
                              : 'border-warning/40 bg-warning/5'
                          : m.enabled === false
                            ? 'border-zinc-800 bg-zinc-950 opacity-40'
                            : 'border-zinc-700 bg-zinc-950 hover:border-warning/50'
                    }`}
                    onClick={() => selectMissionBox(m)}
                  >
                    <span className="font-semibold block">{m.name}</span>
                    <span className="font-mono text-xs text-zinc-400 mt-0.5">код {m.code}</span>
                    <span className="text-[10px] text-zinc-500 block mt-0.5">
                      {m.enabled === false ? 'выкл' : 'вкл'}
                    </span>
                    {issued && (
                      <span className="text-[10px] text-zinc-500 block mt-0.5">
                        {done?.delivered ? 'сдан' : done?.destroyed ? 'вскрыт' : 'выдан'}
                      </span>
                    )}
                  </button>
                  );
                })}
              </div>

              {stage2Assignments.length > 0 && (
                <div className="rounded-lg border border-zinc-700 bg-zinc-950 p-3">
                  <h3 className="text-sm font-bold text-zinc-300 mb-2">История выдач</h3>
                  <ul className="space-y-1.5 max-h-36 overflow-y-auto text-sm">
                    {[...stage2Assignments]
                      .sort((a, b) => b.round_number - a.round_number)
                      .map((a) => (
                        <li key={a.id} className="flex flex-wrap items-center gap-2 text-zinc-400">
                          <span className="font-mono text-xs text-zinc-600">#{a.round_number}</span>
                          <span className="text-zinc-200">{a.cache_name}</span>
                          <span className="text-xs">
                            {new Date(a.assigned_at).toLocaleString()}
                          </span>
                          <span
                            className={`text-xs ${
                              a.delivered
                                ? 'text-green-400'
                                : a.destroyed
                                  ? 'text-purple-400'
                                  : 'text-warning'
                            }`}
                          >
                            {a.delivered
                              ? `сдан ${a.delivered_by_side === 'A' ? 'ЛК' : 'СБГ'}`
                              : a.destroyed
                                ? `вскрыт ${a.destroyed_by_side === 'A' ? 'ЛК' : 'СБГ'}`
                                : 'активна'}
                          </span>
                        </li>
                      ))}
                  </ul>
                </div>
              )}

              {selectedMission && (
                <div className="rounded-lg border border-zinc-700 bg-zinc-950 p-4 grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <h3 className="text-lg font-bold">{selectedMission.name}</h3>
                    <p className="font-mono text-sm text-zinc-400">
                      {selectedMission.lat.toFixed(6)}, {selectedMission.lon.toFixed(6)}
                    </p>
                    <a
                      href={selectedMission.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-sm text-sideA underline break-all"
                    >
                      {selectedMission.url}
                    </a>
                  </div>
                  <div className="space-y-3">
                    <div className="flex flex-wrap items-center gap-3">
                      <span className="text-sm text-zinc-400">Код детонации</span>
                      <input
                        className="input w-28 text-center font-mono text-xl py-2"
                        inputMode="numeric"
                        pattern="[0-9]*"
                        maxLength={6}
                        value={editCode}
                        onChange={(e) => setEditCode(e.target.value.replace(/\D/g, ''))}
                        onBlur={() => {
                          if (editCode !== selectedMission.code) void saveMissionCode();
                        }}
                      />
                      <button
                        type="button"
                        className="btn text-sm border border-zinc-600"
                        disabled={codeSaving}
                        onClick={() => void saveMissionCode()}
                      >
                        {codeSaving ? '…' : 'Сохранить'}
                      </button>
                    </div>
                    <p className="text-xs text-zinc-500">
                      Лист A4 альбомный для наклейки на плёнку: QR и инструкция.
                    </p>
                    <button
                      type="button"
                      className="btn w-full sm:w-auto text-sm border-2 border-warning text-warning bg-warning/10"
                      onClick={() =>
                        downloadStage2PdfSingle(selectedMission).catch(() => {})
                      }
                    >
                      PDF: {selectedMission.name} (1 лист)
                    </button>
                    <button
                      type="button"
                      className={`btn w-full sm:w-auto text-sm border ${
                        selectedMission.enabled !== false
                          ? 'border-zinc-600'
                          : 'border-green-600 text-green-400'
                      }`}
                      disabled={codeSaving}
                      onClick={() =>
                        void toggleFilmLootEnabled(
                          selectedMission.id,
                          selectedMission.enabled === false
                        )
                      }
                    >
                      {selectedMission.enabled !== false ? 'Выключить на карте' : 'Включить на карте'}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </AdminPanelShell>

      <AdminPanelShell
        open={data.current_stage === 3 && missionOpen}
        isNarrow={isNarrow}
        onClose={toggleMissionPanel}
        title="Мертвяки этапа 3"
        borderClass="border-warning/40"
      >
          {mission.length === 0 ? (
            <p className="p-4 text-sm text-zinc-400">Загрузка мертвяков…</p>
          ) : (
            <div className="p-4 space-y-4">
              <div>
                <h2 className="text-base font-bold text-warning">Мертвяки этапа 3</h2>
                <p className="text-sm text-zinc-400 mt-0.5">Включайте нужные из меню · коды для штаба</p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
                {mission.map((m) => (
                  <button
                    key={m.id}
                    type="button"
                    className={`rounded-lg border px-3 py-2 text-left text-sm transition-colors ${
                      selectedMissionId === m.id
                        ? 'border-warning bg-warning/15 text-warning'
                        : 'border-zinc-700 bg-zinc-950 hover:border-warning/50'
                    } ${m.enabled === false ? 'opacity-50' : ''}`}
                    onClick={() => selectMissionBox(m)}
                  >
                    <span className="font-semibold block">{m.name}</span>
                    <span className="font-mono text-xs text-zinc-400 mt-0.5">
                      код {m.code} · {m.enabled === false ? 'выкл' : 'вкл'}
                    </span>
                  </button>
                ))}
              </div>

              {selectedMission && (
                <div className="rounded-lg border border-zinc-700 bg-zinc-950 p-4 space-y-3">
                  <h3 className="text-lg font-bold">{selectedMission.name}</h3>
                  <p className="font-mono text-sm text-zinc-400">
                    {selectedMission.lat.toFixed(6)}, {selectedMission.lon.toFixed(6)}
                  </p>
                  <div className="flex flex-wrap items-center gap-3">
                    <span className="text-sm text-zinc-400">Код</span>
                    <input
                      className="input w-28 text-center font-mono text-xl py-2"
                      inputMode="numeric"
                      maxLength={6}
                      value={editCode}
                      onChange={(e) => setEditCode(e.target.value.replace(/\D/g, ''))}
                      onBlur={() => {
                        if (editCode !== selectedMission.code) void saveMissionCode();
                      }}
                    />
                    <button
                      type="button"
                      className="btn text-sm border border-zinc-600"
                      disabled={codeSaving}
                      onClick={() => void saveMissionCode()}
                    >
                      {codeSaving ? '…' : 'Сохранить'}
                    </button>
                  </div>
                  <button
                    type="button"
                    className={`btn text-sm border ${
                      selectedMission.enabled !== false
                        ? 'border-sideB text-sideB'
                        : 'border-green-600 text-green-400'
                    }`}
                    disabled={codeSaving}
                    onClick={() =>
                      void toggleMertvyakEnabled(selectedMission.id, selectedMission.enabled === false)
                    }
                  >
                    {selectedMission.enabled !== false ? 'Выключить на карте' : 'Включить на карте'}
                  </button>
                </div>
              )}
            </div>
          )}
        </AdminPanelShell>

      <div className="flex-1 flex flex-col min-h-0">
        {data.game_status === 'idle' && (!isNarrow || mapEditMode) && (
          <AdminMapEditorBar
            mapEditMode={mapEditMode}
            hideToggleOnMobile={isNarrow}
            createTarget={createTarget}
            mertvyakCreateSide={mertvyakCreateSide}
            landmarkCreateKind={landmarkCreateKind}
            landmarkCreateSide={landmarkCreateSide}
            onToggleEditMode={() => {
              setMapEditMode((v) => !v);
              setCreateTarget(null);
            }}
            onSetCreateTarget={setCreateTarget}
            onMertvyakSideChange={setMertvyakCreateSide}
            onLandmarkKindChange={setLandmarkCreateKind}
            onLandmarkSideChange={setLandmarkCreateSide}
          />
        )}
        <div className="flex-1 flex flex-col md:flex-row min-h-0 relative">
        <div className="map-page flex-1 min-h-0 max-md:min-h-0 md:min-h-0 relative">
        <GameMap
          data={data}
            showRadii
            engineers={engineers}
            adminStage2Overview
          pulsePointId={pulsePointId}
            warnPointId={warnPointId}
          explosionCacheId={explosionCacheId}
            flyTo={flyTo}
            adminSelection={mapSelection}
            renderAdminPopup={renderAdminPopup}
            onPointClick={selectPoint}
            onCacheClick={selectCache}
            onLandmarkClick={mapEditMode ? selectLandmark : undefined}
            mapEditMode={mapEditMode}
            createTarget={createTarget}
            onObjectMove={(kind, id, lat, lon) => void handleObjectMove(kind, id, lat, lon)}
            onMapClickCreate={(lat, lon) => void handleMapClickCreate(lat, lon)}
            onAdminPopupClose={() => {
              if (popupSwitchRef.current) return;
              setMapSelection(null);
            }}
          />
          {isNarrow &&
            data.current_stage !== 2 &&
            !missionOpen &&
            !lootPanelOpen && (
              <AdminQuickNav
                data={data}
                mapSelection={mapSelection}
                onSelectPoint={selectPoint}
                onSelectCache={selectCache}
                onForceRelease={(id) => void adminAction(`/hold/force-release/${id}`).then(load)}
              />
            )}
        </div>

        {chatOpen && !isNarrow && (
          <aside className="no-print relative z-10 shrink-0 h-[min(42vh,360px)] md:h-auto md:w-80 lg:w-96 border-t md:border-t-0 md:border-l border-zinc-800 flex flex-col min-h-0">
            <FieldOrdersPanel mode="admin" side={chatSide} refreshToken={ordersRefresh} />
            <ChatPanel
              mode="admin"
              side={chatSide}
              thread={chatThread}
              onSideChange={setChatSide}
              onThreadChange={setChatThread}
              refreshToken={chatRefresh}
              className="flex-1 min-h-0"
            />
          </aside>
        )}
        </div>
      </div>

      {chatOpen && isNarrow && (
        <MobileSheet
          open
          onClose={() => setChatOpen(false)}
          title="Чат и приказы"
          variant="bottom"
          contentClassName="flex-1 flex flex-col min-h-0"
        >
          <FieldOrdersPanel mode="admin" side={chatSide} refreshToken={ordersRefresh} />
          <ChatPanel
            mode="admin"
            side={chatSide}
            thread={chatThread}
            onSideChange={setChatSide}
            onThreadChange={setChatThread}
            refreshToken={chatRefresh}
            className="flex-1 min-h-0"
          />
        </MobileSheet>
      )}

      {!isNarrow &&
        data.current_stage !== 2 &&
        !missionOpen &&
        !lootPanelOpen &&
        (data.points.length > 0 || data.caches.length > 0) && (
        <div className="no-print shrink-0 p-2 border-t border-zinc-800">
          <p className="text-[10px] uppercase tracking-wide text-zinc-600 mb-1.5 px-0.5">Быстрый переход</p>
          <div className="flex flex-wrap gap-1 max-h-24 overflow-y-auto">
          {data.points.map((p) => (
            <button
              key={p.id}
              type="button"
                className={`btn text-xs py-1 min-h-0 border ${
                  mapSelection?.kind === 'point' && mapSelection.id === p.id
                    ? 'border-sideA bg-sideA/20 text-sideA'
                    : 'border-zinc-700'
                }`}
                onClick={() => selectPoint(p)}
              >
                {p.name}
              </button>
            ))}
            {data.caches.map((c) => (
              <button
                key={`c-${c.id}`}
                type="button"
                className={`btn text-xs py-1 min-h-0 border ${
                  mapSelection?.kind === 'cache' && mapSelection.id === c.id
                    ? 'border-warning bg-warning/20 text-warning'
                    : 'border-zinc-700'
                }`}
                onClick={() => selectCache(c)}
              >
                {c.name}
            </button>
          ))}
          {data.points.filter((p) => p.held_by).map((p) => (
            <button
              key={`fr-${p.id}`}
              type="button"
                className="btn text-xs bg-sideB text-white py-1 min-h-0"
              onClick={() => adminAction(`/hold/force-release/${p.id}`).then(load)}
            >
              Сброс {p.id}
            </button>
          ))}
        </div>
      </div>
      )}

      <div className="no-print hidden">
        <QRPrint />
      </div>

      {tracksOpen && data && <AdminTracksPanel data={data} onClose={() => setTracksOpen(false)} />}
    </div>
  );
}
