export interface SceneItem {
  type: 'image' | 'video';
  src: string;
  durationInFrames: number;
  volume?: number;
}

export interface WordItem {
  word: string;
  start: number; // in seconds
  end: number;   // in seconds
}

export type VideoStyle = 'anime' | 'cinematic' | 'viral' | 'chill';

export interface CharacterInfo {
  name: string;
  avatarSrc?: string;
  fullBodySrc?: string;
  condition?: string;
  gear?: string;
  day?: number;
  mentalState?: string;
}

export interface ShortsVideoProps {
  scenes: SceneItem[];
  voiceoverSrc?: string;
  words?: WordItem[];
  musicSrc?: string;
  musicVolume?: number;
  ambientSrc?: string;
  ambientVolume?: number;
  style?: VideoStyle;
  title?: string;
  episodeBadge?: string;
  chapterSubtitle?: string;
  cliffhangerCta?: string;
  logoSrc?: string;
  character?: CharacterInfo;
  durationInFrames: number;
  useOriginalAudio?: boolean;
}

