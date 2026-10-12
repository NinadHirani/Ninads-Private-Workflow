import React from 'react';
import {
  AbsoluteFill,
  Audio,
  Img,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import { ShortsVideoProps } from './types';
import { SceneRenderer } from './SceneRenderer';
import { CaptionsOverlay } from './CaptionsOverlay';

export const ShortsVideo: React.FC<ShortsVideoProps> = ({
  scenes,
  voiceoverSrc,
  words,
  musicSrc,
  musicVolume = 0.18,
  style = 'anime',
  title,
  logoSrc,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Top header badge animation (enters during first 15 frames, stays for 4 seconds, fades out)
  const headerEntrance = spring({
    frame,
    fps,
    config: { damping: 14, mass: 0.8 },
  });

  const headerOpacity = interpolate(
    frame,
    [0, 15, fps * 4.5, fps * 5.2],
    [0, 1, 1, 0],
    { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }
  );

  return (
    <AbsoluteFill style={{ backgroundColor: '#000000' }}>
      {/* Visual Scenes with Ken Burns camera motion */}
      <SceneRenderer scenes={scenes} style={style} />

      {/* Voiceover Spoken Audio */}
      {voiceoverSrc ? <Audio src={voiceoverSrc} /> : null}

      {/* Background Music Track */}
      {musicSrc ? (
        <Audio src={musicSrc} volume={musicVolume} loop />
      ) : null}

      {/* Optional Top Hook Header / Topic Badge */}
      {title ? (
        <div
          style={{
            position: 'absolute',
            top: 100,
            left: 30,
            right: 30,
            display: 'flex',
            justifyContent: 'center',
            opacity: headerOpacity,
            transform: `translateY(${(1 - headerEntrance) * -40}px)`,
            zIndex: 90,
            pointerEvents: 'none',
          }}
        >
          <div
            style={{
              padding: '14px 28px',
              backgroundColor: 'rgba(0, 0, 0, 0.7)',
              border:
                style === 'anime'
                  ? '2px solid #FFE500'
                  : '2px solid rgba(255, 255, 255, 0.3)',
              borderRadius: 30,
              boxShadow: '0 8px 30px rgba(0, 0, 0, 0.7)',
              backdropFilter: 'blur(10px)',
            }}
          >
            <span
              style={{
                fontFamily:
                  'Impact, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                fontSize: 34,
                fontWeight: 900,
                letterSpacing: 2,
                textTransform: 'uppercase',
                color: style === 'anime' ? '#FFE500' : '#FFFFFF',
                textShadow: '0 2px 10px rgba(0,0,0,0.8)',
              }}
            >
              {title}
            </span>
          </div>
        </div>
      ) : null}

      {/* Dynamic Word-by-Word Kinetic Captions */}
      <CaptionsOverlay words={words} style={style} />

      {/* Logo Watermark (Corner) */}
      {logoSrc ? (
        <div
          style={{
            position: 'absolute',
            top: 40,
            right: 40,
            opacity: 0.8,
            zIndex: 95,
            pointerEvents: 'none',
          }}
        >
          <Img
            src={logoSrc}
            style={{
              width: 90,
              height: 90,
              objectFit: 'contain',
              filter: 'drop-shadow(0 4px 10px rgba(0,0,0,0.6))',
            }}
          />
        </div>
      ) : null}
    </AbsoluteFill>
  );
};
