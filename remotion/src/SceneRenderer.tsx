import {
  AbsoluteFill,
  Sequence,
  useCurrentFrame,
  interpolate,
  Easing,
  Img,
  Video,
  staticFile,
} from 'remotion';
import { SceneItem, VideoStyle } from './types';

const resolveMediaSrc = (src: string): string => {
  if (!src) return '';
  if (src.startsWith('data:') || src.startsWith('http://') || src.startsWith('https://')) {
    return src;
  }
  if (src.startsWith('/Users') || src.startsWith('/home') || src.startsWith('C:') || src.startsWith('D:')) {
    const parts = src.split(/public[/\\]+/);
    if (parts.length > 1) {
      return staticFile(parts[1].replace(/^[/\\]+/, ''));
    }
    return '';
  }
  return staticFile(src.replace(/^[/\\]+/, ''));
};

const SingleScene: React.FC<{
  scene: SceneItem;
  index: number;
  style?: VideoStyle;
  useOriginalAudio?: boolean;
}> = ({ scene, index, style = 'anime', useOriginalAudio = false }) => {
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

  const mediaSrc = resolveMediaSrc(scene.src);
  const sceneVolume = scene.volume !== undefined ? scene.volume : (useOriginalAudio ? 1.0 : 0.0);

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
            src={mediaSrc}
            loop
            volume={sceneVolume}
            style={{
              width: '100%',
              height: '100%',
              objectFit: 'cover',
            }}
          />
        ) : (
          <Img
            src={mediaSrc}
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
  useOriginalAudio?: boolean;
}> = ({ scenes, style, useOriginalAudio = false }) => {
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
            <SingleScene
              scene={scene}
              index={idx}
              style={style}
              useOriginalAudio={useOriginalAudio}
            />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
