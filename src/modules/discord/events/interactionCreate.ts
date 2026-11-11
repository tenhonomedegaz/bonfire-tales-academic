import { Interaction, TextChannel, MessageFlags } from 'discord.js';
import { ComponentType } from "discord.js";

import { handleInteractionButton } from '@/modules/discord/events/handlers/handleInteractionButton';
import { IBotEnhanced } from '@/modules/discord/types';
import { handleInteractionContextMenu } from '@/modules/discord/events/handlers/handleInteractionContextMenu';
import { handleInteractionCommand } from '@/modules/discord/events/handlers/handleInteractionCommand';
import { handleInteractionAutoComplete } from '@/modules/discord/events/handlers/handleInteractionAutoComplete';

export interface IDiscordEventInteractionCreate {
  name: string;
  once: boolean;
  execute: (bot: IBotEnhanced, interaction: Interaction) => Promise<void>;
}

export const interactionCreateEvent: IDiscordEventInteractionCreate = {
  name: 'interactionCreate',
  once: false,
  execute: async (bot, interaction) => {
    try {
      // Logging
      if (interaction.channel?.isTextBased()) {
        console.log(
          `(${interaction.guild?.name}) - ${interaction.user.tag} (${interaction.user.id}) in #${
            (interaction.channel as TextChannel)?.name
          }\n${interaction.type} - command: ${
            interaction.isChatInputCommand() ? interaction.commandName : ''
          }`
        );
      }

      // Autocomplete
      if (interaction.isAutocomplete()) {
        await handleInteractionAutoComplete(bot, interaction);
        return;
      }

      // Slash commands
      if (interaction.isChatInputCommand()) {
        await handleInteractionCommand(bot, interaction);
        return;
      }

      // Context menu
      if (interaction.isContextMenuCommand()) {
        await handleInteractionContextMenu(bot, interaction);
        return;
      }

      // Buttons
      if (interaction.isMessageComponent() && interaction.componentType === ComponentType.Button) {
        console.log("BUTTON CLICKED:", interaction.customId);

        // ✔ All buttons use the normal handler
        await handleInteractionButton(bot, interaction);
        return;
      }

      // String select menus
      if (interaction.isStringSelectMenu()) {
        return;
      }

      // Modal submit
      if (interaction.isModalSubmit()) {
        return;
      }

    } catch (error) {
      bot.logger.log('error', 'interactionCreateEvent', error);

      if (!(interaction as any).replied && !(interaction as any).deferred) {
        try {
          await (interaction as any).reply({
            content: 'Ocorreu um erro durante a interação.',
            flags: [MessageFlags.Ephemeral],
          });
        } catch {}
      }
    }
  },
};
