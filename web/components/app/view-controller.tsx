'use client';

import { useEffect, useRef } from 'react';
import { useTheme } from 'next-themes';
import { AnimatePresence, motion } from 'motion/react';
import { toast } from 'sonner';
import { useSessionContext } from '@livekit/components-react';
import type { AppConfig } from '@/app-config';
import { AgentSessionView_01 } from '@/components/agents-ui/blocks/agent-session-view-01';
import {
  CoachActionsBanner,
  CoachPackPanel,
  DebriefPanel,
  QuestionBanner,
  ScoreCardPanel,
} from '@/components/app/interview-overlay';
import { SetupForm } from '@/components/app/setup-form';
import { useInterviewState } from '@/hooks/useInterviewState';
import { DEFAULT_SETUP, type InterviewSetup, sendSetup } from '@/lib/interview-setup';

const MotionSetupForm = motion.create(SetupForm);
const MotionSessionView = motion.create(AgentSessionView_01);

const VIEW_MOTION_PROPS = {
  variants: {
    visible: {
      opacity: 1,
    },
    hidden: {
      opacity: 0,
    },
  },
  initial: 'hidden',
  animate: 'visible',
  exit: 'hidden',
  transition: {
    duration: 0.5,
    ease: 'linear' as const,
  },
};

interface ViewControllerProps {
  appConfig: AppConfig;
}

export function ViewController({ appConfig }: ViewControllerProps) {
  const session = useSessionContext();
  const { isConnected, start, end } = session;
  const { resolvedTheme } = useTheme();
  const pendingSetup = useRef<InterviewSetup | null>(null);
  const lastSetup = useRef<InterviewSetup | null>(null);
  const restartPending = useRef(false);
  const {
    question,
    questionNumber,
    questionTotal,
    card,
    coachPack,
    gamePlans,
    rewrite,
    debrief,
    ended,
    dismissCard,
  } = useInterviewState(session.room);

  const startWithSetup = (setup: InterviewSetup) => {
    pendingSetup.current = setup;
    lastSetup.current = setup;
    start();
  };

  // Coach panel: "Practice this in Drill" restarts the session as a
  // one-question graded rep, keeping the same documents.
  const practiceInDrill = (questionText: string) => {
    const base = lastSetup.current;
    pendingSetup.current = {
      ...DEFAULT_SETUP,
      mode: 'interview',
      followup_mode: 'listen',
      profile_id: base?.profile_id ?? 'pm',
      materials: base?.materials ?? {},
      source: { scripted: [questionText], use_pack: false, bank_count: 0, intel_text: '' },
    };
    lastSetup.current = pendingSetup.current;
    restartPending.current = true;
    toast.info('Switching to a Drill rep of that question...');
    end();
  };

  useEffect(() => {
    if (!isConnected && restartPending.current) {
      restartPending.current = false;
      start();
    }
  }, [isConnected, start]);

  useEffect(() => {
    if (!isConnected || !pendingSetup.current) return;
    const setup = pendingSetup.current;
    pendingSetup.current = null;
    sendSetup(session.room, setup)
      .then((droppedDocs) => {
        if (droppedDocs.length > 0) {
          toast.warning(
            `Could not send ${droppedDocs.join(', ')} to the interviewer; continuing without.`
          );
        }
      })
      .catch((err) => {
        console.error('failed to send interview setup', err);
        toast.warning('Setup could not reach the interviewer; using defaults.');
      });
  }, [isConnected, session.room]);

  useEffect(() => {
    if (!ended || !isConnected) return;
    // The interviewer announced the end: leave before the agent does so
    // the departure never reads as a failure.
    end();
    toast.success('Session complete. Nice work.');
  }, [ended, isConnected, end]);

  const agentRpc = (method: string, payload: object) => {
    const agent = Array.from(session.room.remoteParticipants.values())[0];
    if (!agent) return;
    session.room.localParticipant
      .performRpc({
        destinationIdentity: agent.identity,
        method,
        payload: JSON.stringify(payload),
      })
      .catch((err) => console.error(`${method} failed`, err));
  };

  const discuss = (text: string) => agentRpc('discuss_question', { text });
  const requestRewrite = () => agentRpc('get_rewrite', {});

  return (
    <>
      <AnimatePresence mode="wait">
        {/* Setup view */}
        {!isConnected && (
          <MotionSetupForm key="setup" {...VIEW_MOTION_PROPS} onStartCall={startWithSetup} />
        )}
        {/* Session view */}
        {isConnected && (
          <MotionSessionView
            key="session-view"
            {...VIEW_MOTION_PROPS}
            preConnectMessage="Your interviewer is joining. Speak your answer after the question."
            supportsChatInput={appConfig.supportsChatInput}
            supportsVideoInput={appConfig.supportsVideoInput}
            supportsScreenShare={appConfig.supportsScreenShare}
            isPreConnectBufferEnabled={appConfig.isPreConnectBufferEnabled}
            audioVisualizerType={appConfig.audioVisualizerType}
            audioVisualizerColor={
              resolvedTheme === 'dark'
                ? appConfig.audioVisualizerColorDark
                : appConfig.audioVisualizerColor
            }
            audioVisualizerColorShift={appConfig.audioVisualizerColorShift}
            audioVisualizerBarCount={appConfig.audioVisualizerBarCount}
            audioVisualizerGridRowCount={appConfig.audioVisualizerGridRowCount}
            audioVisualizerGridColumnCount={appConfig.audioVisualizerGridColumnCount}
            audioVisualizerRadialBarCount={appConfig.audioVisualizerRadialBarCount}
            audioVisualizerRadialRadius={appConfig.audioVisualizerRadialRadius}
            audioVisualizerWaveLineWidth={appConfig.audioVisualizerWaveLineWidth}
            onInterrupt={() => agentRpc('interrupt', {})}
            className="fixed inset-0"
          />
        )}
      </AnimatePresence>
      {isConnected && (
        <>
          <QuestionBanner question={question} number={questionNumber} total={questionTotal} />
          {coachPack && !question && <CoachActionsBanner />}
          {coachPack && (
            <CoachPackPanel
              pack={coachPack}
              gamePlans={gamePlans}
              onDiscuss={discuss}
              onPractice={practiceInDrill}
            />
          )}
          {card && (
            <ScoreCardPanel
              card={card}
              rewrite={rewrite}
              onRewrite={requestRewrite}
              onDismiss={dismissCard}
            />
          )}
          {debrief && <DebriefPanel debrief={debrief} />}
        </>
      )}
    </>
  );
}
