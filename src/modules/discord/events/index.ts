import { readyEvent, IDiscordEventReady } from './ready';
import { disconnectEvent, IDiscordEventDisconnect } from './disconnect';
import { interactionCreateEvent, IDiscordEventInteractionCreate } from './interactionCreate';

const events: (
  | IDiscordEventReady
  | IDiscordEventDisconnect
  | IDiscordEventInteractionCreate
)[] = [
  readyEvent,
  disconnectEvent,
  interactionCreateEvent,
];

export { events };
