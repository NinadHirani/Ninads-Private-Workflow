import React, { useMemo } from 'react';
import { useCurrentFrame, useVideoConfig } from 'remotion';
import { WordItem, VideoStyle } from './types';

interface Phrase {
  words: WordItem[];
  startSec: number;
  endSec: number;
}

export const CaptionsOverlay: React.FC<{
  words: WordItem[];
  style?: VideoStyle;
}> = ({ words, style = 'anime' }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const currentSec = frame / fps;

  // Group words into short mobile-friendly phrases (3-4 words max)
  const phrases = useMemo(() => {
    if (!words || words.length === 0) return [];
    const result: Phrase[] = [];
    let currentBatch: WordItem[] = [];

    for (let i = 0; i < words.length; i++) {
      currentBatch.push(words[i]);
      const isBatchFull = currentBatch.length >= 3;
      const isLongPause =
        i < words.length - 1 && words[i + 1].start - words[i].end > 0.45;
      const isEnd = i === words.length - 1;

      if (isBatchFull || isLongPause || isEnd) {
        result.push({
          words: [...currentBatch],
          startSec: currentBatch[0].start,
          endSec: currentBatch[currentBatch.length - 1].end,
        });
        currentBatch = [];
      }
    }
    return result;
  }, [words]);

  // Find currently active phrase
  const activePhrase = phrases.find(
    (p) => currentSec >= p.startSec - 0.05 && currentSec <= p.endSec + 0.15
  );

  if (!activePhrase) return null;

  // Theme styling based on genre
  const highlightColor =
    style === 'anime'
      ? '#FFE500' // vibrant anime yellow
      : style === 'viral'
      ? '#00FFA3' // viral neon cyan/green
      : style === 'chill'
      ? '#E0F2FE' // soft sky white
      : '#FCD34D'; // warm gold cinematic

  return (
    <div
      style={{
        position: 'absolute',
        bottom: 260,
        left: 40,
        right: 40,
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: 16,
        textAlign: 'center',
        pointerEvents: 'none',
        zIndex: 100,
      }}
    >
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          justifyContent: 'center',
          gap: '12px 16px',
          backgroundColor: 'rgba(0, 0, 0, 0.45)',
          padding: '16px 28px',
          borderRadius: 24,
          backdropFilter: 'blur(8px)',
          boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
          border: '1px solid rgba(255,255,255,0.1)',
        }}
      >
        {activePhrase.words.map((w, idx) => {
          const isWordActive =
            currentSec >= w.start - 0.05 && currentSec <= w.end + 0.05;

          return (
            <span
              key={idx}
              style={{
                fontFamily:
                  'Impact, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                fontSize: 54,
                fontWeight: 900,
                textTransform: 'uppercase',
                letterSpacing: 2,
                color: isWordActive ? highlightColor : '#FFFFFF',
                textShadow: isWordActive
                  ? `0 0 20px ${highlightColor}, -3px -3px 0 #000, 3px -3px 0 #000, -3px 3px 0 #000, 3px 3px 0 #000`
                  : '-3px -3px 0 #000, 3px -3px 0 #000, -3px 3px 0 #000, 3px 3px 0 #000',
                transform: isWordActive ? 'scale(1.14)' : 'scale(1.0)',
                transition: 'transform 0.08s ease, color 0.08s ease',
                display: 'inline-block',
              }}
            >
              {w.word}
            </span>
          );
        })}
      </div>
    </div>
  );
};
