import { adminCommands } from '@/modules/discord/commands/admin';
// import { exampleCommands } from '@/modules/discord/commands/examples';
import { contextMenus } from '@/modules/discord/commands/contextMenus';
import { utilCommands } from '@/modules/discord/commands/util';
import { bonfireCommands } from '@/modules/discord/commands/bonfire';

const commands = [
  ...adminCommands,
  ...utilCommands,
  ...contextMenus,
  // ...exampleCommands,
  ...bonfireCommands,
];

export { commands };
