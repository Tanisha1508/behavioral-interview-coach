import type { RemoteParticipant, Room } from 'livekit-client';

/** Mirrors SessionConfig fields in src/session/setup.py. Materials travel
 * as separate set_doc RPCs (15KiB payload limit per call), then
 * start_interview carries the config. */
export interface InterviewSetup {
  profile_id: string;
  mode: 'interview' | 'coach';
  session_type: 'DRILL' | 'SIMULATION';
  duration_min: number | null; // SIMULATION only, 15-60
  followup_mode: 'listen' | 'probing';
  materials: Record<string, string>;
  source: {
    scripted: string[];
    use_pack: boolean;
    bank_count: number;
    intel_text: string;
  };
}

export const DEFAULT_SETUP: InterviewSetup = {
  profile_id: 'pm',
  mode: 'interview',
  session_type: 'DRILL',
  duration_min: null,
  followup_mode: 'listen',
  materials: {},
  source: { scripted: [], use_pack: false, bank_count: 3, intel_text: '' },
};

function waitForAgent(room: Room, timeoutMs = 20000): Promise<RemoteParticipant> {
  return new Promise((resolve, reject) => {
    const existing = Array.from(room.remoteParticipants.values())[0];
    if (existing) return resolve(existing);
    const timer = setTimeout(() => {
      room.off('participantConnected', onJoin);
      reject(new Error('agent did not join the room in time'));
    }, timeoutMs);
    const onJoin = (p: RemoteParticipant) => {
      clearTimeout(timer);
      room.off('participantConnected', onJoin);
      resolve(p);
    };
    room.on('participantConnected', onJoin);
  });
}

async function rpcWithRetry(
  room: Room,
  destinationIdentity: string,
  method: string,
  payload: string,
  tries = 10
): Promise<void> {
  for (let i = 0; i < tries; i++) {
    try {
      await room.localParticipant.performRpc({ destinationIdentity, method, payload });
      return;
    } catch (err) {
      // The agent may not have registered its RPC handlers yet right
      // after joining; on a cold worker start registration can lag the
      // join by several seconds, and a ~2s retry window lost the whole
      // setup form (live 2026-07-13, TEST-LOG finding 1). Keep trying
      // for ~10s before giving up.
      if (i === tries - 1) throw err;
      await new Promise((r) => setTimeout(r, 1000));
    }
  }
}

// LiveKit rejects RPC payloads over 15KiB. The form's 12000-char cap only
// guarantees that for ASCII; bullets and smart quotes from pasted PDFs are
// 2-3 UTF-8 bytes each, so measure the encoded payload and trim by bytes.
const MAX_RPC_PAYLOAD_BYTES = 15_000;

function fitPayload(name: string, text: string): string {
  const bytes = (t: string) => new TextEncoder().encode(JSON.stringify({ name, text: t })).length;
  if (bytes(text) <= MAX_RPC_PAYLOAD_BYTES) return JSON.stringify({ name, text });
  let lo = 0;
  let hi = text.length;
  while (lo < hi) {
    const mid = Math.ceil((lo + hi) / 2);
    if (bytes(text.slice(0, mid)) <= MAX_RPC_PAYLOAD_BYTES) lo = mid;
    else hi = mid - 1;
  }
  return JSON.stringify({ name, text: text.slice(0, lo) });
}

/** Send the interview setup to the agent after the room connects. Returns
 * the names of documents that could not be delivered; a failed document
 * must never block start_interview, or the agent falls back to a default
 * session after a long silent wait (live failure 2026-07-13). */
export async function sendSetup(room: Room, setup: InterviewSetup): Promise<string[]> {
  const agent = await waitForAgent(room);
  const droppedDocs: string[] = [];
  for (const [name, text] of Object.entries(setup.materials)) {
    if (!text.trim()) continue;
    try {
      await rpcWithRetry(room, agent.identity, 'set_doc', fitPayload(name, text));
    } catch (err) {
      console.error(`set_doc failed for ${name}`, err);
      droppedDocs.push(name);
    }
  }
  const config = { ...setup, materials: {} };
  await rpcWithRetry(room, agent.identity, 'start_interview', JSON.stringify(config));
  return droppedDocs;
}
