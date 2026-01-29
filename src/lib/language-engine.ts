
import { Language } from '../../types';
import { GoogleGenAI, Modality } from "@google/genai";

// --- Mappings ---

// Basic Runic Mapping (Futhark-ish) for Dwarvish/Giant
const LATIN_TO_RUNIC: Record<string, string> = {
  a: 'ᚨ', b: 'ᛒ', c: 'ᚲ', d: 'ᛞ', e: 'ᛖ', f: 'ᚠ', g: 'ᚷ', h: 'ᚺ', i: 'ᛁ', 
  j: 'ᛃ', k: 'ᚴ', l: 'ᛚ', m: 'ᛗ', n: 'ᚾ', o: 'ᛟ', p: 'ᛈ', q: 'ᛩ', r: 'ᚱ', 
  s: 'ᛊ', t: 'ᛏ', u: 'ᚢ', v: 'ᚡ', w: 'ᚹ', x: 'ᛪ', y: 'ᛇ', z: 'ᛉ',
  ' ': ':', '.': '᛫', ',': '᛬'
};

// Mock Mapping for "Elvish" (Visual aesthetic only for MVP)
// Real Tengwar requires a font. We'll use Unicode lookalikes or accented chars for "aesthetic" if native font fails.
const LATIN_TO_ELVISH_AESTHETIC: Record<string, string> = {
  a: 'á', e: 'ë', i: 'í', o: 'ó', u: 'ú', y: 'ŷ',
  th: 'þ', dh: 'ð'
};

// Gemini Voice Mapping based on Culture/Vibe
const GEMINI_VOICE_MAP: Record<string, string> = {
  'pt-BR': 'Puck',   // Comum (Neutral/Friendly)
  'de-DE': 'Fenrir', // Enânico (Deep/Strong)
  'is-IS': 'Fenrir', // Gigante (Deep/Ancient)
  'cy-GB': 'Kore',   // Élfico (Soft/Melodic)
  'tr-TR': 'Charon', // Órquico (Rough/Deep)
  'hu-HU': 'Puck',   // Goblínico (High/Fast - Puck is versatile)
  'ar-SA': 'Zephyr', // Dracônico (Calm/Mystical)
  'it-IT': 'Zephyr', // Celestial (Calm/Angelic)
  'la': 'Fenrir',    // Infernal (Commanding)
  'default': 'Puck'
};

// --- Transliteration Engine ---

export const transliterateText = (text: string, engine: string): string => {
  const normalized = text.toLowerCase();
  
  if (engine === 'runic') {
    return normalized.split('').map(char => LATIN_TO_RUNIC[char] || char).join('');
  }
  
  if (engine === 'tengwar') {
    // MVP: Just makes it look fancy/accented since we don't have a Tengwar webfont loaded in the prompt context
    return text.replace(/[aeiouy]/g, (m) => LATIN_TO_ELVISH_AESTHETIC[m] || m);
  }

  // Draconic could use a specific font class in CSS, here we return raw
  return text; 
};

// --- Translation Engine (Mock/Dictionary) ---

export const translateText = (text: string, lang: Language): string => {
  // 1. Direct Dictionary Lookup
  const words = text.split(/\b/); // Split keeping delimiters
  const dictionary = lang.dictionary || {};

  const translatedWords = words.map(word => {
    const key = word.toLowerCase();
    
    // Check Dictionary
    if (dictionary[key]) {
      // Preserve Case (Basic)
      const isCap = word[0] === word[0].toUpperCase() && word[0] !== word[0].toLowerCase();
      const trans = dictionary[key];
      return isCap ? trans.charAt(0).toUpperCase() + trans.slice(1) : trans;
    }

    // 2. Fallback: Phonetic Filters (Make it sound like the language)
    // Only apply to actual words (len > 1)
    if (!word.match(/[a-zà-ú]/i)) return word;

    if (lang.slug === 'elfico') {
      // Elvish: More vowels, softer endings
      let t = word.replace(/r$/i, 'rion').replace(/o$/i, 'on').replace(/a$/i, 'ë');
      return t;
    }

    if (lang.slug === 'orquico') {
      // Orcish: Hard consonants, guttural
      let t = word.replace(/a/gi, 'u').replace(/e/gi, 'agh').replace(/i/gi, 'uk');
      if (t.length > 4 && !t.includes("'")) t = t.slice(0, 3) + "'" + t.slice(3);
      return t.toUpperCase();
    }

    if (lang.slug === 'enanico') {
      // Dwarvish: Consonant heavy
      let t = word.replace(/a/gi, 'o').replace(/u/gi, 'û').replace(/th/gi, 'z');
      if (!t.match(/[kzgh]/)) t += "kh";
      return t;
    }

    if (lang.slug === 'goblinico') {
      // Goblin: Chattery, repetitive
      let t = word.replace(/s/gi, 'zz').replace(/k/gi, 'k-k');
      return t;
    }

    // Common/Default
    return word;
  });

  return translatedWords.join('');
};

// --- Audio Decoding Helpers (For Gemini Raw PCM) ---

function decodeBase64(base64: string) {
  const binaryString = atob(base64);
  const len = binaryString.length;
  const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }
  return bytes;
}

async function decodeAudioData(
  data: Uint8Array,
  ctx: AudioContext,
  sampleRate: number,
  numChannels: number,
): Promise<AudioBuffer> {
  const dataInt16 = new Int16Array(data.buffer);
  const frameCount = dataInt16.length / numChannels;
  const buffer = ctx.createBuffer(numChannels, frameCount, sampleRate);

  for (let channel = 0; channel < numChannels; channel++) {
    const channelData = buffer.getChannelData(channel);
    for (let i = 0; i < frameCount; i++) {
      channelData[i] = dataInt16[i * numChannels + channel] / 32768.0;
    }
  }
  return buffer;
}

let geminiAudioContext: AudioContext | null = null;

async function speakWithGemini(text: string, langRef: string) {
  const voiceName = GEMINI_VOICE_MAP[langRef] || GEMINI_VOICE_MAP['default'];
  
  // Note: Assuming process.env.API_KEY is available in the environment
  const ai = new GoogleGenAI({ apiKey: process.env.API_KEY });
  
  const response = await ai.models.generateContent({
    model: "gemini-2.5-flash-preview-tts",
    contents: [{ parts: [{ text }] }],
    config: {
      responseModalities: [Modality.AUDIO],
      speechConfig: {
        voiceConfig: {
          prebuiltVoiceConfig: { voiceName },
        },
      },
    },
  });

  const base64Audio = response.candidates?.[0]?.content?.parts?.[0]?.inlineData?.data;
  if (!base64Audio) throw new Error("No audio data returned");

  if (!geminiAudioContext) {
    geminiAudioContext = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 24000 });
  }

  const audioBuffer = await decodeAudioData(
    decodeBase64(base64Audio),
    geminiAudioContext,
    24000,
    1
  );

  const source = geminiAudioContext.createBufferSource();
  source.buffer = audioBuffer;
  source.connect(geminiAudioContext.destination);
  source.start();
}

// --- TTS Main Function ---

export const speakText = async (text: string, langRef: string) => {
  // 1. Try Gemini TTS (Humanized)
  if (process.env.API_KEY) {
    try {
      await speakWithGemini(text, langRef);
      return;
    } catch (e) {
      console.warn("Gemini TTS falhou, usando fallback do navegador.", e);
    }
  } else {
    // Silent fail/log if no API key, proceed to fallback
    console.debug("Sem API Key para Gemini TTS, usando Web Speech.");
  }

  // 2. Fallback: Web Speech API (Robotic)
  if (!('speechSynthesis' in window)) {
    console.warn("Web Speech API not supported.");
    return;
  }

  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  
  // Find voice
  const voices = window.speechSynthesis.getVoices();
  const voice = voices.find(v => v.lang === langRef) || 
                voices.find(v => v.lang.startsWith(langRef.split('-')[0]));

  if (voice) {
    utterance.voice = voice;
  } else {
    // Fallback tuning for flavor
    if (langRef === 'is-IS' || langRef === 'de-DE' || langRef === 'tr-TR') { 
        utterance.pitch = 0.6; // Deep
        utterance.rate = 0.8;
    } else if (langRef === 'cy-GB') { 
        utterance.pitch = 1.2; // High/Soft
    }
  }
  
  utterance.lang = langRef;
  window.speechSynthesis.speak(utterance);
};
