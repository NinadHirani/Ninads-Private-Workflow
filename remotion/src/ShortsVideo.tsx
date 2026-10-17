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
  episodeBadge,
  chapterSubtitle,
  cliffhangerCta,
  logoSrc,
  durationInFrames,
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

      {/* Episodic Series Badge or Top Topic Badge */}
      {episodeBadge || title ? (
        <div
          style={{
            position: 'absolute',
            top: 80,
            left: 30,
            right: 30,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            opacity: headerOpacity,
            transform: `translateY(${(1 - headerEntrance) * -40}px)`,
            zIndex: 90,
            pointerEvents: 'none',
          }}
        >
          <div
            style={{
              padding: episodeBadge ? '12px 28px' : style === 'chill' ? '12px 24px' : '14px 28px',
              backgroundColor: episodeBadge ? 'rgba(8, 12, 20, 0.88)' : style === 'chill' ? 'rgba(15, 23, 42, 0.75)' : 'rgba(0, 0, 0, 0.75)',
              border: episodeBadge
                ? '2px solid rgba(239, 68, 68, 0.85)'
                : style === 'anime'
                ? '2px solid #FFE500'
                : style === 'chill'
                ? '1px solid rgba(255, 255, 255, 0.25)'
                : '2px solid rgba(255, 255, 255, 0.3)',
              borderRadius: 24,
              boxShadow: episodeBadge
                ? '0 10px 35px rgba(0, 0, 0, 0.9), 0 0 20px rgba(239, 68, 68, 0.35)'
                : '0 8px 30px rgba(0, 0, 0, 0.7)',
              backdropFilter: 'blur(14px)',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 4,
            }}
          >
            <span
              style={{
                fontFamily:
                  style === 'chill'
                    ? '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
                    : 'Impact, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                fontSize: episodeBadge ? 30 : style === 'chill' ? 24 : 32,
                fontWeight: 900,
                letterSpacing: 2.2,
                textTransform: 'uppercase',
                color: '#FFFFFF',
                textShadow: '0 2px 10px rgba(0,0,0,0.9)',
              }}
            >
              {episodeBadge || title}
            </span>
            {chapterSubtitle ? (
              <span
                style={{
                  fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                  fontSize: 18,
                  fontWeight: 700,
                  letterSpacing: 3,
                  textTransform: 'uppercase',
                  color: '#EF4444',
                  textShadow: '0 2px 8px rgba(0,0,0,0.8)',
                }}
              >
                {chapterSubtitle}
              </span>
            ) : null}
          </div>
        </div>
      ) : null}

      {/* Dynamic Word-by-Word Kinetic Captions (renders null if words is empty) */}
      {words && words.length > 0 ? (
        <CaptionsOverlay words={words} style={style} />
      ) : null}

      {/* Cliffhanger Outro CTA Banner (fades in during last 4 seconds) */}
      {cliffhangerCta ? (
        <div
          style={{
            position: 'absolute',
            bottom: 120,
            left: 30,
            right: 30,
            display: 'flex',
            justifyContent: 'center',
            opacity: interpolate(
              frame,
              [Math.max(0, durationInFrames - fps * 4), Math.max(0, durationInFrames - fps * 3.2)],
              [0, 1],
              { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }
            ),
            zIndex: 92,
            pointerEvents: 'none',
          }}
        >
          <div
            style={{
              padding: '12px 28px',
              backgroundColor: 'rgba(15, 23, 42, 0.92)',
              border: '2px solid #EF4444',
              borderRadius: 24,
              boxShadow: '0 10px 40px rgba(0, 0, 0, 0.95), 0 0 20px rgba(239, 68, 68, 0.45)',
              backdropFilter: 'blur(16px)',
              textAlign: 'center',
            }}
          >
            <span
              style={{
                fontFamily: 'Impact, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                fontSize: 24,
                fontWeight: 800,
                letterSpacing: 2,
                textTransform: 'uppercase',
                color: '#F8FAFC',
                textShadow: '0 2px 10px rgba(0,0,0,0.9)',
              }}
            >
              {cliffhangerCta}
            </span>
          </div>
        </div>
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
