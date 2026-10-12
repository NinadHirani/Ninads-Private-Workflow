import React from 'react';
import {
  AbsoluteFill,
  Sequence,
  useCurrentFrame,
  interpolate,
  Easing,
  Img,
  Video,
} from 'remotion';
import { SceneItem, VideoStyle } from './types';

const SingleScene: React.FC<{
  scene: SceneItem;
  index: number;
  style?: VideoStyle;
}> = ({ scene, index, style = 'anime' }) => {
  const frame = useCurrentFrame();
  const duration = scene.durationInFrames;

  // Alternate Ken Burns direction between scenes: zoom-in vs zoom-out with pan
  const isEven = index % 2 === 0;
  const scale = interpolate(
    frame,
    [0, duration],
    isEven ? [1.02, 1.16] : [1.16, 1.02],
    {
      easing: Easing.bezier(0.25, 0.1, 0.25, 1),
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    }
  );

  const translateY = interpolate(
    frame,
    [0, duration],
    isEven ? [0, -25] : [-25, 0],
    {
      easing: Easing.linear,
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    }
  );

  // Crossfade at beginning and end of each scene
  const opacity = interpolate(
    frame,
    [0, 10, duration - 10, duration],
    [0.75, 1, 1, 0.85],
    {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    }
  );

  return (
    <AbsoluteFill
      style={{
        overflow: 'hidden',
        backgroundColor: '#0a0a0c',
        opacity,
      }}
    >
      <div
        style={{
          width: '100%',
          height: '100%',
          transform: `scale(${scale}) translateY(${translateY}px)`,
          transformOrigin: isEven ? 'center center' : 'center top',
        }}
      >
        {scene.type === 'video' ? (
          <Video
            src={scene.src}
            style={{
              width: '100%',
              height: '100%',
              objectFit: 'cover',
            }}
          />
        ) : (
          <Img
            src={scene.src}
            style={{
              width: '100%',
              height: '100%',
              objectFit: 'cover',
            }}
          />
        )}
      </div>

      {/* Cinematic Vignette */}
      <AbsoluteFill
        style={{
          background:
            style === 'anime'
              ? 'radial-gradient(circle at center, transparent 40%, rgba(10,5,20,0.65) 90%, rgba(0,0,0,0.95) 100%)'
              : 'radial-gradient(circle at center, transparent 45%, rgba(0,0,0,0.55) 85%, rgba(0,0,0,0.9) 100%)',
          pointerEvents: 'none',
        }}
      />

      {/* Top & Bottom Cinematic Shadows for Title & Captions Readability */}
      <AbsoluteFill
        style={{
          background:
            'linear-gradient(to bottom, rgba(0,0,0,0.7) 0%, transparent 18%, transparent 70%, rgba(0,0,0,0.85) 100%)',
          pointerEvents: 'none',
        }}
      />
    </AbsoluteFill>
  );
};

export const SceneRenderer: React.FC<{
  scenes: SceneItem[];
  style?: VideoStyle;
}> = ({ scenes, style }) => {
  let accumulatedFrames = 0;

  return (
    <AbsoluteFill>
      {scenes.map((scene, idx) => {
        const fromFrame = accumulatedFrames;
        accumulatedFrames += scene.durationInFrames;

        return (
          <Sequence
            key={idx}
            from={fromFrame}
            durationInFrames={scene.durationInFrames}
          >
            <SingleScene scene={scene} index={idx} style={style} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
