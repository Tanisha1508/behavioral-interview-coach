'use client';

import { type MotionProps, motion } from 'motion/react';
import { SpeakingOwl } from '@/components/app/speaking-owl';
import { cn } from '@/lib/shadcn/utils';

// The agent tile renders the speaking owl mascot (components/app/speaking-owl).
// The audioVisualizer* props are kept for API compatibility with the vendored
// session block, but are no longer used: the owl is the visualizer.
interface AudioVisualizerProps extends MotionProps {
  isChatOpen: boolean;
  audioVisualizerType?: 'bar' | 'wave' | 'grid' | 'radial' | 'aura';
  audioVisualizerColor?: `#${string}`;
  audioVisualizerColorShift?: number;
  audioVisualizerWaveLineWidth?: number;
  audioVisualizerGridRowCount?: number;
  audioVisualizerGridColumnCount?: number;
  audioVisualizerRadialBarCount?: number;
  audioVisualizerRadialRadius?: number;
  audioVisualizerBarCount?: number;
  className?: string;
}

export function AudioVisualizer({
  className,
  initial,
  animate,
  transition,
  style,
}: AudioVisualizerProps) {
  return (
    <motion.div
      className={cn('flex items-center justify-center', className)}
      initial={initial}
      animate={animate}
      transition={transition}
      style={style}
    >
      <SpeakingOwl />
    </motion.div>
  );
}
