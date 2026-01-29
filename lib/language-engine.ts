
import { Language } from '../types';
import { GoogleGenAI, Modality } from "@google/genai";

// --- Mappings ---

const LATIN_TO_RUNIC: Record<string, string> = {
  a: 'ᚨ', b: 'ᛒ', c: 'ᚲ', d: 'ᛞ', e: 'ᛖ', f: 'ᚠ', g: 'ᚷ', h: 'ᚺ', i: 'ᛁ', 
  j: 'ᛃ', k: 'ᚴ', l: 'ᛚ', m: 'ᛗ', n: 'ᚾ', o: 'ᛟ', p: 'ᛈ', q: 'ᛩ', r: 'ᚱ', 
  s: 'ᛊ', t: 'ᛏ', u: 'ᚢ', v: 'ᚡ', w: 'ᚹ', x: 'ᛪ', y: 'ᛇ', z: 'ᛉ',
  ' ': ':', '.': '᛫', ',': '᛬'
};

const LATIN_TO_BRAILLE: Record<string, string> = {
  'a': '⠁', 'b': '⠃', 'c': '⠉', 'd': '⠙', 'e': '⠑', 'f': '⠋', 'g': '⠛', 'h': '⠓', 'i': '⠊', 'j': '⠚',
  'k': '⠅', 'l': '⠇', 'm': '⠍', 'n': '⠝', 'o': '⠕', 'p': '⠏', 'q': '⠟', 'r': '⠗', 's': '⠎', 't': '⠞',
  'u': '⠥', 'v': '⠧', 'w': '⠺', 'x': '⠭', 'y': '⠽', 'z': '⠵', ' ': ' ', ',': '⠂', '.': '⠲'
};

const LATIN_TO_ELVISH_AESTHETIC: Record<string, string> = {
  a: 'á', e: 'ë', i: 'í', o: 'ó', u: 'ú', y: 'ŷ',
  th: 'þ', dh: 'ð'
};

const GEMINI_VOICE_MAP: Record<string, string> = {
  'pt-BR': 'Puck',
  'de-DE': 'Fenrir',
  'is-IS': 'Fenrir',
  'cy-GB': 'Kore',
  'tr-TR': 'Charon',
  'ar-SA': 'Zephyr',
  'default': 'Puck'
};

// --- Transliteration Engine ---

export const transliterateText = (text: string, engine: string): string => {
  if (!text) return "";
  const normalized = text.toLowerCase();
  
  if (engine === 'runic') {
    return normalized.split('').map(char => LATIN_TO_RUNIC[char] || char).join('');
  }
  
  if (engine === 'braille') {
    return normalized.split('').map(char => LATIN_TO_BRAILLE[char] || char).join('');
  }

  if (engine === 'tengwar') {
    return text.replace(/[aeiouy]/g, (m) => LATIN_TO_ELVISH_AESTHETIC[m] || m);
  }

  return text; 
};

// --- Translation Engine ---

export const translateText = (text: string, lang: Language): string => {
  if (!text) return "";
  if (lang.modality === 'signed') {
    return text.toUpperCase()
      .replace(/\s(A|O|DE|DA|DO|UM|UMA)\s/gi, ' ')
      .replace(/\b(ESTOU|ESTÁ|ESTAVA)\s/gi, '')
      .trim();
  }

  const words = text.split(/\b/);
  const dictionary = lang.dictionary || {};

  const translatedWords = words.map(word => {
    const key = word.toLowerCase();
    if (dictionary[key]) {
      const isCap = word[0] === word[0].toUpperCase() && word[0] !== word[0].toLowerCase();
      const trans = dictionary[key];
      return isCap ? trans.charAt(0).toUpperCase() + trans.slice(1) : trans;
    }

    if (!word.match(/[a-zà-ú]/i)) return word;

    if (lang.slug === 'elfico') {
      return word.replace(/r$/i, 'rion').replace(/o$/i, 'on').replace(/a$/i, 'ë');
    }

    if (lang.slug === 'orquico') {
      let t = word.replace(/a/gi, 'u').replace(/e/gi, 'agh').replace(/i/gi, 'uk');
      if (t.length > 4 && !t.includes("'")) t = t.slice(0, 3) + "'" + t.slice(3);
      return t.toUpperCase();
    }

    return word;
  });

  return translatedWords.join('');
};

// --- TTS Logic ---

async function decodeAudioData(data: Uint8Array, ctx: AudioContext, sampleRate: number): Promise<AudioBuffer> {
  const dataInt16 = new Int16Array(data.buffer);
  const buffer = ctx.createBuffer(1, dataInt16.length, sampleRate);
  const channelData = buffer.getChannelData(0);
  for (let i = 0; i < dataInt16.length; i++) {
    channelData[i] = dataInt16[i] / 32768.0;
  }
  return buffer;
}

export const speakText = async (text: string, langRef: string) => {
  if (!text) return;
  
  try {
    if (typeof process !== 'undefined' && process.env.API_KEY) {
      const ai = new GoogleGenAI({ apiKey: process.env.API_KEY });
      const voiceName = GEMINI_VOICE_MAP[langRef] || GEMINI_VOICE_MAP['default'];
      
      // FIX: Add a clear instruction to the prompt to ensure TTS model understands the task.
      const prompt = `Say: ${text}`;
      
      const response = await ai.models.generateContent({
        model: "gemini-2.5-flash-preview-tts",
        contents: [{ parts: [{ text: prompt }] }],
        config: {
          responseModalities: [Modality.AUDIO],
          speechConfig: {
            voiceConfig: { prebuiltVoiceConfig: { voiceName } },
          },
        },
      });

      const base64Audio = response.candidates?.[0]?.content?.parts?.[0]?.inlineData?.data;
      if (base64Audio) {
        const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 24000 });
        const binaryString = atob(base64Audio);
        const len = binaryString.length;
        const bytes = new Uint8Array(len);
        for (let i = 0; i < len; i++) bytes[i] = binaryString.charCodeAt(i);
        
        const buffer = await decodeAudioData(bytes, audioContext, 24000);
        const source = audioContext.createBufferSource();
        source.buffer = buffer;
        source.connect(audioContext.destination);
        source.start();
        return;
      }
    }
  } catch (err) {
    console.error("Gemini TTS Error, falling back to WebSpeech:", err);
  }

  // Fallback to Web Speech API
  if ('speechSynthesis' in window) {
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = langRef;
    window.speechSynthesis.speak(utterance);
  }
};
