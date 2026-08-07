import * as amplitude from '@amplitude/analytics-browser';

// Analytics is optional: without this env var the app runs with analytics disabled.
export const isAmplitudeConfigured = Boolean(process.env.NEXT_PUBLIC_AMPLITUDE_API_KEY);

let initialized = false;

export function initAmplitude() {
  if (initialized) return;
  initialized = true;

  const apiKey = process.env.NEXT_PUBLIC_AMPLITUDE_API_KEY;
  if (!apiKey) {
    console.warn('Amplitude API key missing — analytics disabled');
    return;
  }

  amplitude.init(apiKey, { autocapture: false });
}
