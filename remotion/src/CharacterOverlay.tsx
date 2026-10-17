import React from 'react';
import {
  Img,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import { CharacterInfo } from './types';

interface CharacterOverlayProps {
  character?: CharacterInfo;
  durationInFrames: number;
}

export const CharacterOverlay: React.FC<CharacterOverlayProps> = ({
  character,
  durationInFrames,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  if (!character || !character.name) {
    return null;
  }

  // HUD Entrance spring
  const hudEntrance = spring({
    frame,
    fps,
    config: { damping: 15, mass: 0.7 },
  });

  // Calculate simulated heart rate BPM with subtle natural variance
  const bpm = Math.round(76 + Math.sin(frame / 12) * 5 + Math.cos(frame / 25) * 3);

  // Subtle breathing scale for avatar / HUD
  const breatheScale = 1 + Math.sin((frame / fps) * Math.PI * 1.2) * 0.02;

  // Bodycam PiP entrance & exit (fades in at frame 15, subtle persistent presence)
  const pipOpacity = interpolate(
    frame,
    [10, 25, durationInFrames - 30, durationInFrames - 10],
    [0, 1, 1, 0],
    { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }
  );

  // Bodycam subtle slow zoom / breathing
  const bodycamScale = interpolate(
    frame % (fps * 8),
    [0, fps * 4, fps * 8],
    [1.0, 1.05, 1.0],
    { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }
  );

  // Recording blinking dot
  const recDotOpacity = Math.floor(frame / 15) % 2 === 0 ? 1 : 0.2;

  return (
    <>
      {/* 1. TOP-LEFT SURVIVOR STATUS HUD */}
      <div
        style={{
          position: 'absolute',
          top: 70,
          left: 32,
          display: 'flex',
          alignItems: 'center',
          gap: 14,
          padding: '10px 18px 10px 12px',
          background: 'linear-gradient(135deg, rgba(10, 15, 24, 0.92) 0%, rgba(17, 24, 39, 0.85) 100%)',
          border: '1.5px solid rgba(239, 68, 68, 0.75)',
          borderRadius: 20,
          boxShadow: '0 8px 30px rgba(0, 0, 0, 0.85), 0 0 15px rgba(239, 68, 68, 0.3)',
          backdropFilter: 'blur(12px)',
          transform: `translateX(${(1 - hudEntrance) * -60}px) scale(${breatheScale})`,
          opacity: hudEntrance,
          zIndex: 95,
          pointerEvents: 'none',
        }}
      >
        {/* Avatar Photo / Icon */}
        <div
          style={{
            width: 58,
            height: 58,
            borderRadius: 16,
            overflow: 'hidden',
            border: '2px solid #EF4444',
            position: 'relative',
            boxShadow: '0 0 10px rgba(239, 68, 68, 0.5)',
            backgroundColor: '#0f172a',
            flexShrink: 0,
          }}
        >
          {character.avatarSrc ? (
            <Img
              src={character.avatarSrc}
              style={{
                width: '100%',
                height: '100%',
                objectFit: 'cover',
              }}
            />
          ) : (
            <div
              style={{
                width: '100%',
                height: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#EF4444',
                fontWeight: 900,
                fontSize: 22,
              }}
            >
              {character.name[0]}
            </div>
          )}
          {/* Subtle Scanline Overlay */}
          <div
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              background: 'repeating-linear-gradient(0deg, rgba(0,0,0,0.15) 0px, rgba(0,0,0,0.15) 2px, transparent 2px, transparent 4px)',
              pointerEvents: 'none',
            }}
          />
        </div>

        {/* Character Info */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span
              style={{
                fontFamily: 'Impact, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                fontSize: 22,
                letterSpacing: 2,
                color: '#F8FAFC',
                textTransform: 'uppercase',
                textShadow: '0 2px 8px rgba(0,0,0,0.8)',
              }}
            >
              {character.name}
            </span>
            <span
              style={{
                fontSize: 11,
                fontWeight: 800,
                letterSpacing: 1.2,
                padding: '2px 8px',
                borderRadius: 10,
                backgroundColor: 'rgba(239, 68, 68, 0.25)',
                border: '1px solid #EF4444',
                color: '#FECACA',
                textTransform: 'uppercase',
              }}
            >
              DAY {character.day || 1}
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {/* Heart Rate Vitals */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ color: '#EF4444', fontSize: 13, display: 'inline-block', transform: `scale(${1 + (frame % 25 < 5 ? 0.3 : 0)})` }}>
                ♥
              </span>
              <span
                style={{
                  fontFamily: 'Courier New, monospace',
                  fontSize: 13,
                  fontWeight: 700,
                  color: '#94A3B8',
                  letterSpacing: 1,
                }}
              >
                {bpm} BPM
              </span>
            </div>

            {/* Condition Pill */}
            <span
              style={{
                fontSize: 11,
                fontWeight: 700,
                color: '#38BDF8',
                letterSpacing: 1,
                textTransform: 'uppercase',
                maxWidth: 160,
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              {character.condition ? `[${character.condition.split(',')[0]}]` : '[ALERT]'}
            </span>
          </div>
        </div>
      </div>

      {/* 2. LOWER-RIGHT TACTICAL BODY-CAM FEED */}
      {character.fullBodySrc ? (
        <div
          style={{
            position: 'absolute',
            bottom: 240,
            right: 32,
            width: 220,
            height: 310,
            borderRadius: 18,
            overflow: 'hidden',
            border: '2px solid rgba(239, 68, 68, 0.75)',
            boxShadow: '0 12px 36px rgba(0, 0, 0, 0.9), 0 0 20px rgba(239, 68, 68, 0.25)',
            opacity: pipOpacity,
            zIndex: 91,
            pointerEvents: 'none',
            backgroundColor: '#0a0f18',
          }}
        >
          {/* Character Action Video / Image */}
          <div
            style={{
              width: '100%',
              height: '100%',
              transform: `scale(${bodycamScale})`,
              transformOrigin: 'center center',
            }}
          >
            <Img
              src={character.fullBodySrc}
              style={{
                width: '100%',
                height: '100%',
                objectFit: 'cover',
                filter: 'contrast(1.15) brightness(0.95)',
              }}
            />
          </div>

          {/* Tactical HUD Header on Body-Cam */}
          <div
            style={{
              position: 'absolute',
              top: 8,
              left: 10,
              right: 10,
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              zIndex: 3,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <div
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  backgroundColor: '#EF4444',
                  opacity: recDotOpacity,
                  boxShadow: '0 0 6px #EF4444',
                }}
              />
              <span
                style={{
                  fontFamily: 'Courier New, monospace',
                  fontSize: 10,
                  fontWeight: 900,
                  color: '#FFFFFF',
                  letterSpacing: 1.5,
                  textShadow: '0 1px 4px rgba(0,0,0,0.9)',
                }}
              >
                LIVE CAM
              </span>
            </div>
            <span
              style={{
                fontFamily: 'Courier New, monospace',
                fontSize: 10,
                fontWeight: 700,
                color: '#94A3B8',
              }}
            >
              ACT-0{character.day || 1}
            </span>
          </div>

          {/* Tactical Corner Brackets */}
          <div
            style={{
              position: 'absolute',
              inset: 6,
              border: '1px dashed rgba(255, 255, 255, 0.3)',
              borderRadius: 12,
              pointerEvents: 'none',
            }}
          />

          {/* Scanline Grid */}
          <div
            style={{
              position: 'absolute',
              inset: 0,
              background: 'repeating-linear-gradient(0deg, rgba(0,0,0,0.2) 0px, rgba(0,0,0,0.2) 2px, transparent 2px, transparent 4px)',
              pointerEvents: 'none',
            }}
          />
        </div>
      ) : null}
    </>
  );
};
