import React from 'react';
import { Composition, CalculateMetadataFunction } from 'remotion';
import { ShortsVideo } from './ShortsVideo';
import { ShortsVideoProps } from './types';

const defaultProps: ShortsVideoProps = {
  scenes: [
    {
      type: 'image',
      src: 'https://images.unsplash.com/photo-1534447677768-be436bb09401?w=1080&h=1920&fit=crop',
      durationInFrames: 150,
    },
    {
      type: 'image',
      src: 'https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=1080&h=1920&fit=crop',
      durationInFrames: 150,
    },
  ],
  voiceoverSrc: '',
  words: [
    { word: 'ONE', start: 0.2, end: 0.6 },
    { word: 'PUNCH', start: 0.6, end: 1.0 },
    { word: 'MAN', start: 1.0, end: 1.4 },
    { word: 'IS', start: 1.5, end: 1.8 },
    { word: 'LEGENDARY', start: 1.8, end: 2.5 },
  ],
  style: 'anime',
  title: 'ONE-PUNCH MAN ANIME',
  durationInFrames: 300,
  useOriginalAudio: false,
};

const calculateMetadata: CalculateMetadataFunction<ShortsVideoProps> = ({
  props,
}) => {
  const duration = props.durationInFrames || 300;
  return {
    durationInFrames: duration,
    width: 1080,
    height: 1920,
    fps: 30,
  };
};

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="ShortsVideo"
        component={ShortsVideo}
        durationInFrames={300}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={defaultProps}
        calculateMetadata={calculateMetadata}
      />
    </>
  );
};
