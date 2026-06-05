export type BobbyState = 'idle' | 'listening' | 'thinking' | 'speaking';

export interface BobbyEvent {
  state: BobbyState;
  text: string;
  transcript: string[];
  timestamp: string;
}
