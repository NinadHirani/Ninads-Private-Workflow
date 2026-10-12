export interface SceneItem {
  type: 'image' | 'video';
  src: string;
  durationInFrames: number;
}

export interface WordItem {
  word: string;
  start: number; // in seconds
  end: number;   // in seconds
}

export type VideoStyle = 'anime' | 'cinematic' | 'viral' | 'chill';

export interface ShortsVideoProps {
  scenes: SceneItem[];
  voiceoverSrc: string;
  words: WordItem[];
  musicSrc?: string;
  musicVolume?: number;
  style?: VideoStyle;
  title?: string;
  logoSrc?: string;
  durationInFrames: number;
}
