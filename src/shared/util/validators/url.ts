import { URL } from 'url';

export function isValidUrl(value: string, protocols = ['http', 'https']): boolean {
  try {
    const url = new URL(value);
    const protocolsWithColon = protocols.map((protocol) => `${protocol.toLowerCase()}:`);
    return protocolsWithColon.includes(url.protocol.toLowerCase());
  } catch (error) {
    return false;
  }
}
