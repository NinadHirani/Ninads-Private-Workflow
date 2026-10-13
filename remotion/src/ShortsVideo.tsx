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
  ambientSrc,
  ambientVolume = 0.65,
  style = 'anime',
  title,
  logoSrc,
  useOriginalAudio = false,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Top header badge animation (enters during first 15 frames, stays for 4.5 seconds, fades out)
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
      <SceneRenderer
        scenes={scenes}
        style={style}
        useOriginalAudio={useOriginalAudio}
      />

      {/* Ambient Soundscape Track (rain, ocean surf, forest wind ASMR) */}
      {ambientSrc ? (
        <Audio src={ambientSrc} volume={ambientVolume} loop />
      ) : null}

      {/* Background Music Track (only played if volume > 0) */}
      {musicSrc && musicVolume > 0 ? (
        <Audio src={musicSrc} volume={musicVolume} loop />
      ) : null}

      {/* Spoken AI Voiceover (only played in commentary mode, never over original scene voice) */}
      {!useOriginalAudio && voiceoverSrc ? <Audio src={voiceoverSrc} /> : null}

      {/* Optional Top Hook Header / Topic Badge */}
      {title ? (
        <div
          style={{
            position: 'absolute',
            top: 90,
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
              padding: style === 'chill' ? '12px 24px' : '14px 28px',
              backgroundColor:
                style === 'chill'
                  ? 'rgba(15, 23, 42, 0.75)'
                  : 'rgba(0, 0, 0, 0.75)',
              border:
                style === 'anime'
                  ? '2px solid #FFE500'
                  : style === 'chill'
                  ? '1px solid rgba(255, 255, 255, 0.25)'
                  : '2px solid rgba(255, 255, 255, 0.3)',
              borderRadius: 30,
              boxShadow: '0 8px 30px rgba(0, 0, 0, 0.7)',
              backdropFilter: 'blur(12px)',
            }}
          >
            <span
              style={{
                fontFamily:
                  style === 'chill'
                    ? '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
                    : 'Impact, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                fontSize: style === 'chill' ? 24 : 32,
                fontWeight: style === 'chill' ? 700 : 900,
                letterSpacing: style === 'chill' ? 1.5 : 2,
                textTransform: 'uppercase',
                color:
                  style === 'anime'
                    ? '#FFE500'
                    : style === 'chill'
                    ? '#F8FAFC'
                    : '#FFFFFF',
                textShadow: '0 2px 10px rgba(0,0,0,0.8)',
              }}
            >
              {title}
            </span>
          </div>
        </div>
      ) : null}

      {/* Dynamic Word-by-Word Kinetic Captions (renders null if words is empty) */}
      {words && words.length > 0 ? (
        <CaptionsOverlay words={words} style={style} />
      ) : null}

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
