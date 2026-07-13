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
  tries = 4
): Promise<void> {
  for (let i = 0; i < tries; i++) {
    try {
      await room.localParticipant.performRpc({ destinationIdentity, method, payload });
      return;
    } catch (err) {
      // The agent may not have registered its RPC handlers yet right
      // after joining; back off briefly and retry.
      if (i === tries - 1) throw err;
      await new Promise((r) => setTimeout(r, 600));
    }
  }
}

/** Send the interview setup to the agent after the room connects. */
export async function sendSetup(room: Room, setup: InterviewSetup): Promise<void> {
  const agent = await waitForAgent(room);
  for (const [name, text] of Object.entries(setup.materials)) {
    if (!text.trim()) continue;
    await rpcWithRetry(room, agent.identity, 'set_doc', JSON.stringify({ name, text }));
  }
  const config = { ...setup, materials: {} };
  await rpcWithRetry(room, agent.identity, 'start_interview', JSON.stringify(config));
}
